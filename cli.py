from datetime import date, datetime

from analysis import SentimentEngine, WeatherReporter, rescore_all
from journal import (DATE_FORMAT, DIMENSIONS, DISCLAIMER, STALE_NOTE, InvalidEntryError,
                     JournalEntry, VibeWeatherError)
from storage import JournalStore


def ask_date(prompt):
    """Ask the user for a date. Pressing Enter without typing means today."""
    raw = input(f"{prompt} (YYYY-MM-DD, blank = today): ").strip()
    if not raw:
        return date.today()
    try:
        return datetime.strptime(raw, DATE_FORMAT).date()
    except ValueError:
        raise InvalidEntryError("Date must look like 2026-09-29")


def ask_float(prompt):
    """Ask the user for a number (used for keyword weights)."""
    try:
        return float(input(prompt).strip())
    except ValueError:
        raise InvalidEntryError("Please enter a number between 0 and 1")


class VibeWeatherApp:
    """The text menu: the user types a number and the matching method runs."""

    MENU = """
===== VibeWeather =====
1. Write a journal entry
2. View entries
3. Delete an entry
4. Mood trend chart
5. Reflection summary
6. Read an entry in full & explain its score
7. Manage custom keywords
8. Re-score all entries
0. Quit (changes are saved as you go)"""

    def __init__(self, store=None):
        self.store = store or JournalStore()
        self.read_only = False
        self.entries: list[JournalEntry] = self._safe_load(self.store.load_entries, [])
        self.engine = SentimentEngine(self._safe_load(self.store.load_lexicon, {}))
        self.reporter = WeatherReporter()

    def _safe_load(self, loader, default):
        """Load a file. If it is broken, warn the user and stop saving (read-only mode)."""
        try:
            return loader()
        except VibeWeatherError as err:
            print(f"Warning: {err}")
            print("Starting with empty data in read-only mode: nothing will be saved, "
                  "so your file is NOT overwritten. Fix it or restore the .bak copy, "
                  "then restart.")
            self.read_only = True
            return default

    def save(self):
        """Save after every change, so closing the terminal never loses entries."""
        if self.read_only:
            print("(Read-only mode - not saved, to avoid overwriting a damaged file.)")
            return
        try:
            self.store.save_entries(self.entries)
            self.store.save_lexicon(self.engine.custom_words)
        except OSError as err:
            print(f"Error: could not save - {err}")

    def add_entry(self):
        """Ask for a date and some text, score it and save it."""
        entry_date = ask_date("Date")
        print("Write your entry (one line):")
        text = input("> ")
        scores, _ = self.engine.score(text)
        entry = JournalEntry(entry_date, text, scores, self.reporter.classify(scores))
        self.entries.append(entry)
        icon = self.reporter.WEATHER_ICONS.get(entry.weather, "?")
        print(f"Vibe for {entry.date}: {entry.weather} {icon}")
        if not entry.text:
            print("(Empty entry - scores are neutral.)")
        self.save()

    def list_entries(self, order="date"):
        """Print a numbered list of the entries, by date or by intensity."""
        if order == "intensity":
            ordered = sorted(self.entries, key=lambda entry: -entry.intensity)
        else:
            ordered = sorted(self.entries)
        for i, e in enumerate(ordered, 1):
            flat = " ".join(e.text.split())      # put a multi-line entry on one line
            preview = (flat[:40] + "...") if len(flat) > 40 else flat
            print(f"{i:>3}. {e.date}  {e.weather:<13} {preview}")
        return ordered

    def view_entries(self):
        """Ask how to sort, then show the list."""
        if not self.entries:
            print("No entries yet.")
            return
        order = input("Sort by date or intensity? (d/i) ").strip().lower()
        self.list_entries("intensity" if order == "i" else "date")

    def pick_entry(self):
        """Show the list and let the user pick one entry by its number."""
        if not self.entries:
            print("No entries yet.")
            return None
        ordered = self.list_entries()
        try:
            idx = int(input("Entry number: ")) - 1
            if not 0 <= idx < len(ordered):
                raise ValueError
        except ValueError:
            raise InvalidEntryError("Not a valid entry number")
        return ordered[idx]

    def delete_entry(self):
        """Delete the entry the user picks (after asking y/n)."""
        entry = self.pick_entry()
        if entry and input(f"Delete entry from {entry.date}? (y/n) ").strip().lower() == "y":
            # "is not" makes sure only this exact entry is removed, even if
            # another entry has the same date and text
            self.entries = [e for e in self.entries if e is not entry]
            print("Deleted.")
            self.save()

    def show_entry(self):
        """Show one entry in full, with the words that gave it its score."""
        entry = self.pick_entry()
        if entry:
            scores, explanation = self.engine.score(entry.text)
            weather, rule = self.reporter.explain_weather(entry.scores)
            print(f"\n{entry.date}: {entry.weather}")
            print(f'  "{entry.text}"' if entry.text else "  (empty entry)")
            for d in DIMENSIONS:
                print(f"  {d:<9}: {entry.scores[d]:.2f}")
            for line in explanation:
                print("  -", line)
            print(f"  - {weather} because {rule}")
            if scores != entry.scores or weather != entry.weather:    # scored with old rules
                print("  " + STALE_NOTE)

    def manage_keywords(self):
        """Add, update or remove the user's own keywords."""
        names = []
        for word in self.engine.custom_words:
            names.append(word.replace("_", " "))      # show "fed_up" as "fed up"
        names.sort()
        print("Your keywords:", ", ".join(names) or "(none)")
        choice = input("Add/update (a), remove (r), or Enter to go back: ").strip().lower()
        if choice == "a":
            word = self.engine.check_keyword(input("Word or phrase: "))   # check it first
            weights = {d: ask_float(f"  {d} weight (0-1): ") for d in DIMENSIONS}
            self.engine.add_keyword(word, weights)
            print("Keyword added.")
            self.save()
        elif choice == "r":
            self.engine.remove_keyword(input("Word to remove: "))
            print("Keyword removed.")
            self.save()

    def rescore_entries(self):
        """Score every entry again with the current keywords."""
        if not self.entries:
            print("No entries yet.")
            return
        if input(f"Re-score all {len(self.entries)} entries with the current "
                 "keywords? (y/n) ").strip().lower() != "y":
            return
        changed = rescore_all(self.entries, self.engine, self.reporter)
        print(f"Re-scored: {changed} of {len(self.entries)} entries changed.")
        self.save()

    def run(self):
        """Show the menu again and again until the user types 0."""
        print(DISCLAIMER)
        actions = {                      # menu number -> what to do
            "1": self.add_entry,
            "2": self.view_entries,
            "3": self.delete_entry,
            "4": lambda: print(self.reporter.trend_chart(
                self.entries, input(f"Dimension {DIMENSIONS}: ").strip().lower())),
            "5": lambda: print(self.reporter.summary(self.entries)),
            "6": self.show_entry,
            "7": self.manage_keywords,
            "8": self.rescore_entries,
        }
        while True:
            print(self.MENU)
            try:
                choice = input("Choose: ").strip()
                if choice == "0":
                    break
                action = actions.get(choice)
                if action is None:
                    print("Please choose a number from the menu.")
                    continue
                action()
            except VibeWeatherError as err:          # show the problem, keep the menu going
                print(f"Error: {err}")
            except (KeyboardInterrupt, EOFError):     # Ctrl+C / Ctrl+D quits safely
                print()
                break
        print("Goodbye - take care!")


if __name__ == "__main__":
    VibeWeatherApp().run()
