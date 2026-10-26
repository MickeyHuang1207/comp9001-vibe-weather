import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import patch

from analysis import SentimentEngine, WeatherReporter, rescore_all
from cli import VibeWeatherApp
from journal import (DIMENSIONS, CorruptedDataError, InvalidEntryError, JournalEntry,
                     SchemaMismatchError)
from storage import JournalStore

NEUTRAL = {d: 0.5 for d in DIMENSIONS}


class TestScoring(unittest.TestCase):
    """Cases from the tutor's feedback."""

    def setUp(self):
        self.engine = SentimentEngine()

    def test_negation_changes_score(self):
        happy, _ = self.engine.score("I am happy")
        not_happy, _ = self.engine.score("I am not happy")
        self.assertNotEqual(happy, not_happy)
        self.assertGreater(happy["vitality"], not_happy["vitality"])

    def test_intensity(self):
        very, _ = self.engine.score("I am very stressed")
        slightly, _ = self.engine.score("I am slightly stressed")
        self.assertGreater(very["stress"], slightly["stress"])

    def test_mixed_signals(self):
        mixed, _ = self.engine.score(
            "I was stressed this morning, but I feel much better now")
        stressed, _ = self.engine.score("I was stressed this morning")
        self.assertLess(mixed["stress"], stressed["stress"])

    def test_scores_in_range(self):
        for text in ["", "hello world", "extremely very stressed anxious angry"]:
            scores, _ = self.engine.score(text)
            for d in DIMENSIONS:
                self.assertTrue(0.0 <= scores[d] <= 1.0, (text, d, scores[d]))

    def test_no_keywords_is_neutral_foggy(self):
        scores, _ = self.engine.score("I went to the library")
        self.assertEqual(scores, NEUTRAL)
        self.assertEqual(WeatherReporter().classify(scores), "Foggy")

    def test_empty_entry_is_neutral(self):
        scores, _ = self.engine.score("")
        self.assertEqual(scores, NEUTRAL)

    def test_custom_keyword_changes_score(self):
        before, _ = self.engine.score("big deadline today")
        self.engine.add_keyword("deadline", {"stress": 1.0, "vitality": 0.2, "calmness": 0.0})
        after, explanation = self.engine.score("big deadline today")
        self.assertGreater(after["stress"], before["stress"])
        self.assertTrue(any("deadline" in line for line in explanation))

    def test_weather_mapping(self):
        r = WeatherReporter()
        self.assertEqual(r.classify(self.engine.score("I am very stressed")[0]), "Stormy")
        self.assertEqual(r.classify(self.engine.score("I feel happy and energetic")[0]), "Sunny")

    def test_more_weather(self):
        r = WeatherReporter()
        cases = {"Exhausted and sad, I did not sleep well": "Rainy",
                 "Relaxed and peaceful day at the beach": "Sunny",
                 "I am tired": "Overcast",
                 "I was stressed this morning, but I feel much better now": "Partly Cloudy"}
        for text, weather in cases.items():
            self.assertEqual(r.classify(self.engine.score(text)[0]), weather, text)

    def test_every_score_gets_a_weather(self):
        """The rule table has no gaps: every score maps to a real weather."""
        r = WeatherReporter()
        grid = [i / 10 for i in range(11)]
        for s in grid:
            for v in grid:
                for c in grid:
                    weather = r.classify({"stress": s, "vitality": v, "calmness": c})
                    self.assertIn(weather, r.WEATHER_ICONS)
                    self.assertNotEqual(weather, "Unclassified")

    def test_weather_reason(self):
        weather, rule = WeatherReporter().explain_weather(
            self.engine.score("I am very stressed")[0])
        self.assertEqual(weather, "Stormy")
        self.assertIn("stress", rule)

    def test_concession_clause_counts_less(self):
        mixed, _ = self.engine.score("Although I was stressed, I feel better")
        stressed, _ = self.engine.score("I was stressed")
        self.assertLess(mixed["stress"], stressed["stress"])

    def test_negation_stops_at_comma(self):
        self.assertEqual(self.engine.score("No, I am happy")[0],
                         self.engine.score("I am happy")[0])

    def test_explanation_mentions_keyword(self):
        _, explanation = self.engine.score("I am very stressed")
        self.assertTrue(any("stressed" in line for line in explanation))

    def test_negation_reaches_next_mood_word(self):
        happy, _ = self.engine.score("I am really happy")
        far, _ = self.engine.score("I don't think that I am really happy")
        self.assertLess(far["vitality"], happy["vitality"])

    def test_one_negator_cancels_one_word(self):
        scores, _ = self.engine.score("I am not tired and I feel great")
        great, _ = self.engine.score("I feel great")
        self.assertGreater(scores["vitality"], 0.7)          # "great" is not negated
        self.assertLessEqual(scores["vitality"], great["vitality"] + 0.1)

    def test_negating_unpleasant_is_weaker(self):
        """Litotes: "not bad" is only okay, while "not good" is clearly bad."""
        self.engine.add_keyword("sunny", {"stress": 0.0, "vitality": 1.0, "calmness": 1.0})
        self.engine.add_keyword("gloomy", {"stress": 1.0, "vitality": 0.0, "calmness": 0.0})
        not_pleasant, _ = self.engine.score("not sunny")       # mirror-image words, so
        not_unpleasant, _ = self.engine.score("not gloomy")    # only the rule differs
        self.assertGreater(abs(not_pleasant["stress"] - 0.5),
                           abs(not_unpleasant["stress"] - 0.5))
        self.assertNotEqual(WeatherReporter().classify(self.engine.score("It is not bad")[0]),
                            "Sunny")

    def test_last_sentence_counts_more(self):
        ends_calm, _ = self.engine.score("I was anxious all morning. Now I feel calm.")
        ends_anxious, _ = self.engine.score("I feel calm now. I was anxious all morning.")
        self.assertLess(ends_calm["stress"], ends_anxious["stress"])

    def test_more_negators(self):
        good, _ = self.engine.score("It feels good")
        for text in ["It doesn't feel good", "It dont feel good", "Nothing good today"]:
            negated, _ = self.engine.score(text)
            self.assertLess(negated["vitality"], good["vitality"], text)
        stressed, _ = self.engine.score("I will be stressed")
        not_stressed, _ = self.engine.score("I won't be stressed")
        self.assertLess(not_stressed["stress"], stressed["stress"])

    def test_not_very_is_milder_than_not(self):
        happy, _ = self.engine.score("I am happy")
        not_happy, _ = self.engine.score("I am not happy")
        not_very, _ = self.engine.score("I am not very happy")
        self.assertLess(not_happy["vitality"], not_very["vitality"])
        self.assertLess(not_very["vitality"], happy["vitality"])
        self.assertNotEqual(WeatherReporter().classify(not_very), "Stormy")


