import re
from collections import Counter
from datetime import date, timedelta

from journal import DIMENSIONS, DISCLAIMER, InvalidEntryError, JournalEntry, is_unit_number

# ---------- word rule lists ----------
# Negation words: flip meaning, e.g. not happy
NEGATIVITIES= {"not", "no", "never", "hardly", "nothing", "without", "nor", "neither",
            "cannot", "don't", "doesn't", "didn't", "isn't", "aren't", "wasn't",
            "weren't", "can't", "couldn't", "won't", "wouldn't", "shouldn't",
            "haven't", "hasn't", "hadn't", "dont", "doesnt", "didnt", "isnt", "wasnt", "cant", "wont"}
# Intensifier words: make the next mood word stronger, e.g. very tired
INTENSIFIERS = {"very": 1.5, "extremely": 2.0, "really": 1.3, "so": 1.3, "super": 1.5,
                "much": 1.3}
# Softener words: make the next mood word weaker, e.g. slightly tired
DIMINISHERS = {"slightly": 0.5, "somewhat": 0.7, "a_bit": 0.6, "little": 0.6}
MODIFIERS = {**INTENSIFIERS, **DIMINISHERS}
# Contrast words
CONTRAST_WORDS = {"but", "however", "although", "though"}
# Concession words: although / though
CONCESSIVE_WORDS = {"although", "though"}
CLAUSE_BREAKS = {".", ",", "!", "?", ";"}      # Punctuation to split sentence parts
SENTENCE_ENDS = CLAUSE_BREAKS - {","}          # These marks mean a full sentence ends
GRAMMAR_WORDS = NEGATIVITIES | set(MODIFIERS) | CONTRAST_WORDS   # Cannot be mood keywords
MAX_PHRASE_WORDS = 4      # A custom phrase like "over the moon" can have up to 4 words

# ---------- scoring weights ----------
# "not" on positive words: flip by -0.5
NEGATE_PLEASANT = -0.5
# "not" on negative words: flip by -0.25 (not bad is only okay)
NEGATE_UNPLEASANT = -0.25
# Words after "but" count twice
CONTRAST_AFTER = 2.0
# Words inside "although" part count half
CONCESSION_INSIDE = 0.5
# Words in the last sentence count 1.5 times
END_WEIGHT = 1.5

# ---------- default mood word bank ----------
# Word -> scores for stress, vitality, calmness (0=low, 1=high)
DEFAULT_LEXICON = {
    "happy":     {"stress": 0.0, "vitality": 0.8, "calmness": 0.5},
    "excited":   {"stress": 0.1, "vitality": 0.9, "calmness": 0.2},
    "energetic": {"stress": 0.0, "vitality": 0.9, "calmness": 0.3},
    "calm":      {"stress": 0.0, "vitality": 0.3, "calmness": 0.9},
    "relaxed":   {"stress": 0.0, "vitality": 0.4, "calmness": 0.9},
    "peaceful":  {"stress": 0.0, "vitality": 0.3, "calmness": 1.0},
    "better":    {"stress": 0.0, "vitality": 0.6, "calmness": 0.6},
    "good":      {"stress": 0.0, "vitality": 0.6, "calmness": 0.5},
    "tired":     {"stress": 0.4, "vitality": 0.0, "calmness": 0.3},
    "exhausted": {"stress": 0.6, "vitality": 0.0, "calmness": 0.1},
    "sad":       {"stress": 0.4, "vitality": 0.1, "calmness": 0.2},
    "stressed":  {"stress": 0.9, "vitality": 0.2, "calmness": 0.0},
    "anxious":   {"stress": 0.9, "vitality": 0.3, "calmness": 0.0},
    "worried":   {"stress": 0.7, "vitality": 0.2, "calmness": 0.1},
    "angry":     {"stress": 0.8, "vitality": 0.5, "calmness": 0.0},
    "overwhelmed": {"stress": 1.0, "vitality": 0.2, "calmness": 0.0},
    "great":     {"stress": 0.0, "vitality": 0.9, "calmness": 0.6},
    "grateful":  {"stress": 0.0, "vitality": 0.6, "calmness": 0.8},
    "bad":       {"stress": 0.6, "vitality": 0.2, "calmness": 0.2},
    "upset":     {"stress": 0.7, "vitality": 0.3, "calmness": 0.1},
    "nervous":   {"stress": 0.7, "vitality": 0.4, "calmness": 0.1},
    "frustrated": {"stress": 0.8, "vitality": 0.4, "calmness": 0.0},
    "lonely":    {"stress": 0.5, "vitality": 0.2, "calmness": 0.3},
    "stress":    {"stress": 0.9, "vitality": 0.3, "calmness": 0.0},
}


