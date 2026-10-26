import math
from tkinter import font as tkfont

# Window UI color definitions
BG = "#EDE4FF"          # Window background
CARD = "#FFFFFF"        # Card background
BORDER = "#DCCBFF"      # Card border color
INK = "#3D226E"         # Main text color
MUTED = "#8A77B5"       # Secondary text color
SOFT = "#F6F1FF"        # Text box / slider track background
ACCENT = "#9B7BF0"      # Main button color
ACCENT_DARK = "#7C5CE0" # Darker button shade
PILL = "#A78BFA"        # Small label tag color
TITLE_STROKE = "#9670E6"# Title outline color
TITLE_SHADOW = "#F7B4D8"# Title shadow color
BANNER = ("#D9C9FF", "#EDE4FF", "#F8E6FF") # Banner gradient colors
BLUSH = "#FFA5C3"       # Cheek blush color
SUN, SUN_EDGE = "#FFDE78", "#FFC45A" # Sun fill and outline
DIM_COLOURS = {"stress": "#F43F5E", "vitality": "#F59E0B", "calmness": "#38BDF8"} # Status colors

# Drawing config for each weather type, key = weather name
SKY_COLOURS = {                       # Top / bottom sky gradient colors
    "Sunny": ("#F1E6FF", "#FFF4D9"),
    "Partly Cloudy": ("#E7DBFF", "#F8F3FF"),
    "Overcast": ("#DED7EF", "#F2EEF9"),
    "Rainy": ("#D6E2FA", "#EFF3FF"),
    "Stormy": ("#CDBDF2", "#E8E0FA"),
    "Foggy": ("#EEEAF7", "#FAF8FD"),
    "Unclassified": ("#E9DDFF", "#FBF7FF"),
}
TAG_COLOURS = {                       # Text color for history table entries
    "Sunny": "#D99A00",
    "Partly Cloudy": "#8B5CF6",
    "Overcast": "#8C84A8",
    "Rainy": "#3B9EE8",
    "Stormy": "#6D3FD6",
    "Foggy": "#A59CC0",
    "Unclassified": "#B9A6F0",
}
CLOUD_COLOURS = {                     # Cloud fill color, cloud outline color
    "Sunny": ("#FFFFFF", "#D8C4FF"),
    "Partly Cloudy": ("#FFFFFF", "#D8C4FF"),
    "Overcast": ("#E8E4F5", "#BEB4DD"),
    "Rainy": ("#DCE6FF", "#A3BCEB"),
    "Stormy": ("#B4A5E6", "#8A6FD2"),
    "Foggy": ("#F5F2FC", "#D7CDEF"),
    "Unclassified": ("#FFFFFF", "#D8C4FF"),
}
FACES = {                             # Facial expression used by draw_face()
    "Sunny": "joy",
    "Partly Cloudy": "happy",
    "Overcast": "meh",
    "Rainy": "sad",
    "Stormy": "shock",
    "Foggy": "sleep",
    "Unclassified": "sleep",
}

def known_weather(weather):
    """Fallback to Unclassified for unknown weather types"""
    if weather in FACES:
        return weather
    return "Unclassified"

def tag_colour(weather):
    """Get text color for weather history table"""
    return TAG_COLOURS[known_weather(weather)]

def pick_font_family(root):
    """Return first available font from candidate list"""
    available = set(tkfont.families(root))
    for family in ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter",
                   "Noto Sans", "DejaVu Sans"):
        if family in available:
            return family
    return "Helvetica"

def hex_to_rgb(colour):
    """Convert hex color string to RGB integer list [R,G,B]"""
    return [int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)]

def blend(c1, c2, t):
    """Linear‑interpolate two colors. t=0 → c1, t=1 → c2"""
    a = hex_to_rgb(c1)
    b = hex_to_rgb(c2)
    mixed = []
    for i in range(3):
        mixed.append(round(a[i] + (b[i] - a[i]) * t))
    return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"

def banner_colour(t):
    """Get banner gradient color at position t (0=left, 1=right)"""
    if t < 0.5:
        return blend(BANNER[0], BANNER[1], t * 2)
    return blend(BANNER[1], BANNER[2], (t - 0.5) * 2)

def rounded_rect(canvas, x0: float, y0: float, x1: float, y1: float, r: float,
                 fill, outline="", tags=()):
    """Draw rounded‑corner rectangle using smooth polygon"""
    r = max(0.0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))     # Clamp corner radius
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
           x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return canvas.create_polygon(pts, smooth=True, fill=fill, outline=outline, tags=tags)

# Cloud shape data: (x offset, y offset, radius) for four circle parts
CLOUD_PARTS = ((-40, 8, 26), (-12, -10, 34), (22, -2, 30), (46, 10, 22))