class TestEntry(unittest.TestCase):
    def test_chronological_sort(self):
        a = JournalEntry(date(2026, 9, 2), "b")
        b = JournalEntry(date(2026, 9, 1), "a")
        self.assertEqual(sorted([a, b]), [b, a])

    def test_round_trip(self):
        e = JournalEntry(date(2026, 9, 1), "calm day",
                         {"stress": 0.1, "vitality": 0.5, "calmness": 0.9}, "Sunny")
        self.assertEqual(JournalEntry.from_dict(e.to_dict()).to_dict(), e.to_dict())

    def test_bad_schema(self):
        with self.assertRaises(SchemaMismatchError):
            JournalEntry.from_dict({"date": "2026-09-01", "text": "x"})

    def test_too_long(self):
        with self.assertRaises(InvalidEntryError):
            JournalEntry(date.today(), "x" * 5000)

    def test_intensity_sort(self):
        neutral = JournalEntry(date(2026, 9, 1), "a", dict(NEUTRAL))
        strong = JournalEntry(date(2026, 9, 2), "b",
                              {"stress": 1.0, "vitality": 0.0, "calmness": 0.0})
        self.assertEqual(sorted([neutral, strong], key=lambda e: -e.intensity),
                         [strong, neutral])

    def test_score_out_of_range(self):
        data = JournalEntry(date(2026, 9, 1), "x", dict(NEUTRAL)).to_dict()
        data["scores"]["stress"] = 1.5
        with self.assertRaises(SchemaMismatchError):
            JournalEntry.from_dict(data)

    def test_default_scores_are_neutral(self):
        e = JournalEntry(date(2026, 9, 1), "not scored yet")
        self.assertEqual(e.scores, NEUTRAL)
        self.assertEqual(e.intensity, 0)

    def test_text_must_be_string(self):
        data = JournalEntry(date(2026, 9, 1), "x").to_dict()
        data["text"] = 42
        with self.assertRaises(SchemaMismatchError):
            JournalEntry.from_dict(data)


