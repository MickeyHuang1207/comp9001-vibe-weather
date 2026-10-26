import math
import random
import tkinter as tk
# Import drawing utilities and color constants
from drawing import (ACCENT, ACCENT_DARK, BG, BORDER, CARD, CLOUD_COLOURS, FACES, INK,
                     MUTED, PILL, SKY_COLOURS, SOFT, blend, draw_cloud, draw_face,
                     draw_sparkle, draw_sun, known_weather, rounded_rect)


class Card:
    """Rounded‑corner white card widget"""
    def __init__(self, master, padding=16, radius=16):
        self.canvas = tk.Canvas(master, bg=BG, highlightthickness=0)
        self.radius = radius
        self.body = tk.Frame(self.canvas, bg=CARD)  # Inner container for child widgets
        self._win = self.canvas.create_window(padding, padding, window=self.body, anchor="nw")
        self.padding = padding
        self.canvas.bind("<Configure>", self._redraw)  # Redraw on size change

    def _redraw(self, event):
        """Redraw rounded borders when card resizes"""
        c = self.canvas
        c.delete("bg")
        rounded_rect(c, 0, 0, event.width - 1, event.height - 1, self.radius, fill=BORDER, tags="bg")
        rounded_rect(c, 2.5, 2.5, event.width - 3.5, event.height - 3.5, self.radius - 2, fill=CARD, tags="bg")
        c.tag_lower("bg")
        p = self.padding
        c.itemconfigure(self._win, width=event.width - 2 * p, height=event.height - 2 * p - 2)


class FlatButton:
    """Flat‑style button implemented with Label (fix macOS button color issue)"""
    def __init__(self, master, text, command, font, primary=False, small=False, night=False):
        if night:
            self.normal, self.hover, fg = PILL, ACCENT_DARK, "white"
        else:
            self.normal = ACCENT if primary else SOFT
            self.hover = ACCENT_DARK if primary else BORDER
            fg = "white" if primary else INK
        self.label = tk.Label(master, text=text, font=font, cursor="hand2",
                              bg=self.normal, fg=fg,
                              padx=10 if small else 16, pady=4 if small else 8)
        self.command = command
        # Bind mouse events
        self.label.bind("<Enter>", self._on_enter)
        self.label.bind("<Leave>", self._on_leave)
        self.label.bind("<Button-1>", self._on_click)

    def _on_enter(self, _event):
        """Mouse hovers over button: use hover color"""
        self.label.configure(bg=self.hover)

    def _on_leave(self, _event):
        """Mouse leaves button: restore normal color"""
        self.label.configure(bg=self.normal)

    def _on_click(self, _event):
        """Trigger callback on button click"""
        self.command()