# ---------- SentimentEngine: turn text into scores ----------
class SentimentEngine:
    """Calculate stress, vitality, calmness scores from journal text."""

    def __init__(self, custom_lexicon=None):
        # Copy default words, keep original unchanged
        self.lexicon = {w: dict(v) for w, v in DEFAULT_LEXICON.items()}
        self.custom_words = dict(custom_lexicon or {})
        self.lexicon.update(self.custom_words)      # User words override default

    @staticmethod
    def tokenize(text):
        """Split text into lowercase words and punctuation.
        "a bit" becomes "a_bit" so it works as one word.
        """
        text = text.lower().replace("’", "'")
        text = re.sub(r"\ba bit\b", "a_bit", text)
        return re.findall(r"[a-z_]+(?:'[a-z]+)?|[.,!?;]", text)

    @staticmethod
    def check_keyword(word):
        """Check if a new keyword or short phrase is valid.
        A phrase like "fed up" is saved as "fed_up", so it can be matched as one word.
        """
        parts = word.strip().lower().replace("_", " ").split()
        if len(parts) == 0 or len(parts) > MAX_PHRASE_WORDS:
            raise InvalidEntryError(f"Keyword must be 1 to {MAX_PHRASE_WORDS} English words")
        for part in parts:
            if not re.fullmatch(r"[a-z]+(?:'[a-z]+)?", part):
                raise InvalidEntryError("Keyword can only use English letters")
        word = "_".join(parts)
        if word in GRAMMAR_WORDS:                   # e.g. "very", "not" or "a bit"
            raise InvalidEntryError(f"'{word.replace('_', ' ')}' is a rule word, "
                                    "cannot be a keyword")
        return word

    def add_keyword(self, word, weights):
        """Add or update user's custom keyword. Weights must be 0 to 1."""
        word = self.check_keyword(word)
        if set(weights) != set(DIMENSIONS):
            raise InvalidEntryError(f"Weights need: {', '.join(DIMENSIONS)}")
        for dim, value in weights.items():
            if not is_unit_number(value):
                raise InvalidEntryError(f"{dim} weight must be between 0 and 1")
        clean = {d: float(weights[d]) for d in DIMENSIONS}
        self.custom_words[word] = clean
        self.lexicon[word] = clean

    def remove_keyword(self, word):
        """Delete one custom keyword or phrase. Default words stay."""
        word = "_".join(word.strip().lower().replace("_", " ").split())   # "fed up" -> "fed_up"
        if word not in self.custom_words:
            raise InvalidEntryError(f"'{word.replace('_', ' ')}' is not your custom keyword")
        del self.custom_words[word]
        if word in DEFAULT_LEXICON:
            self.lexicon[word] = dict(DEFAULT_LEXICON[word])
        else:
            del self.lexicon[word]

    def _join_phrases(self, tokens):
        """Join the words of a custom phrase into one token.
        e.g. ["i", "am", "fed", "up"] -> ["i", "am", "fed_up"]
        If two phrases could match at the same place, the longer one wins.
        """
        phrases = []
        for word in self.lexicon:
            if "_" in word:
                phrases.append(word.split("_"))     # "fed_up" -> ["fed", "up"]
        if len(phrases) == 0:                       # no phrases, nothing to join
            return tokens
        joined = []
        i = 0
        while i < len(tokens):
            best = []
            for parts in phrases:
                if tokens[i:i + len(parts)] == parts and len(parts) > len(best):
                    best = parts
            if len(best) > 0:                       # found a phrase starting here
                joined.append("_".join(best))
                i += len(best)
            else:
                joined.append(tokens[i])
                i += 1
        return joined

    def score(self, text):
        """Main function: get scores and explanation from text."""
        tokens = self._join_phrases(self.tokenize(text))
        last_start = self._last_sentence_start(tokens)
        totals = {d: 0.0 for d in DIMENSIONS}
        total_count = 0.0
        explanation = []
        contrast = concession = negator = None
        for i, token in enumerate(tokens):
            if token in CLAUSE_BREAKS:
                concession = negator = None
                if token in SENTENCE_ENDS:
                    contrast = None
            elif token in CONCESSIVE_WORDS:
                concession, negator = token, None
            elif token in CONTRAST_WORDS:
                contrast, negator = token, None
            elif token in NEGATIVITIES:
                negator = i
            elif token in self.lexicon:
                ending = 0 < last_start <= i
                level, count, line = self._keyword_effect(tokens, i, negator, contrast,
                                                          concession, ending)
                negator = None
                for d in DIMENSIONS:
                    totals[d] += count * level[d]
                total_count += count
                explanation.append(line)
        if total_count == 0:
            return ({d: 0.5 for d in DIMENSIONS},
                    ["No mood words found, all scores stay neutral (0.5)."])
        return {d: round(totals[d] / total_count, 3) for d in DIMENSIONS}, explanation

    @staticmethod
    def _last_sentence_start(tokens):
        """Find where the last sentence starts."""
        words = [k for k, t in enumerate(tokens) if t not in CLAUSE_BREAKS]
        if not words:
            return 0
        ends = [k for k in range(words[-1]) if tokens[k] in SENTENCE_ENDS]
        return ends[-1] + 1 if ends else 0

    def _keyword_effect(self, tokens, i, negator, contrast, concession, ending):
        """Calculate how one mood word affects scores.
        Return new level, weight count, explanation text.
        """
        start, multiplier = i, 1.0
        while start > 0 and tokens[start - 1] in MODIFIERS:
            start -= 1
            multiplier *= MODIFIERS[tokens[start]]
        weights = self.lexicon[tokens[i]]
        pleasant = (weights["vitality"] + weights["calmness"]) / 2 > weights["stress"]
        if negator is None:
            factor = multiplier
        else:
            factor = (NEGATE_PLEASANT if pleasant else NEGATE_UNPLEASANT) / multiplier
        level = {d: min(1.0, max(0.0, 0.5 + (weights[d] - 0.5) * factor))
                 for d in DIMENSIONS}
        count = ((CONTRAST_AFTER if contrast else 1.0)
                 * (CONCESSION_INSIDE if concession else 1.0)
                 * (END_WEIGHT if ending else 1.0))

        notes = []
        if negator is not None:
            notes.append(f"negated {'pleasant' if pleasant else 'unpleasant'} word, x{factor:.3g}")
            start = min(start, negator)
        elif multiplier != 1.0:
            notes.append(f"x{multiplier:.3g}")
        if contrast:
            notes.append(f"after '{contrast}', x{CONTRAST_AFTER:g}")
        if concession:
            notes.append(f"in '{concession}' clause, x{CONCESSION_INSIDE:g}")
        if ending:
            notes.append(f"last sentence, x{END_WEIGHT:g}")
        phrase = " ".join(tokens[start:i + 1]).replace("_", " ")
        values = ", ".join(f"{d} {level[d]:.2f}" for d in DIMENSIONS)
        line = f"'{phrase}' -> {values}" + (f" ({'; '.join(notes)})" if notes else "")
        return level, count, line


