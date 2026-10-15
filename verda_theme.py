"""
Visual theme for the VERDA Risk Model Lab.

Developer: József Szeles, Department of System Engineering, University of Pannonia

A flat, modern look built on the standard ttk "clam" theme: dark header and
tab bar, light-grey page, white cards with thin borders, one blue accent.
Uses only the standard library, so the PyInstaller build is unchanged.
"""

import sys
import tkinter as tk
from tkinter import ttk, font as tkfont

# -- palette ------------------------------------------------------------------
HEADER = "#0f172a"        # top bar and tab bar
HEADER_2 = "#1e293b"      # hovered tab
HEADER_TEXT = "#f8fafc"
HEADER_MUTED = "#94a3b8"
PAGE = "#eef2f7"          # page background
CARD = "#ffffff"          # card / canvas background
SUBTLE = "#f8fafc"        # table headings, info boxes
LINE = "#dbe2ea"          # borders
INK = "#0f172a"           # main text
MUTED = "#64748b"         # secondary text
FAINT = "#94a3b8"         # tertiary text, edges
ACCENT = "#2563eb"
ACCENT_DARK = "#1d4ed8"
ACCENT_SOFT = "#dbeafe"
RISK = "#dc2626"
RISK_SOFT = "#fee2e2"
RISK_FILL = "#f87171"     # heat-map end for "more risk"
GOOD = "#16a34a"
GOOD_SOFT = "#dcfce7"
GOOD_FILL = "#4ade80"
WARN = "#d97706"

# -- fonts --------------------------------------------------------------------
FAMILY = "Segoe UI" if sys.platform.startswith("win") else "Helvetica"
MONO_FAMILY = "Consolas" if sys.platform.startswith("win") else "Courier"

F_BASE = (FAMILY, 10)
F_SMALL = (FAMILY, 9)
F_TINY = (FAMILY, 8)
F_BOLD = (FAMILY, 10, "bold")
F_SMALL_BOLD = (FAMILY, 9, "bold")
F_TITLE = (FAMILY, 12, "bold")
F_SECTION = (FAMILY, 9, "bold")
F_KPI = (FAMILY, 26, "bold")
F_APP = (FAMILY, 15, "bold")
F_MONO = (MONO_FAMILY, 10)


def apply(root):
    """Configure fonts and ttk styles for the whole application."""
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
        try:
            tkfont.nametofont(name).configure(family=FAMILY, size=10)
        except tk.TclError:
            pass
    root.configure(bg=PAGE)

    s = ttk.Style(root)
    s.theme_use("clam")

    s.configure(".", background=CARD, foreground=INK, font=F_BASE,
                bordercolor=LINE, lightcolor=CARD, darkcolor=CARD,
                troughcolor=SUBTLE, focuscolor=ACCENT_SOFT, selectbackground=ACCENT_SOFT,
                selectforeground=INK, insertcolor=INK)

    # frames and labels
    s.configure("TFrame", background=CARD)
    s.configure("Page.TFrame", background=PAGE)
    s.configure("TLabel", background=CARD, foreground=INK)
    s.configure("Muted.TLabel", background=CARD, foreground=MUTED, font=F_SMALL)
    s.configure("Page.TLabel", background=PAGE, foreground=MUTED, font=F_SMALL)
    s.configure("KpiCaption.TLabel", background=CARD, foreground=MUTED, font=F_SECTION)
    s.configure("Kpi.TLabel", background=CARD, foreground=INK, font=F_KPI)
    s.configure("Code.TLabel", background=CARD, foreground=FAINT, font=F_SMALL)

    # cards: section title on the page, white panel with a thin border below it
    s.configure("Card.TFrame", background=CARD, bordercolor=LINE, lightcolor=LINE,
                darkcolor=LINE, relief="solid", borderwidth=1)
    s.configure("Section.TLabel", background=PAGE, foreground=MUTED, font=F_SECTION)

    # buttons
    s.configure("TButton", background="#f1f5f9", foreground=INK, bordercolor="#cbd5e1",
                lightcolor="#f1f5f9", darkcolor="#f1f5f9", relief="raised", borderwidth=1,
                padding=(12, 6), focusthickness=0, focuscolor="#f1f5f9")
    s.map("TButton",
          background=[("pressed", "#cbd5e1"), ("active", "#e2e8f0")],
          lightcolor=[("pressed", "#cbd5e1"), ("active", "#e2e8f0")],
          darkcolor=[("pressed", "#cbd5e1"), ("active", "#e2e8f0")],
          bordercolor=[("active", FAINT)])
    s.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", bordercolor=ACCENT,
                lightcolor=ACCENT, darkcolor=ACCENT, font=F_BOLD, focuscolor=ACCENT)
    s.map("Accent.TButton",
          background=[("pressed", ACCENT_DARK), ("active", ACCENT_DARK)],
          bordercolor=[("active", ACCENT_DARK)],
          lightcolor=[("active", ACCENT_DARK)], darkcolor=[("active", ACCENT_DARK)])

    # inputs
    s.configure("TEntry", fieldbackground=CARD, foreground=INK, bordercolor=LINE,
                lightcolor=CARD, darkcolor=CARD, padding=(6, 3))
    s.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT_SOFT)])
    for w in ("TRadiobutton", "TCheckbutton"):
        s.configure(w, background=CARD, foreground=INK, indicatorbackground=CARD,
                    indicatorforeground=CARD, upperbordercolor=FAINT, lowerbordercolor=FAINT,
                    indicatormargin=(0, 0, 6, 0), padding=(2, 3), focuscolor=CARD)
        s.map(w,
              indicatorbackground=[("selected", ACCENT), ("active", ACCENT_SOFT)],
              upperbordercolor=[("selected", ACCENT)], lowerbordercolor=[("selected", ACCENT)],
              background=[("active", CARD)])

    # tables
    s.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=INK,
                bordercolor=LINE, lightcolor=CARD, darkcolor=CARD, rowheight=26, borderwidth=0)
    s.map("Treeview", background=[("selected", ACCENT_SOFT)], foreground=[("selected", INK)])
    s.configure("Treeview.Heading", background=SUBTLE, foreground=MUTED, font=F_SMALL_BOLD,
                relief="flat", bordercolor=LINE, lightcolor=SUBTLE, darkcolor=SUBTLE, padding=(8, 6))
    s.map("Treeview.Heading", background=[("active", "#eef2f7")])

    # scrollbars
    for orient in ("Vertical", "Horizontal"):
        s.configure(f"{orient}.TScrollbar", background="#cbd5e1", troughcolor=CARD,
                    bordercolor=CARD, lightcolor="#cbd5e1", darkcolor="#cbd5e1",
                    arrowcolor=MUTED, gripcount=0, arrowsize=12)
        s.map(f"{orient}.TScrollbar", background=[("active", FAINT)])

    # notebook = dark tab bar under the header
    s.configure("TNotebook", background=HEADER, bordercolor=HEADER, lightcolor=HEADER,
                darkcolor=HEADER, borderwidth=0, tabmargins=(16, 0, 16, 0))
    s.configure("TNotebook.Tab", background=HEADER, foreground=HEADER_MUTED, padding=(20, 10),
                bordercolor=HEADER, lightcolor=HEADER, darkcolor=HEADER, font=F_BOLD,
                focuscolor=HEADER)
    s.map("TNotebook.Tab",
          background=[("selected", PAGE), ("active", HEADER_2)],
          foreground=[("selected", INK), ("active", HEADER_TEXT)],
          bordercolor=[("selected", PAGE)], lightcolor=[("selected", PAGE)],
          expand=[("selected", (0, 0, 0, 0))])
    return s


