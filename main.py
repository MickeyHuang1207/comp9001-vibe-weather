"""Run with Python 3.10+ and Tkinter. All the other code files are beside this file."""
import math
import os
import random
import sys
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import messagebox, simpledialog, ttk

from analysis import (SentimentEngine, WeatherReporter, average_score, by_intensity,
                      most_common_weather, rescore_all)
from drawing import (ACCENT, BANNER, BG, BORDER, CARD, CLOUD_COLOURS, DIM_COLOURS, FACES,
                     INK, MUTED, PILL, SOFT, TAG_COLOURS, banner_colour, blend, draw_cloud,
                     draw_face, draw_sparkle, known_weather, pick_font_family,
                     rounded_rect, sticker_text, tag_colour)
from journal import DATE_FORMAT, DIMENSIONS, STALE_NOTE, JournalEntry, VibeWeatherError
from storage import JournalStore
from widgets import Card, FlatButton, Segmented, WeatherScene

TAGLINES = {
    # Simple message under the banner title
    "Sunny": "Bright and full of energy — enjoy the moment!",
    "Partly Cloudy": "Mostly okay, with small worries drifting past.",
    "Overcast": "A quiet day when your energy feels low.",
    "Rainy": "Things feel heavy; be kind to yourself.",
    "Stormy": "Pressure is high. Take a slow breath.",
    "Foggy": "Your feelings feel a little unclear right now.",
    "Unclassified": "Write down your thoughts to see your mood weather."
}

DISCLAIMER_SHORT = (
    "For your own reflection only. "
    "This is not a mental health evaluation."
)

# Sample journal entries for the demo button
DEMO_WEEK = [
    "I feel happy and energised after a good night’s sleep.",
    "A little nervous about the quiz, but mostly calm.",
    "I feel stressed and worried about my assignment.",
    "I’m tired and sad — I did not sleep well.",
    "I felt stressed this morning, but I feel much better now.",
    "A relaxing, peaceful day at the beach.",
    "I’m really excited! My project finally works."
]

# Optional banner picture: put a file called background.png next to this file
BACKGROUND_IMAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "background.png")

PLACEHOLDER = "How did your day go? Write a few lines about it…"


