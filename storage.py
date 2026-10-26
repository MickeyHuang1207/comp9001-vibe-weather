import json
import shutil
from pathlib import Path

from analysis import SentimentEngine
from journal import CorruptedDataError, InvalidEntryError, JournalEntry, SchemaMismatchError

# Data folder sits beside this code file
DATA_DIR = Path(__file__).parent / "data"
JOURNAL_FILE = DATA_DIR / "journal.json"
LEXICON_FILE = DATA_DIR / "custom_lexicon.json"


class JournalStore:
    """Load and save diary entries and custom keywords safely."""

    def __init__(self, journal_file=JOURNAL_FILE, lexicon_file=LEXICON_FILE):
        self.journal_file = Path(journal_file)
        self.lexicon_file = Path(lexicon_file)

    @staticmethod
    def _read_json(path, default):
        """Read JSON file. Return default value if file does not exist."""
        if not path.exists():
            return default
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as err:          # File content is broken
            raise CorruptedDataError(f"{path.name} is corrupted (line {err.lineno})")
        except UnicodeDecodeError:                   # Not a readable text file
            raise CorruptedDataError(f"{path.name} is not a readable text file")
        except OSError as err:                       # No permission to read file
            raise CorruptedDataError(f"Cannot read {path.name}: {err}")

    @staticmethod
    def _write_json(path, data):
        """Save data into JSON safely.
        Write to temp file first, make backup, then replace original file.
        This prevents data loss if the program crashes.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        if path.exists():
            shutil.copy2(path, path.with_suffix(".bak"))      # Make backup
        tmp.replace(path)

    def load_entries(self):
        """Load all diary entries from journal.json."""
        data = self._read_json(self.journal_file, [])
        if not isinstance(data, list):
            raise SchemaMismatchError("journal.json must contain a list of entries")
        return [JournalEntry.from_dict(item) for item in data]

    def save_entries(self, entries: list[JournalEntry]):
        """Save entries to journal.json, sorted by date (oldest first)."""
        self._write_json(self.journal_file, [e.to_dict() for e in sorted(entries)])

    def load_lexicon(self):
        """Load user custom keywords and validate each keyword."""
        data = self._read_json(self.lexicon_file, {})
        if not isinstance(data, dict):
            raise SchemaMismatchError("custom_lexicon.json must contain an object")
        checker = SentimentEngine()
        for word, weights in data.items():
            if not isinstance(weights, dict):
                raise SchemaMismatchError(f"Bad weights for keyword '{word}'")
            try:
                checker.add_keyword(word, weights)     # Use the same check rule
            except InvalidEntryError as err:
                raise SchemaMismatchError(f"Bad keyword '{word}': {err}")
        return checker.custom_words

    def save_lexicon(self, custom_words):
        """Save user custom keywords into custom_lexicon.json."""
        self._write_json(self.lexicon_file, custom_words)