class TestStorage(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.store = JournalStore(self.dir / "j.json", self.dir / "l.json")

    def test_missing_file_is_empty(self):
        self.assertEqual(self.store.load_entries(), [])

    def test_save_and_load(self):
        e = JournalEntry(date(2026, 9, 1), "hi")
        self.store.save_entries([e])
        self.assertEqual(self.store.load_entries(), [e])

    def test_corrupted_json(self):
        (self.dir / "j.json").write_text("[{broken")
        with self.assertRaises(CorruptedDataError):
            self.store.load_entries()

    def test_wrong_structure(self):
        (self.dir / "j.json").write_text(json.dumps({"not": "a list"}))
        with self.assertRaises(SchemaMismatchError):
            self.store.load_entries()

    def test_backup_kept(self):
        self.store.save_entries([JournalEntry(date(2026, 9, 1), "one")])
        self.store.save_entries([])
        self.assertTrue((self.dir / "j.bak").exists())

    def test_backup_is_previous_version(self):
        self.store.save_entries([JournalEntry(date(2026, 9, 1), "one")])
        self.store.save_entries([JournalEntry(date(2026, 9, 2), "two")])
        backup = json.loads((self.dir / "j.bak").read_text(encoding="utf-8"))
        self.assertEqual(backup[0]["text"], "one")
        self.assertEqual(self.store.load_entries()[0].text, "two")

    def test_unreadable_file_is_corrupted(self):
        (self.dir / "j.json").write_bytes(b"\xff\xfe\x00 not text")
        with self.assertRaises(CorruptedDataError):
            self.store.load_entries()

    def test_lexicon_round_trip(self):
        engine = SentimentEngine()
        engine.add_keyword("deadline", {"stress": 0.9, "vitality": 0.3, "calmness": 0.0})
        self.store.save_lexicon(engine.custom_words)
        restored = SentimentEngine(self.store.load_lexicon())
        self.assertEqual(restored.lexicon["deadline"], engine.lexicon["deadline"])

    def test_bad_lexicon_weight(self):
        (self.dir / "l.json").write_text(json.dumps(
            {"deadline": {"stress": "high", "vitality": 0.3, "calmness": 0.0}}))
        with self.assertRaises(SchemaMismatchError):
            self.store.load_lexicon()


class TestApp(unittest.TestCase):
    """The command-line app saves as it goes and never overwrites a damaged file."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.store = JournalStore(self.dir / "j.json", self.dir / "l.json")

    @staticmethod
    def run_quietly(func, *answers):
        with patch("builtins.input", side_effect=list(answers)), \
                redirect_stdout(io.StringIO()):
            return func()

    def test_entry_saved_immediately(self):
        app = self.run_quietly(lambda: VibeWeatherApp(self.store))
        self.run_quietly(app.add_entry, "2026-09-01", "calm day")
        self.assertEqual([e.text for e in self.store.load_entries()], ["calm day"])

    def test_delete_is_saved(self):
        self.store.save_entries([JournalEntry(date(2026, 9, 1), "private")])
        app = self.run_quietly(lambda: VibeWeatherApp(self.store))
        self.run_quietly(app.delete_entry, "1", "y")
        self.assertEqual(self.store.load_entries(), [])

    def test_delete_removes_the_chosen_twin(self):
        """Same date and text (so ==), but only the picked entry is deleted."""
        old = JournalEntry(date(2026, 9, 1), "deadline today", dict(NEUTRAL), "Foggy")
        new = JournalEntry(date(2026, 9, 1), "deadline today",
                           {"stress": 1.0, "vitality": 0.2, "calmness": 0.0}, "Stormy")
        self.store.save_entries([old, new])
        app = self.run_quietly(lambda: VibeWeatherApp(self.store))
        self.run_quietly(app.delete_entry, "2", "y")              # the Stormy one
        self.assertEqual([e.weather for e in self.store.load_entries()], ["Foggy"])

    def test_rescore_updates_old_entries(self):
        old = JournalEntry(date(2026, 9, 1), "I am very stressed", dict(NEUTRAL), "Unclassified")
        self.store.save_entries([old])
        app = self.run_quietly(lambda: VibeWeatherApp(self.store))
        self.run_quietly(app.rescore_entries, "y")
        saved = self.store.load_entries()[0]
        self.assertEqual(saved.weather, "Stormy")
        self.assertEqual(saved.text, "I am very stressed")
        self.assertEqual(rescore_all(app.entries, app.engine, app.reporter), 0)

    def test_damaged_file_not_overwritten(self):
        (self.dir / "j.json").write_text("[{broken")
        app = self.run_quietly(lambda: VibeWeatherApp(self.store))
        self.assertTrue(app.read_only)
        self.run_quietly(app.add_entry, "2026-09-01", "new entry")
        self.assertEqual((self.dir / "j.json").read_text(), "[{broken")

    def test_multiline_entry_listed_on_one_line(self):
        self.store.save_entries([JournalEntry(date(2026, 9, 1), "line one\nline two")])
        app = self.run_quietly(lambda: VibeWeatherApp(self.store))
        out = io.StringIO()
        with redirect_stdout(out):
            app.list_entries()
        self.assertIn("line one line two", out.getvalue())

    def test_bad_keyword_rejected_before_weights(self):
        app = self.run_quietly(lambda: VibeWeatherApp(self.store))
        with self.assertRaises(InvalidEntryError):    # no weight answers are given
            self.run_quietly(app.manage_keywords, "a", "very")   # a rule word, not allowed


class TestKeywords(unittest.TestCase):
    def test_add_and_remove(self):
        engine = SentimentEngine()
        engine.add_keyword("Deadline", {"stress": 0.9, "vitality": 0.3, "calmness": 0.0})
        self.assertIn("deadline", engine.lexicon)
        engine.remove_keyword("deadline")
        self.assertNotIn("deadline", engine.lexicon)

    def test_invalid_weight(self):
        with self.assertRaises(InvalidEntryError):
            SentimentEngine().add_keyword("x", {"stress": 2, "vitality": 0, "calmness": 0})

    def test_grammar_word_rejected(self):
        for word in ["very", "not", "but"]:
            with self.assertRaises(InvalidEntryError):
                SentimentEngine().add_keyword(
                    word, {"stress": 1, "vitality": 0, "calmness": 0})

    def test_phrase_keyword(self):
        engine = SentimentEngine()
        before, _ = engine.score("I am so fed up with this")
        engine.add_keyword("Fed Up", {"stress": 0.9, "vitality": 0.2, "calmness": 0.1})
        after, explanation = engine.score("I am so fed up with this")
        self.assertEqual(before, NEUTRAL)                     # not a mood word before
        self.assertGreater(after["stress"], 0.8)
        self.assertTrue(any("'so fed up'" in line for line in explanation))

    def test_phrase_works_with_rules(self):
        engine = SentimentEngine()
        engine.add_keyword("over the moon", {"stress": 0.0, "vitality": 1.0, "calmness": 0.7})
        happy, _ = engine.score("I am over the moon")
        not_happy, _ = engine.score("I am not over the moon")
        self.assertEqual(WeatherReporter().classify(happy), "Sunny")
        self.assertLess(not_happy["vitality"], happy["vitality"])

    def test_longer_phrase_wins(self):
        engine = SentimentEngine()
        engine.add_keyword("stressed out", {"stress": 0.6, "vitality": 0.3, "calmness": 0.2})
        _, explanation = engine.score("I am stressed out")
        self.assertTrue(explanation[0].startswith("'stressed out'"))   # not just "stressed"

    def test_phrase_saved_and_removed(self):
        engine = SentimentEngine()
        engine.add_keyword("fed up", {"stress": 0.9, "vitality": 0.2, "calmness": 0.1})
        with tempfile.TemporaryDirectory() as folder:
            store = JournalStore(Path(folder) / "j.json", Path(folder) / "l.json")
            store.save_lexicon(engine.custom_words)
            restored = SentimentEngine(store.load_lexicon())
        self.assertIn("fed_up", restored.lexicon)
        restored.remove_keyword("fed up")
        self.assertNotIn("fed_up", restored.lexicon)

    def test_bad_phrases_rejected(self):
        for word in ["fed up!", "one two three four five", "a bit", "12 days"]:
            with self.assertRaises(InvalidEntryError):
                SentimentEngine().add_keyword(
                    word, {"stress": 1, "vitality": 0, "calmness": 0})


class TestReporter(unittest.TestCase):
    def test_chart_shows_missing_days(self):
        e = JournalEntry(date(2026, 9, 29), "x",
                         {"stress": 0.8, "vitality": 0.2, "calmness": 0.1})
        chart = WeatherReporter().trend_chart([e], "stress", days=3, end=date(2026, 9, 29))
        self.assertIn("(no entry)", chart)
        self.assertIn("0.80", chart)

    def test_chart_averages_same_day(self):
        day = date(2026, 9, 29)
        entries = [JournalEntry(day, "a", {"stress": 0.2, "vitality": 0.5, "calmness": 0.5}),
                   JournalEntry(day, "b", {"stress": 0.6, "vitality": 0.5, "calmness": 0.5})]
        chart = WeatherReporter().trend_chart(entries, "stress", days=1, end=day)
        self.assertIn("0.40", chart)

    def test_summary_empty(self):
        self.assertIn("No journal entries", WeatherReporter().summary([]))

    def test_summary_compares_days(self):
        def entry(day, stress):
            return JournalEntry(date(2026, 9, day), "x",
                                {"stress": stress, "vitality": 0.5, "calmness": 0.5})
        summary = WeatherReporter().summary([entry(1, 0.0), entry(1, 1.0), entry(2, 0.6)])
        self.assertIn("+0.10", summary)                  # daily average 0.5 -> 0.6
        self.assertNotIn("2026-09-01 -> 2026-09-01", summary)

    def test_summary_is_not_a_diagnosis(self):
        e = JournalEntry(date(2026, 9, 1), "x", dict(NEUTRAL), "Foggy")
        self.assertIn("not a diagnosis", WeatherReporter().summary([e]))


if __name__ == "__main__":
    unittest.main()
