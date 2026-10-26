from datetime import date, datetime

# Three mood dimensions for every journal entry
DIMENSIONS = ("stress", "vitality", "calmness")
DATE_FORMAT = "%Y-%m-%d"          # Date format
MAX_ENTRY_LENGTH = 2000           # Max characters for one diary entry

DISCLAIMER = ("Note: VibeWeather is a tool for personal reflection only. "
              "It is not a diagnosis of your mental health.")
# Show this note if entry was scored with old rules
STALE_NOTE = ("(Scored with older keywords or an older version of the algorithm, "
              "so this explanation may not match the stored score.)")


def is_unit_number(value):
    """Check if input is a number between 0 and 1."""
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and 0.0 <= value <= 1.0)


# ---------- Custom error classes ----------
# All errors inherit from VibeWeatherError, so we can catch them together

class VibeWeatherError(Exception):
    """Base error class for this program."""


class InvalidEntryError(VibeWeatherError):
    """Triggered when user input is invalid."""


class CorruptedDataError(VibeWeatherError):
    """Triggered when the saved JSON file is broken."""


class SchemaMismatchError(VibeWeatherError):
    """Triggered when JSON file exists but data format is wrong."""


# ---------- Journal entry class ----------

class JournalEntry:
    """One single diary entry: date, text, mood scores and weather label."""

    def __init__(self, entry_date, text, scores=None, weather=None):
        if not isinstance(entry_date, date):
            raise InvalidEntryError("entry_date must be a datetime.date")
        text = text.strip() if isinstance(text, str) else ""
        if len(text) > MAX_ENTRY_LENGTH:
            raise InvalidEntryError(f"Entry is longer than {MAX_ENTRY_LENGTH} characters")
        self.date = entry_date
        self.text = text          # Empty entry is allowed
        self.scores = scores or {d: 0.5 for d in DIMENSIONS}     # Default neutral score 0.5
        self.weather = weather or "Unclassified"

    @property
    def intensity(self):
        """Measure how strong the mood is, distance from neutral 0.5."""
        return sum(abs(self.scores[d] - 0.5) for d in DIMENSIONS)

    def __lt__(self, other: object) -> bool:
        """Sort entries by date (oldest first)."""
        if not isinstance(other, JournalEntry):
            return NotImplemented
        return self.date < other.date

    def __eq__(self, other: object) -> bool:
        """Two entries are equal if date and text match."""
        if not isinstance(other, JournalEntry):
            return NotImplemented
        return self.date == other.date and self.text == other.text

    def __repr__(self):
        """Short preview when printing this entry."""
        return f"JournalEntry({self.date.isoformat()}, {self.weather!r})"

    def to_dict(self):
        """Convert entry to dict, ready to save into JSON file."""
        return {"date": self.date.strftime(DATE_FORMAT), "text": self.text,
                "scores": self.scores, "weather": self.weather}

    @classmethod
    def from_dict(cls, data):
        """Load an entry from saved JSON data and check its validity."""
        if not isinstance(data, dict):
            raise SchemaMismatchError("Each entry must be a JSON object")
        for key in ("date", "text", "scores", "weather"):
            if key not in data:
                raise SchemaMismatchError(f"Entry is missing field '{key}'")
        try:
            entry_date = datetime.strptime(data["date"], DATE_FORMAT).date()
        except (TypeError, ValueError):
            raise SchemaMismatchError(f"Bad date: {data['date']!r}")
        if not isinstance(data["text"], str) or not isinstance(data["weather"], str):
            raise SchemaMismatchError(f"Bad text or weather for {data['date']}")
        scores = data["scores"]
        # Scores must have exactly stress, vitality, calmness, each between 0 and 1
        if (not isinstance(scores, dict)
                or set(scores) != set(DIMENSIONS)
                or not all(is_unit_number(v) for v in scores.values())):
            raise SchemaMismatchError(f"Bad scores for {data['date']}")
        return cls(entry_date, data["text"],
                   {d: float(scores[d]) for d in DIMENSIONS}, data["weather"])