def header(root, title, subtitle, right_text):
    """Dark app header above the tab bar."""
    bar = tk.Frame(root, bg=HEADER, padx=20, pady=12)
    logo = tk.Canvas(bar, width=28, height=28, bg=HEADER, highlightthickness=0)
    round_rect(logo, 2, 2, 26, 26, r=7, fill=ACCENT, outline="")
    logo.create_polygon(14, 7, 21, 14, 14, 21, 7, 14, fill="#ffffff", outline="")
    logo.pack(side="left", padx=(0, 12))
    tk.Label(bar, text=title, bg=HEADER, fg=HEADER_TEXT, font=F_APP).pack(side="left")
    tk.Label(bar, text=subtitle, bg=HEADER, fg=HEADER_MUTED, font=F_BASE).pack(side="left", padx=(14, 0))
    tk.Label(bar, text=right_text, bg=HEADER, fg=HEADER_MUTED, font=F_SMALL,
             justify="right").pack(side="right")
    return bar


def style_canvas(canvas):
    canvas.configure(background=CARD, highlightthickness=1, highlightbackground=LINE,
                     highlightcolor=LINE)


def style_toplevel(win):
    win.configure(bg=CARD)


def round_rect(canvas, x0, y0, x1, y1, r=8, **kw):
    """Rounded rectangle as a smoothed polygon (clickable, exportable to .eps)."""
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
           x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return canvas.create_polygon(pts, smooth=True, **kw)


class Card(ttk.Frame):
    """A white card with a section title above it.

    Drop-in replacement for ttk.LabelFrame: children are added to the card
    itself, pack()/grid() place the whole card, and config(text=...) changes
    the title.
    """

    def __init__(self, parent, text="", padding=12, **kw):
        self._outer = ttk.Frame(parent, style="Page.TFrame")
        self._title = ttk.Label(self._outer, text=text, style="Section.TLabel")
        self._title.pack(anchor="w", pady=(0, 6))
        super().__init__(self._outer, style="Card.TFrame", padding=padding, **kw)
        ttk.Frame.pack_configure(self, fill="both", expand=True)

    def pack_configure(self, *a, **kw):
        return self._outer.pack_configure(*a, **kw)
    pack = pack_configure

    def grid_configure(self, *a, **kw):
        return self._outer.grid_configure(*a, **kw)
    grid = grid_configure

    def configure(self, cnf=None, **kw):
        if cnf and "text" in cnf:
            cnf = dict(cnf)
            kw["text"] = cnf.pop("text")
        if "text" in kw:
            self._title.configure(text=kw.pop("text"))
            if not kw and not cnf:
                return None
        return super().configure(cnf, **kw)
    config = configure


_font_cache = {}


def fit_font(text, max_width, size=9, bold=True, min_size=8):
    """Largest font (down to min_size) in which text fits max_width pixels."""
    for sz in range(size, min_size - 1, -1):
        key = (sz, bold)
        if key not in _font_cache:
            _font_cache[key] = tkfont.Font(family=FAMILY, size=sz, weight="bold" if bold else "normal")
        if _font_cache[key].measure(text) <= max_width:
            return (FAMILY, sz, "bold") if bold else (FAMILY, sz)
    return (FAMILY, min_size, "bold") if bold else (FAMILY, min_size)