def draw_cloud(c, x, y, s, fill, outline, tags=()):
    """Render cloud shape from multiple ovals + bottom rectangle"""
    for colour, shrink in ((outline, 0), (fill, 5)):
        for dx, dy, r in CLOUD_PARTS:
            r -= shrink
            c.create_oval(x + (dx - r) * s, y + (dy - r) * s, x + (dx + r) * s,
                          y + (dy + r) * s, fill=colour, outline="", tags=tags)
        inset = 4 if shrink else 0
        # Fill flat bottom of cloud
        c.create_rectangle(x + (-40 + inset) * s, y + 6 * s, x + (46 - inset) * s,
                           y + (32 - inset * 1.2) * s, fill=colour, outline="", tags=tags)

def draw_face(c, x, y, s, kind, tags=()):
    """Draw cartoon face: joy/happy/meh/sad/shock/sleep expressions"""
    ex, ey, er = 19 * s, y + 4 * s, 6.5 * s
    for side in (-1, 1):                                    # Draw left and right eye
        cx = x + side * ex
        if kind in ("joy", "sleep"):                        # Closed eyes
            start, extent = (20, 140) if kind == "joy" else (200, 140)
            c.create_arc(cx - er, ey - er * 0.8, cx + er, ey + er * 0.8, start=start,
                         extent=extent, style="arc", outline=INK, width=max(2, 2.2 * s),
                         tags=tags)
        else:                                               # Open eyes with highlight
            r = er * (0.8 if kind == "meh" else 1)
            c.create_oval(cx - r, ey - r * 1.25, cx + r, ey + r * 1.25, fill=INK,
                          outline="", tags=tags)
            c.create_oval(cx - r * 0.55, ey - r * 0.95, cx + r * 0.05, ey - r * 0.3,
                          fill="white", outline="", tags=tags)
        c.create_oval(cx + side * 14 * s - 7 * s, y + 13 * s, cx + side * 14 * s + 7 * s,
                      y + 21 * s, fill=BLUSH, outline="", tags=tags)      # Blush cheeks
    mx, my = x, y + 18 * s                                  # Mouth position
    if kind in ("joy", "happy"):
        c.create_arc(mx - 8 * s, my - 8 * s, mx + 8 * s, my + 8 * s, start=180,
                     extent=180, style="chord", fill=INK, outline="", tags=tags)
        c.create_arc(mx - 4 * s, my, mx + 4 * s, my + 8 * s, start=180, extent=180,
                     style="chord", fill="#FF82A0", outline="", tags=tags)
    elif kind == "meh":
        c.create_line(mx - 6 * s, my + 3 * s, mx + 6 * s, my + 3 * s, fill=INK,
                      width=max(2, 2.2 * s), tags=tags)
    elif kind == "sad":
        c.create_arc(mx - 7 * s, my, mx + 7 * s, my + 10 * s, start=20, extent=140,
                     style="arc", outline=INK, width=max(2, 2.2 * s), tags=tags)
    elif kind == "shock":
        c.create_oval(mx - 4 * s, my - 1 * s, mx + 4 * s, my + 9 * s, fill=INK,
                      outline="", tags=tags)
    else:                                                    # Sleep expression
        c.create_oval(mx - 3 * s, my + 1 * s, mx + 3 * s, my + 7 * s, fill=INK,
                      outline="", tags=tags)

def draw_sun(c, x, y, r, spin=0.0, face=True, tags=()):
    """Draw sun graphic with 10 ray circles; optional rotating face"""
    for k in range(10):
        a = k * math.pi / 5 + spin
        px, py, pr = x + math.cos(a) * r * 1.38, y + math.sin(a) * r * 1.38, r * 0.26
        c.create_oval(px - pr, py - pr, px + pr, py + pr, fill=SUN_EDGE, outline="",
                      tags=tags)
    c.create_oval(x - r, y - r, x + r, y + r, fill=SUN, outline=SUN_EDGE,
                  width=max(2, r / 12), tags=tags)
    if face:
        draw_face(c, x, y - r * 0.2, r / 30, "joy", tags)

def draw_sparkle(c, x, y, r, colour, tags=()):
    """Draw 4‑point star shape (alternating long‑short points)"""
    pts = []
    for k in range(8):
        a = k * math.pi / 4 - math.pi / 2
        rr = r if k % 2 == 0 else r * 0.3
        pts += [x + math.cos(a) * rr, y + math.sin(a) * rr]
    c.create_polygon(pts, fill=colour, outline="", tags=tags)

def sticker_text(c, x, y, text, font, tags=(), anchor="w"):
    """Render styled text: white fill, purple outline, pink drop shadow"""
    for dx, dy in ((2, 3), (3, 3)):                        # Pink shadow layer
        c.create_text(x + dx, y + dy, text=text, font=font, fill=TITLE_SHADOW,
                      anchor=anchor, tags=tags)
    for k in range(12):                                    # Offset copies for outline effect
        a = k * math.pi / 6
        c.create_text(x + math.cos(a) * 2.5, y + math.sin(a) * 2.5, text=text, font=font,
                      fill=TITLE_STROKE, anchor=anchor, tags=tags)
    c.create_text(x, y, text=text, font=font, fill="white", anchor=anchor, tags=tags)