#  the main window
class VibeWeatherGUI:
    """The main VibeWeather window."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("VibeWeather")
        self.root.geometry("1200x840")
        self.root.minsize(1060, 780)
        self.root.configure(bg=BG)

        # the fonts used in the window: name -> (font, size, maybe "bold")
        family = pick_font_family(self.root)
        self.f = {
            "title": (family, 24, "bold"), "sub": (family, 11),
            "h": (family, 13, "bold"), "big": (family, 24, "bold"),
            "body": (family, 11), "small": (family, 10), "tiny": (family, 9),
            "bold": (family, 11, "bold"), "stat": (family, 18, "bold"),
            "input": (family, 12),
        }

        # load the saved data (if a file is broken we go into read-only mode)
        self.store = JournalStore()
        self.read_only = False
        self.entries: list[JournalEntry] = self.safe_load(self.store.load_entries, [])
        self.engine = SentimentEngine(self.safe_load(self.store.load_lexicon, {}))
        self.reporter = WeatherReporter()
        self.chart_days = tk.IntVar(value=7)           # 7, 14 or 30 days in the chart
        self.sort_mode = tk.StringVar(value="date")    # "date" or "intensity"
        self.current_weather = "Unclassified"
        self.current_scores = None
        self.rows: list[JournalEntry] = []            # the entries in the same order as the table
        self.banner_image = None
        self.banner_image_loaded = False

        # the widgets below are made by build() and its helper methods
        self.banner: tk.Canvas
        self.banner_button_frame: tk.Frame
        self.banner_buttons: int          # the id of the button bar on the banner canvas
        self.date_var: tk.StringVar
        self.text: tk.Text
        self.counter: tk.Label
        self.scene: WeatherScene
        self.weather_tag: tk.Label
        self.weather_label: tk.Label
        self.date_label: tk.Label
        self.bars: tk.Canvas
        self.explain: tk.Text
        self.tree: ttk.Treeview
        self.stats: tk.Frame
        self.stat_labels: dict
        self.chart: tk.Canvas

        self.style()
        self.build()
        self.refresh()
        self.show_latest()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)    # save when the window closes

    def run(self):
        """Start the window. It stays open until the user closes it."""
        self.root.mainloop()

    # ---------- loading and saving ----------
    def safe_load(self, loader, default):
        """Load a file. If it is broken, warn the user and switch to read-only mode."""
        try:
            return loader()
        except VibeWeatherError as err:
            messagebox.showwarning(
                "Data problem", f"{err}\n\nStarting with empty data in read-only mode: "
                                "nothing will be saved, so your file is NOT overwritten. "
                                "Fix it or restore the .bak copy, then restart.")
            self.read_only = True
            return default

    def save(self):
        """Save the entries and keywords (does nothing in read-only mode)."""
        if self.read_only:
            return
        try:
            self.store.save_entries(self.entries)
            self.store.save_lexicon(self.engine.custom_words)
        except OSError as err:
            messagebox.showerror("Save failed", str(err))

    def on_close(self):
        """Save, then close the window."""
        self.save()
        self.root.destroy()

    # ---------- building the window ----------
    def style(self):
        """Colors for the history table and its scroll bar."""
        s = ttk.Style(self.root)
        s.theme_use("clam")                    # this theme lets me change the colors
        s.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=INK,
                    rowheight=30, borderwidth=0, font=self.f["body"])
        s.configure("Treeview.Heading", background=CARD, foreground=MUTED,
                    borderwidth=0, relief="flat", font=self.f["small"])
        s.map("Treeview", background=[("selected", "#EDE4FF")],
              foreground=[("selected", INK)])
        s.map("Treeview.Heading", background=[("active", CARD)])
        # noinspection PyTypeChecker
        s.layout("Treeview", [("Treeview.treearea", {"sticky": "news"})])  # no table border
        s.configure("Vertical.TScrollbar", background=SOFT, troughcolor=CARD,
                    borderwidth=0, arrowsize=0, relief="flat")

    def label(self, parent, text="", font="body", fg=INK):
        """Make a label with one of my fonts and the same background as its parent."""
        return tk.Label(parent, text=text, font=self.f[font], fg=fg, bg=parent["bg"])

    @staticmethod
    def new_card(parent, row, column):
        """Make a Card, put it in the grid, and return the frame for its widgets."""
        card = Card(parent)
        card.canvas.grid(row=row, column=column, sticky="nsew", padx=8, pady=8)
        return card.body

    def build(self):
        """Build the banner, the 4 cards and the footer."""
        # the banner at the top (its colors and face follow the weather)
        self.banner = tk.Canvas(self.root, height=100, highlightthickness=0, bg=BG)
        self.banner.pack(fill="x", padx=16, pady=(16, 0))
        self.banner.bind("<Configure>", self.on_banner_resize)
        button_bar = self.banner_button_frame = tk.Frame(
            self.banner, bg=blend(BANNER[1], BANNER[2], 0.75))
        self.banner_buttons = self.banner.create_window(0, 0, window=button_bar, anchor="e")
        FlatButton(button_bar, "Load demo week", self.load_demo, self.f["small"],
                   small=True, night=True).label.pack(side="left", padx=(0, 6))
        FlatButton(button_bar, "Keywords", self.manage_keywords, self.f["small"],
                   small=True, night=True).label.pack(side="left", padx=(0, 6))
        FlatButton(button_bar, "Re-score all", self.rescore_entries, self.f["small"],
                   small=True, night=True).label.pack(side="left")

        # the 4 cards sit in a grid: 2 columns (5:7 wide) and 2 rows
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=8, pady=8)
        body.columnconfigure(0, weight=5, uniform="c")
        body.columnconfigure(1, weight=7, uniform="c")
        body.rowconfigure(0, weight=1, minsize=330)
        body.rowconfigure(1, weight=1, minsize=330)

        self.build_writer(self.new_card(body, 0, 0))
        self.build_today(self.new_card(body, 0, 1))
        self.build_history(self.new_card(body, 1, 0))
        self.build_trend(self.new_card(body, 1, 1))

        # the footer: a warning in read-only mode, then the disclaimer
        footer = tk.Frame(self.root, bg=BG)
        footer.pack(pady=(0, 10))
        if self.read_only:
            self.label(footer, "Read-only mode: a data file could not be read, so "
                               "nothing is saved.   ", "tiny",
                       DIM_COLOURS["stress"]).pack(side="left")
        self.label(footer, DISCLAIMER_SHORT, "tiny", MUTED).pack(side="left")

    def build_writer(self, p):
        """Top-left card: the date box, the text box and the save button."""
        self.label(p, "Today's journal", "h").pack(anchor="w")
        row = tk.Frame(p, bg=CARD)
        row.pack(fill="x", pady=(10, 8))
        self.label(row, "Date", "small", MUTED).pack(side="left")
        self.date_var = tk.StringVar(value=date.today().strftime(DATE_FORMAT))
        tk.Entry(row, textvariable=self.date_var, width=11, font=self.f["body"],
                 relief="flat", bg=SOFT, fg=INK, insertbackground=INK,
                 highlightthickness=1, highlightbackground=SOFT,
                 highlightcolor=ACCENT).pack(side="left", padx=8, ipady=4)
        FlatButton(row, "Today", self.set_today,
                   self.f["tiny"], small=True).label.pack(side="left")

        self.text = tk.Text(p, height=5, wrap="word", font=self.f["input"], relief="flat",
                            bg=SOFT, fg=INK, insertbackground=INK, padx=12, pady=10,
                            highlightthickness=1, highlightbackground=SOFT,
                            highlightcolor=ACCENT)
        self.text.pack(fill="both", expand=True)
        self.placeholder(True)                        # show the gray hint text
        self.text.bind("<FocusIn>", self.on_text_focus_in)
        self.text.bind("<FocusOut>", self.on_text_focus_out)
        self.text.bind("<KeyRelease>", self.on_key_release)

        bottom = tk.Frame(p, bg=CARD)
        bottom.pack(fill="x", pady=(10, 0))
        self.counter = self.label(bottom, "0 characters", "tiny", MUTED)
        self.counter.pack(side="left")
        FlatButton(bottom, "Analyse & save", self.add_entry, self.f["bold"],
                   primary=True).label.pack(side="right")

    def build_today(self, p):
        """Top-right card: the weather animation, the scores and "Why this score?"."""
        p.columnconfigure(1, weight=1)
        p.rowconfigure(0, weight=1)
        self.scene = WeatherScene(p)
        self.scene.canvas.grid(row=0, column=0, sticky="nw")
        info = tk.Frame(p, bg=CARD, padx=18)
        info.grid(row=0, column=1, sticky="nsew")

        self.weather_tag = tk.Label(info, text=" TODAY ", font=self.f["tiny"],
                                    fg="white", bg=PILL)
        self.weather_tag.pack(anchor="w")
        self.weather_label = self.label(info, "No entry yet", "big")
        self.weather_label.pack(anchor="w", pady=(4, 0))
        self.date_label = self.label(info, "", "small", MUTED)
        self.date_label.pack(anchor="w")
        self.bars = tk.Canvas(info, width=200, height=92, bg=CARD, highlightthickness=0)
        self.bars.pack(fill="x", pady=(12, 0))
        self.bars.bind("<Configure>", self.redraw_bars)

        self.label(p, "Why this score?", "bold").grid(row=1, column=0, columnspan=2,
                                                       sticky="w", pady=(12, 4))
        self.explain = tk.Text(p, height=2, wrap="word", font=self.f["small"],
                               relief="flat", bg=SOFT, fg=INK, padx=10, pady=6,
                               highlightthickness=0)
        self.explain.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self.explain.configure(state="disabled")       # read-only for the user

    def build_history(self, p):
        """Bottom-left card: the history table with sorting, View and Delete."""
        top = tk.Frame(p, bg=CARD)
        top.pack(fill="x")
        self.label(top, "History", "h").pack(side="left")
        FlatButton(top, "Delete", self.delete_entry, self.f["tiny"],
                   small=True).label.pack(side="right")
        FlatButton(top, "View", self.view_entry, self.f["tiny"],
                   small=True).label.pack(side="right", padx=(0, 6))
        Segmented(top, [("Newest", "date"), ("Intensity", "intensity")],
                  self.sort_mode, self.refresh, self.f["tiny"]).frame.pack(side="right", padx=8)

        frame = tk.Frame(p, bg=CARD)
        frame.pack(fill="both", expand=True, pady=(10, 0))
        self.tree = ttk.Treeview(frame, columns=("date", "weather", "text"),
                                 show="headings", selectmode="browse")
        for col, title, width in (("date", "DATE", 96), ("weather", "WEATHER", 120),
                                  ("text", "ENTRY", 240)):
            self.tree.heading(col, text=title, anchor="w")
            self.tree.column(col, width=width, anchor="w", stretch=(col == "text"))
        for name in TAG_COLOURS:                       # each weather gets its own text color
            self.tree.tag_configure(name, foreground=TAG_COLOURS[name])
        self.tree.tag_configure("odd", background="#FBF8FF")
        # connect the scroll bar and the table to each other
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", self.on_open)
        self.tree.bind("<Return>", self.on_open)

    def build_trend(self, p):
        """Bottom-right card: the 7/14/30 day switch, 4 number tiles and the chart."""
        top = tk.Frame(p, bg=CARD)
        top.pack(fill="x")
        self.label(top, "Mood trend", "h").pack(side="left")
        Segmented(top, [("7d", 7), ("14d", 14), ("30d", 30)], self.chart_days,
                  self.refresh, self.f["tiny"]).frame.pack(side="right")

        self.stats = tk.Frame(p, bg=CARD)
        self.stats.pack(fill="x", pady=(10, 4))
        self.stat_labels = {}
        keys = ("stress", "vitality", "calmness", "weather")
        for i in range(len(keys)):
            key = keys[i]
            tile = tk.Frame(self.stats, bg=SOFT, padx=12, pady=8)
            tile.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            self.stats.columnconfigure(i, weight=1, uniform="s")
            title = "Most common" if key == "weather" else f"Avg {key}"
            tk.Label(tile, text=title.upper(), font=self.f["tiny"], fg=MUTED,
                     bg=SOFT).pack(anchor="w")
            value = tk.Label(tile, text="-", bg=SOFT,
                             font=self.f["bold"] if key == "weather" else self.f["stat"],
                             fg=DIM_COLOURS.get(key, INK))
            value.pack(anchor="w")
            self.stat_labels[key] = value

        self.chart = tk.Canvas(p, height=180, bg=CARD, highlightthickness=0)
        self.chart.pack(fill="both", expand=True, pady=(6, 0))
        self.chart.bind("<Configure>", self.on_chart_resize)

    # ---------- small methods that tkinter calls when something happens ----------
    def on_banner_resize(self, _event):
        """The window changed size: draw the banner again."""
        self.draw_banner()

    def on_text_focus_in(self, _event):
        """The user clicked into the text box: remove the hint text."""
        self.placeholder(False)

    def on_text_focus_out(self, _event):
        """The user clicked somewhere else: put the hint back if the box is empty."""
        self.placeholder(True)

    def on_key_release(self, _event):
        """A key was typed: update the character count."""
        self.count()

    def on_open(self, _event):
        """Double-click or Enter in the table: open the entry."""
        self.view_entry()

    def on_chart_resize(self, _event):
        """The chart changed size: draw it again."""
        self.draw_chart()

    def set_today(self):
        """The "Today" button: put today's date in the date box."""
        self.date_var.set(date.today().strftime(DATE_FORMAT))

    # ---------- small helpers ----------
    def placeholder(self, show):
        """Show the gray hint when the box is empty, or remove it when the user starts typing."""
        content = self.text.get("1.0", "end").strip()
        if show and not content:
            self.text.insert("1.0", PLACEHOLDER)
            self.text.configure(fg=MUTED)
        elif not show and content == PLACEHOLDER:
            self.text.delete("1.0", "end")
            self.text.configure(fg=INK)

    def text_value(self):
        """The text the user really typed (the gray hint counts as empty)."""
        content = self.text.get("1.0", "end").strip()
        return "" if content == PLACEHOLDER else content

    def count(self):
        """Update the "N characters" label."""
        self.counter.configure(text=f"{len(self.text_value())} characters")

    def draw_banner(self):
        """Draw the banner: color fade, dots, stars, a cloud, the title and the tagline."""
        c = self.banner
        c.delete("bg")
        w, h = c.winfo_width(), c.winfo_height()

        steps = 80
        for i in range(steps):                               # 80 thin strips = color fade
            x0 = w * i / steps
            c.create_rectangle(x0, 0, x0 + w / steps + 1, h,
                               fill=banner_colour(i / steps), outline="", tags="bg")
        rng = random.Random(9)                               # same seed, so the dots stay put
        for _ in range(int(w / 10)):
            x, y, r = rng.uniform(0, w), rng.uniform(6, h - 6), rng.choice((1.2, 1.8, 2.6))
            c.create_oval(x - r, y - r, x + r, y + r, outline="", tags="bg",
                          fill=rng.choice(("#FFFFFF", "#C9B6F5")))
        for x, y, r, col in ((0.40, 0.25, 8, "#FDE68A"), (0.50, 0.72, 6, "#B79CF5"),
                             (0.60, 0.3, 7, "#FFFFFF"), (0.70, 0.7, 6, "#FDE68A")):
            draw_sparkle(c, w * x, h * y, r, col, tags="bg")
        draw_cloud(c, w * 0.66, h * 0.42, 0.42, "#FFFFFF", "#D8C4FF", tags="bg")
        # round the 4 corners of the banner
        for cx, cy, sx, sy in ((0, 0, 1, 1), (w, 0, -1, 1), (0, h, 1, -1), (w, h, -1, -1)):
            pts = [cx, cy]
            r = 20
            for k in range(11):
                a = math.pi / 2 * k / 10
                pts += [cx + sx * (r - r * math.cos(a)), cy + sy * (r - r * math.sin(a))]
            c.create_polygon(pts, fill=BG, outline=BG, tags="bg")
        image = self.load_banner_image(h - 8)
        if image is not None:
            c.create_image(w - 40 - self.banner_button_frame.winfo_reqwidth(), h / 2,
                           image=image, anchor="e", tags="bg")
        self.draw_mascot(c, 66, h / 2 - 4)
        sticker_text(c, 130, 38, "VibeWeather", self.f["title"], tags="bg")
        c.create_text(132, 72, text=TAGLINES[self.current_weather], anchor="w",
                      fill="#7A5AC8", font=self.f["sub"], tags="bg")
        c.tag_lower("bg")                                    # keep the buttons on top
        c.coords(self.banner_buttons, w - 20, h / 2)

    def load_banner_image(self, max_height):
        """Load background.png once and shrink it to fit the banner."""
        if not self.banner_image_loaded:
            self.banner_image_loaded = True
            if os.path.exists(BACKGROUND_IMAGE):
                try:
                    image = tk.PhotoImage(file=BACKGROUND_IMAGE)
                    factor = max(1, math.ceil(image.height() / max_height))
                    self.banner_image = image.subsample(factor, factor)
                except tk.TclError as err:
                    print(f"Could not load {os.path.basename(BACKGROUND_IMAGE)}: {err}")
        return self.banner_image

    def draw_mascot(self, c, x, y):
        """Draw the small cloud on the banner. Its face matches the current weather."""
        fill, outline = CLOUD_COLOURS[self.current_weather]
        draw_cloud(c, x, y, 0.62, fill, outline, tags="bg")
        draw_face(c, x, y, 0.62, FACES[self.current_weather], tags="bg")

    # ---------- what the buttons do ----------
    def add_entry(self):
        """The save button: check the date, score the text and save the entry."""
        try:
            entry_date = datetime.strptime(self.date_var.get().strip(), DATE_FORMAT).date()
        except ValueError:
            messagebox.showerror("Invalid date", "Date must look like 2026-09-29")
            return
        text = self.text_value()
        if not text and not messagebox.askyesno("Empty entry",
                                                "The entry is empty. Save it anyway?"):
            return
        try:
            scores, _ = self.engine.score(text)
            entry = JournalEntry(entry_date, text, scores, self.reporter.classify(scores))
        except VibeWeatherError as err:
            messagebox.showerror("Invalid entry", str(err))
            return
        self.entries.append(entry)
        self.text.delete("1.0", "end")
        self.placeholder(self.root.focus_get() is not self.text)   # hint back if not typing
        self.count()
        self.save()
        self.refresh()
        self.show_entry(entry)

    def delete_entry(self):
        """Delete the selected entry (after asking)."""
        entry = self.selected()
        if entry is None:
            messagebox.showinfo("Delete", "Select an entry in the history first.")
            return
        if messagebox.askyesno("Delete", f"Delete the entry from {entry.date}?"):
            # keep every entry except this one. "is not" checks for this exact
            # entry, so another entry with the same date and text is kept
            remaining = []
            for other in self.entries:
                if other is not entry:
                    remaining.append(other)
            self.entries = remaining
            self.save()
            self.refresh()
            self.show_latest()          # show the newest entry instead of the deleted one

    def view_entry(self):
        """Open a new window with the whole entry, its weather and its scores."""
        entry = self.selected()
        if entry is None:
            messagebox.showinfo("View", "Select an entry in the history first.")
            return
        win = tk.Toplevel(self.root, bg=CARD, padx=20, pady=16)
        win.title(f"Entry - {entry.date.strftime('%d %b %Y')}")
        win.transient(self.root)
        self.label(win, entry.weather, "big", tag_colour(entry.weather)).pack(anchor="w")
        parts = []
        for d in DIMENSIONS:
            parts.append(f"{d} {entry.scores[d]:.2f}")
        scores = "   ".join(parts)
        self.label(win, f"{entry.date.strftime('%A, %d %B %Y')}   |   {scores}",
                   "small", MUTED).pack(anchor="w")
        text = tk.Text(win, width=60, height=10, wrap="word", font=self.f["input"],
                       relief="flat", bg=SOFT, fg=INK, padx=12, pady=10,
                       highlightthickness=0)
        text.insert("1.0", entry.text or "(empty entry)")
        text.configure(state="disabled")
        text.pack(fill="both", expand=True, pady=10)
        FlatButton(win, "Close", win.destroy, self.f["bold"],
                   primary=True).label.pack(anchor="e")

    def load_demo(self):
        """Add the 7 sample entries, one for each of the last 7 days."""
        if not messagebox.askyesno(
                "Demo week", "Add 7 sample entries (the last 7 days) so you can see "
                             "the chart? They go through your own scoring algorithm."):
            return
        today = date.today()
        for i in range(len(DEMO_WEEK)):
            text = DEMO_WEEK[i]
            d = today - timedelta(days=len(DEMO_WEEK) - 1 - i)     # the last one is today
            scores, _ = self.engine.score(text)
            self.entries.append(JournalEntry(d, text, scores, self.reporter.classify(scores)))
        self.save()
        self.refresh()
        self.show_latest()

    def manage_keywords(self):
        """Add, update or remove the user's own keywords with small pop-up boxes."""
        names = []
        for word in self.engine.custom_words:
            names.append(word.replace("_", " "))      # show "fed_up" as "fed up"
        names.sort()
        words = ", ".join(names)
        if words == "":
            words = "(none)"
        choice = simpledialog.askstring(
            "Custom keywords", f"Your keywords: {words}\n\n"
                               "Type a word or a short phrase (like fed up) to add/update it,\n"
                               "or -word to remove it:",
            parent=self.root)
        if choice is None:                      # Cancel was pressed
            choice = ""
        choice = choice.strip()
        if not choice:
            return
        try:
            if choice.startswith("-"):
                self.engine.remove_keyword(choice[1:])
            else:
                choice = self.engine.check_keyword(choice)      # check the word first
                weights = {}
                for d in DIMENSIONS:
                    value = simpledialog.askfloat(
                        "Weight", f"'{choice.replace('_', ' ')}' - {d} weight (0 to 1):",
                        minvalue=0.0, maxvalue=1.0, parent=self.root)
                    if value is None:           # Cancel was pressed
                        return
                    weights[d] = value
                self.engine.add_keyword(choice, weights)
        except VibeWeatherError as err:
            messagebox.showerror("Keyword", str(err))
            return
        self.save()
        messagebox.showinfo("Keyword", "Saved. New entries will use it - use "
                                       "'Re-score all' to update older entries too.")

    def rescore_entries(self):
        """Score every entry again with the current keywords."""
        if not self.entries:
            messagebox.showinfo("Re-score", "There are no entries yet.")
            return
        if not messagebox.askyesno(
                "Re-score", f"Score all {len(self.entries)} entries again with the "
                            "current keywords and rules?"):
            return
        changed = rescore_all(self.entries, self.engine, self.reporter)
        self.save()
        self.refresh()
        self.show_latest()
        messagebox.showinfo("Re-score", f"{changed} of {len(self.entries)} entries changed.")

    # ---------- showing entries ----------
    def ordered(self):
        """The entries in the chosen order: newest first, or strongest mood first."""
        if self.sort_mode.get() == "intensity":
            return sorted(self.entries, key=by_intensity)
        return sorted(self.entries, reverse=True)        # newest first (uses JournalEntry.__lt__)

    def refresh(self):
        """Fill the history table again, then redraw the chart and the tiles."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.rows = self.ordered()
        for i in range(len(self.rows)):
            e = self.rows[i]
            flat = " ".join(e.text.split())      # put a multi-line entry on one line
            preview = flat if len(flat) <= 48 else flat[:48] + "..."
            tags = [e.weather]
            if i % 2 == 1:
                tags.append("odd")               # light stripes on every other row
            self.tree.insert("", "end", iid=str(i), tags=tags,
                             values=(e.date.strftime("%d %b %Y"), e.weather, preview))
        self.draw_chart()
        self.update_stats()

    def selected(self):
        """The entry that is selected in the table, or None."""
        sel = self.tree.selection()
        return self.rows[int(sel[0])] if sel else None

    def on_select(self, _event):
        """Show the entry the user clicked on in the table."""
        entry = self.selected()
        if entry is not None:
            self.show_entry(entry)

    def show_entry(self, entry: JournalEntry):
        """Show one entry in the top-right card and update the banner."""
        self.current_weather = known_weather(entry.weather)
        self.scene.show(entry.weather)
        self.draw_banner()
        self.weather_tag.configure(
            text=" TODAY " if entry.date == date.today() else f" {entry.date.strftime('%d %b').upper()} ",
            bg=PILL)
        self.weather_label.configure(text=entry.weather)
        self.date_label.configure(text=entry.date.strftime("%A, %d %B %Y"))
        self.draw_bars(entry.scores)
        # work out the explanation again, using the current rules
        scores, explanation = self.engine.score(entry.text)
        weather, rule = self.reporter.explain_weather(entry.scores)
        explanation = explanation + [f"{weather} because {rule}"]
        if scores != entry.scores or weather != entry.weather:     # the saved score is old
            explanation.append(STALE_NOTE)
        self.set_explanation(explanation)

    def show_latest(self):
        """Show the newest entry, or the empty screen when there are no entries."""
        if self.entries:
            self.show_entry(sorted(self.entries)[-1])
            return
        self.current_weather, self.current_scores = "Unclassified", None
        self.scene.show("Unclassified")
        self.draw_banner()
        self.weather_tag.configure(text=" TODAY ")
        self.weather_label.configure(text="No entry yet")
        self.date_label.configure(text="")
        self.bars.delete("all")
        self.set_explanation([])

    def set_explanation(self, lines):
        """Put the explanation lines in the "Why this score?" box."""
        self.explain.configure(state="normal")       # unlock the box, change it, lock it again
        self.explain.delete("1.0", "end")
        self.explain.insert("end", "   |   ".join(lines))
        self.explain.configure(state="disabled")

    def redraw_bars(self, _event):
        """Draw the score bars again after a resize (nothing to draw before an entry)."""
        if self.current_scores:
            self.draw_bars(self.current_scores)

    def draw_bars(self, scores):
        """Draw the three score bars: a light track with a colored bar on top."""
        self.current_scores = scores
        c = self.bars
        c.delete("all")
        width = max(c.winfo_width(), 200)
        x0, x1 = 78, width - 44                  # where the bars start and end
        for i in range(len(DIMENSIONS)):
            d = DIMENSIONS[i]
            y = 12 + i * 30
            c.create_text(0, y, text=d.capitalize(), anchor="w",
                          font=self.f["small"], fill=MUTED)
            c.create_line(x0, y, x1, y, fill=SOFT, width=10, capstyle=tk.ROUND)
            if scores[d] > 0.01:                 # a tiny bar would just look like a dot
                c.create_line(x0, y, x0 + (x1 - x0) * scores[d], y,
                              fill=DIM_COLOURS[d], width=10, capstyle=tk.ROUND)
            c.create_text(width, y, text=f"{scores[d]:.2f}", anchor="e",
                          font=self.f["bold"], fill=INK)

    def draw_chart(self):
        """Draw the trend chart: a weather pill for each day and one line per mood."""
        c = self.chart
        c.delete("all")
        w, h = max(c.winfo_width(), 300), max(c.winfo_height(), 150)
        left, right, top, bottom = 30, w - 18, 26, h - 44     # edges of the drawing area
        days = self.chart_days.get()
        end = date.today()
        start = end - timedelta(days=days - 1)

        x = left                                 # the legend at the top
        for d in DIMENSIONS:
            c.create_oval(x, 6, x + 8, 14, fill=DIM_COLOURS[d], outline="")
            c.create_text(x + 13, 10, text=d.capitalize(), anchor="w",
                          font=self.f["tiny"], fill=MUTED)
            x += 86

        for v in (0, 0.5, 1):                    # reference lines at 0, 0.5 and 1
            y = bottom - (bottom - top) * v
            c.create_line(left, y, right, y, fill=BORDER, dash=(2, 4) if v else ())
            c.create_text(left - 8, y, text=f"{v:g}", anchor="e",
                          font=self.f["tiny"], fill=MUTED)

        step = (right - left) / max(days - 1, 1)  # space between two days
        by_day = {}                              # date -> the entries written that day
        for e in self.entries:
            if start <= e.date <= end:
                if e.date not in by_day:
                    by_day[e.date] = []
                by_day[e.date].append(e)

        # a colored pill under each day shows that day's weather
        pill = max(4, min(step - 4, 26))
        label_every = 1 if days <= 7 else (2 if days <= 14 else 5)    # fewer dates for 14/30 days
        for i in range(days):
            day = start + timedelta(days=i)
            cx = left + i * step
            if day in by_day:
                colour = tag_colour(most_common_weather(by_day[day]))
            else:
                colour = SOFT
            rounded_rect(c, cx - pill / 2, bottom + 8, cx + pill / 2, bottom + 16, 4,
                         fill=colour, outline="")
            if i % label_every == 0 or i == days - 1:
                c.create_text(cx, bottom + 30, text=day.strftime("%d/%m"),
                              font=self.f["tiny"], fill=MUTED)

        if not by_day:                           # nothing to draw: show a message instead
            c.create_text((left + right) / 2, (top + bottom) / 2,
                          text="No entries in this period yet", fill=MUTED,
                          font=self.f["body"])
            return
        # one line per mood. A day with no entry breaks the line, so I never
        # draw a line across a gap.
        for d in DIMENSIONS:
            segment = []
            for i in range(days):
                day = start + timedelta(days=i)
                if day in by_day:
                    avg = average_score(by_day[day], d)
                    segment.append((left + i * step, bottom - (bottom - top) * avg))
                else:
                    self.plot(segment, DIM_COLOURS[d])
                    segment = []
            self.plot(segment, DIM_COLOURS[d])

    def plot(self, points, colour):
        """Draw one piece of a line, with a dot on each day."""
        if len(points) > 1:
            flat = []                            # [(x1, y1), (x2, y2)] -> [x1, y1, x2, y2]
            for x, y in points:
                flat.append(x)
                flat.append(y)
            self.chart.create_line(flat, fill=colour, width=3,
                                   joinstyle=tk.ROUND, capstyle=tk.ROUND)
        for x, y in points:
            self.chart.create_oval(x - 5, y - 5, x + 5, y + 5, fill=colour,
                                   outline=CARD, width=2)

    def update_stats(self):
        """Update the 4 tiles above the chart: the averages and the most common weather."""
        days = self.chart_days.get()
        end = date.today()
        start = end - timedelta(days=days - 1)
        recent = []                              # only the days shown in the chart
        for e in self.entries:
            if start <= e.date <= end:
                recent.append(e)
        if not recent:
            for label in self.stat_labels.values():
                label.configure(text="-")
            return
        for d in DIMENSIONS:
            self.stat_labels[d].configure(text=f"{average_score(recent, d):.2f}")
        weather = most_common_weather(recent)
        self.stat_labels["weather"].configure(text=weather, fg=tag_colour(weather))


def main():
    """Start VibeWeather: open the window and keep it open until it is closed."""
    if sys.platform.startswith("win"):
        try:                                   # makes the text sharp on Windows screens
            import ctypes
            # noinspection PyUnresolvedReferences
            ctypes.windll.shcore.SetProcessDpiAwareness(1)    # only exists on Windows
        except (AttributeError, OSError):      # old Windows doesn't have it, so skip
            pass
    VibeWeatherGUI().run()


if __name__ == "__main__":
    main()