# ---------- WeatherReporter: turn scores into weather ----------
class WeatherReporter:
    """Map three mood scores to a weather type, make charts and summaries."""

    WEATHER_ICONS = {
        "Sunny": "☀", "Partly Cloudy": "⛅", "Overcast": "☁",
        "Rainy": "🌧", "Stormy": "⛈", "Foggy": "🌫", "Unclassified": "?",
    }
    BAR_WIDTH = 30          # Width of text bar chart

    # Check rules top to bottom. First match wins.
    # s = stress, v = vitality, c = calmness
    RULES = (
        ("Foggy", "All scores near neutral, no clear mood",
         lambda s, v, c: max(abs(s - 0.5), abs(v - 0.5), abs(c - 0.5)) < 0.15),
        ("Stormy", "High stress: stress >= 0.8",
         lambda s, v, c: s >= 0.8),
        ("Rainy", "Low vitality and low calmness",
         lambda s, v, c: v < 0.3 and c < 0.3),
        ("Sunny", "Low stress, high vitality or calmness",
         lambda s, v, c: s < 0.3 and (v >= 0.6 or c >= 0.8)),
        ("Overcast", "High stress OR low vitality & calmness",
         lambda s, v, c: s >= 0.6 or (v < 0.4 and c < 0.5)),
        ("Partly Cloudy", "Mixed mood, no stronger rule matched",
         lambda s, v, c: True),
    )

    def classify(self, scores):
        """Only return weather name."""
        return self.explain_weather(scores)[0]

    def explain_weather(self, scores):
        """Return weather name + rule description."""
        s, v, c = (scores[d] for d in DIMENSIONS)
        for weather, rule, matches in self.RULES:
            if matches(s, v, c):
                return weather, rule
        return "Unclassified", "no rule matched"

    def trend_chart(self, entries, dimension, days=7, end: date | None = None):
        """Make a text bar chart for one mood over recent days."""
        if dimension not in DIMENSIONS:
            raise InvalidEntryError(f"Dimension must be one of {DIMENSIONS}")
        if end is None:
            end = date.today()
        by_day = {}
        for e in entries:
            by_day.setdefault(e.date, []).append(e.scores[dimension])

        lines = [f"{dimension.capitalize()} - last {days} days",
                 " " * 12 + "0" + " " * (self.BAR_WIDTH - 2) + "1"]
        for i in range(days - 1, -1, -1):
            day = end - timedelta(days=i)
            label = day.strftime("%a %d %b")
            if day not in by_day:
                lines.append(f"{label:<11} (no entry)")
                continue
            value = sum(by_day[day]) / len(by_day[day])
            bar = "█" * round(value * self.BAR_WIDTH)
            lines.append(f"{label:<11} {bar:<{self.BAR_WIDTH}} {value:.2f}")
        return "\n".join(lines)

    def summary(self, entries: list[JournalEntry]):
        """Calculate averages, most common weather and biggest stress change."""
        if not entries:
            return "No journal entries yet - write your first one!"
        entries = sorted(entries)
        n = len(entries)
        avg = {d: sum(e.scores[d] for e in entries) / n for d in DIMENSIONS}
        weather, count = Counter(e.weather for e in entries).most_common(1)[0]
        stress_by_day = {}
        for e in entries:
            stress_by_day.setdefault(e.date, []).append(e.scores["stress"])
        daily = [(day, sum(v) / len(v)) for day, v in stress_by_day.items()]

        days = len(daily)
        lines = [f"Reflection summary ({n} {'entry' if n == 1 else 'entries'} on "
                 f"{days} {'day' if days == 1 else 'days'}, "
                 f"{entries[0].date} to {entries[-1].date})"]
        for d in DIMENSIONS:
            lines.append(f"  Average {d:<9}: {avg[d]:.2f}")
        lines.append(f"  Most common weather: {weather} "
                     f"{self.WEATHER_ICONS.get(weather, '?')} ({count}/{n} entries)")

        if len(daily) >= 2:
            (day1, s1), (day2, s2) = max(zip(daily, daily[1:]),
                                        key=lambda p: abs(p[1][1] - p[0][1]))
            lines.append(f"  Biggest stress change: {s2 - s1:+.2f} "
                         f"({day1} -> {day2}, daily averages)")
        most_intense = max(entries, key=lambda e: e.intensity)
        lines.append(f"  Most intense day: {most_intense.date} ({most_intense.weather})")
        lines.append("")
        lines.append(DISCLAIMER)
        return "\n".join(lines)


def rescore_all(entries, engine, reporter):
    """Re-calculate scores and weather for all old entries.
    Return how many entries changed.
    """
    changed = 0
    for entry in entries:
        scores, _ = engine.score(entry.text)
        weather = reporter.classify(scores)
        if scores != entry.scores or weather != entry.weather:
            entry.scores, entry.weather = scores, weather
            changed += 1
    return changed


def by_intensity(entry):
    """Used with sorted() to put the strongest mood first."""
    return -entry.intensity


def most_common_weather(entries):
    """Count each weather and return the one that comes up the most (first one wins a tie)."""
    counts = {}
    for entry in entries:
        if entry.weather in counts:
            counts[entry.weather] += 1
        else:
            counts[entry.weather] = 1
    best, best_count = "", 0
    for weather in counts:
        if counts[weather] > best_count:
            best, best_count = weather, counts[weather]
    return best


def average_score(entries, dimension):
    """The average score of one mood over a list of entries."""
    total = 0
    for entry in entries:
        total += entry.scores[dimension]
    return total / len(entries)