class Segmented:
    """Radio‑button‑like segmented option switch"""
    def __init__(self, master, options, variable, command, font):
        self.frame = tk.Frame(master, bg=SOFT, padx=3, pady=3)
        self.variable, self.command, self.buttons = variable, command, {}
        for label, value in options:
            b = tk.Label(self.frame, text=label, font=font, padx=10, pady=3, cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", self._on_click)
            self.buttons[value] = b
        self._paint()

    def _on_click(self, event):
        """Detect which option was clicked"""
        for value, b in self.buttons.items():
            if b is event.widget:
                self._choose(value)

    def _choose(self, value):
        """Save selected value, refresh appearance and run callback"""
        self.variable.set(value)
        self._paint()
        self.command()

    def _paint(self):
        """Update colors: active item white, others light purple"""
        for value, b in self.buttons.items():
            active = value == self.variable.get()
            b.configure(bg=CARD if active else SOFT, fg=INK if active else MUTED)


class WeatherScene:
    """Animated weather display canvas"""
    def __init__(self, master, width: int = 260, height: int = 180):
        self.canvas = tk.Canvas(master, width=width, height=height,
                                highlightthickness=0, bg=CARD)
        self.w, self.h = width, height
        self.weather, self.frame = "Unclassified", 0
        self.drops = []                   # Raindrop data: [x, y, speed]
        self.after_id = None              # Animation timer id
        self.show("Unclassified")

    def show(self, weather):
        """Switch weather type and restart animation"""
        self.weather = known_weather(weather)
        self.frame = 0
        # Set raindrop count for rainy / stormy
        n = {"Rainy": 14, "Stormy": 10}.get(self.weather, 0)
        self.drops = []
        for _ in range(n):
            self.drops.append([random.uniform(70, self.w - 70), random.uniform(110, self.h),
                               random.uniform(1.5, 2.5)])
        if self.after_id:                 # Cancel old animation to avoid duplicates
            self.canvas.after_cancel(self.after_id)
        self._tick()

    def _sky(self):
        """Draw gradient sky, background dots and twinkling sparkles"""
        c = self.canvas
        top, bottom = SKY_COLOURS[self.weather]
        steps = 30
        for i in range(steps):                     # Build gradient with thin strips
            y0 = self.h * i / steps
            c.create_rectangle(0, y0, self.w, y0 + self.h / steps + 1,
                               fill=blend(top, bottom, i / steps), outline="")
        rng = random.Random(3)                     # Fixed seed for static background dots
        for _ in range(18):
            x, y, r = rng.uniform(0, self.w), rng.uniform(0, self.h), rng.choice((1.2, 1.8, 2.4))
            c.create_oval(x - r, y - r, x + r, y + r, fill="white", outline="")
        twinkle = 1 + 0.25 * math.sin(self.frame * 0.12)       # Twinkle scale factor
        draw_sparkle(c, 22, 24, 8 * twinkle, "#FDE68A")
        draw_sparkle(c, self.w - 24, self.h - 26, 7 * twinkle, "#C4B5FD")

    def _corners(self, r=20):
        """Mask four corners for rounded visual effect"""
        w, h = self.w, self.h
        for cx, cy, sx, sy in ((0, 0, 1, 1), (w, 0, -1, 1), (0, h, 1, -1), (w, h, -1, -1)):
            pts = [cx, cy]
            for k in range(11):
                a = math.pi / 2 * k / 10
                pts += [cx + sx * (r - r * math.cos(a)), cy + sy * (r - r * math.sin(a))]
            self.canvas.create_polygon(pts, fill=CARD, outline=CARD)

    def _tick(self):
        """Main animation loop, runs every 40ms"""
        c = self.canvas
        c.delete("all")
        self._sky()
        w, h, f = self.w, self.h, self.frame
        fill, outline = CLOUD_COLOURS[self.weather]
        face = FACES[self.weather]
        bob = math.sin(f * 0.08) * 3                 # Vertical float offset
        drift = math.sin(f * 0.04) * 6               # Horizontal drift offset
        cx, cy = w / 2, h / 2

        if self.weather == "Sunny":
            draw_sun(c, cx, cy + bob, 44, spin=f * 0.015)
        elif self.weather == "Partly Cloudy":
            draw_sun(c, cx + 42, cy - 30, 26, spin=f * 0.015, face=False)
            draw_cloud(c, cx - 12 + drift, cy + 12 + bob, 1.0, fill, outline)
            draw_face(c, cx - 12 + drift, cy + 12 + bob, 1.0, face)
        elif self.weather == "Overcast":
            draw_cloud(c, cx + 40 - drift, cy - 30, 0.65, "#D9D2EC", "#BEB4DD")
            draw_cloud(c, cx - 10 + drift, cy + 8 + bob, 1.0, fill, outline)
            draw_face(c, cx - 10 + drift, cy + 8 + bob, 1.0, face)
        elif self.weather in ("Rainy", "Stormy"):
            # Flash lightning for some frames in stormy weather
            if self.weather == "Stormy" and f % 50 < 18:
                x, y = cx + 8, cy + 20
                c.create_polygon(x, y, x - 16, y + 34, x - 3, y + 34, x - 11, y + 62,
                                 x + 18, y + 22, x + 4, y + 22, x + 12, y,
                                 fill="#FDD24A", outline="")
            # Update and draw falling raindrops
            for d in self.drops:
                x, y = d[0], d[1]
                c.create_oval(x - 4, y, x + 4, y + 8, fill="#8CC2F5", outline="")
                c.create_polygon(x - 3.6, y + 3, x + 3.6, y + 3, x, y - 5,
                                 fill="#8CC2F5", outline="")
                d[1] += d[2]                                 # Move drop downwards
                if d[1] > h:                                 # Reset drop when off‑screen
                    d[0], d[1] = random.uniform(70, w - 70), cy + 20
            draw_cloud(c, cx - 5 + drift, cy - 22 + bob, 1.0, fill, outline)
            draw_face(c, cx - 5 + drift, cy - 22 + bob, 1.0, face)
        elif self.weather == "Foggy":
            draw_cloud(c, cx - 5, cy - 8 + bob, 1.0, fill, outline)
            draw_face(c, cx - 5, cy - 8 + bob, 1.0, face)
            widths = (170, 150, 185)                         # Three moving fog layers
            for i in range(len(widths)):
                y = cy + 22 + i * 18
                off = math.sin(f * 0.05 + i * 1.7) * 18
                c.create_line(cx - widths[i] / 2 + off, y, cx + widths[i] / 2 + off, y,
                              fill="#D5CCEE", width=10, capstyle=tk.ROUND)
        else:                                          # Unclassified: sleepy cloud
            draw_cloud(c, cx - 10, cy + 10 + bob, 1.0, fill, outline)
            draw_face(c, cx - 10, cy + 10 + bob, 1.0, "sleep")
            sleepy_zs = ((48, -30, 10), (60, -46, 13), (74, -64, 16))
            for i in range(len(sleepy_zs)):
                dx, dy, size = sleepy_zs[i]
                if (f // 12) % 4 > i:                  # Show sleep "z" symbols sequentially
                    c.create_text(cx + dx, cy + dy, text="z", fill=ACCENT,
                                  font=("Helvetica", size, "bold"))
        self._corners()
        self.frame += 1
        self.after_id = c.after(40, self._tick)        # ~25 frames per second
