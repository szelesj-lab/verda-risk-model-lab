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
F_KPI = (FAMILY, 22, "bold")
F_APP = (FAMILY, 13, "bold")
F_MONO = (MONO_FAMILY, 10)


# -- high-DPI support ---------------------------------------------------------
S = 1.0   # UI scale factor: 1.0 at 96 dpi (100 %), 1.5 at 144 dpi (150 %)


def enable_dpi_awareness():
    """Ask Windows to let us draw at the real resolution (sharp, not stretched).

    Must run before the Tk window is created. Does nothing on other systems.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)      # system DPI aware
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def px(v):
    """Scale a pixel distance designed at 100 % to the current display."""
    return int(round(v * S))


def pxs(v):
    """Scale an int or a tuple of pixel distances (paddings)."""
    if isinstance(v, (tuple, list)):
        return tuple(px(x) for x in v)
    return px(v)


def apply(root):
    """Configure fonts and ttk styles for the whole application."""
    global S
    try:
        S = max(1.0, root.winfo_fpixels("1i") / 96.0)
    except tk.TclError:
        S = 1.0
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
    s.configure("TPanedwindow", background=PAGE)
    s.configure("Sash", sashthickness=px(10), gripcount=0, background=PAGE, bordercolor=PAGE,
                lightcolor=PAGE, darkcolor=PAGE, handlesize=0)

    # buttons
    s.configure("TButton", background="#f1f5f9", foreground=INK, bordercolor="#cbd5e1",
                lightcolor="#f1f5f9", darkcolor="#f1f5f9", relief="raised", borderwidth=1,
                padding=pxs((10, 4)), focusthickness=0, focuscolor="#f1f5f9")
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
                lightcolor=CARD, darkcolor=CARD, padding=pxs((6, 2)))
    s.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT_SOFT)])
    for w in ("TRadiobutton", "TCheckbutton"):
        s.configure(w, background=CARD, foreground=INK, indicatorbackground=CARD,
                    indicatorforeground=CARD, upperbordercolor=FAINT, lowerbordercolor=FAINT,
                    indicatormargin=pxs((0, 0, 5, 0)), padding=pxs((2, 1)), focuscolor=CARD,
                    indicatorsize=px(12))
        s.map(w,
              indicatorbackground=[("selected", ACCENT), ("active", ACCENT_SOFT)],
              upperbordercolor=[("selected", ACCENT)], lowerbordercolor=[("selected", ACCENT)],
              background=[("active", CARD)])

    # tables
    s.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=INK,
                bordercolor=LINE, lightcolor=CARD, darkcolor=CARD, rowheight=px(26), borderwidth=0)
    s.map("Treeview", background=[("selected", ACCENT_SOFT)], foreground=[("selected", INK)])
    s.configure("Treeview.Heading", background=SUBTLE, foreground=MUTED, font=F_SMALL_BOLD,
                relief="flat", bordercolor=LINE, lightcolor=SUBTLE, darkcolor=SUBTLE, padding=pxs((8, 6)))
    s.map("Treeview.Heading", background=[("active", "#eef2f7")])

    # scrollbars
    for orient in ("Vertical", "Horizontal"):
        s.configure(f"{orient}.TScrollbar", background="#cbd5e1", troughcolor=CARD,
                    bordercolor=CARD, lightcolor="#cbd5e1", darkcolor="#cbd5e1",
                    arrowcolor=MUTED, gripcount=0, arrowsize=px(12))
        s.map(f"{orient}.TScrollbar", background=[("active", FAINT)])

    # notebook = dark tab bar under the header
    s.configure("TNotebook", background=HEADER, bordercolor=HEADER, lightcolor=HEADER,
                darkcolor=HEADER, borderwidth=0, tabmargins=(16, 0, 16, 0))
    s.configure("TNotebook.Tab", background=HEADER, foreground=HEADER_MUTED, padding=pxs((16, 7)),
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
    bar = tk.Frame(root, bg=HEADER, padx=px(16), pady=px(7))
    k = S
    logo = tk.Canvas(bar, width=px(24), height=px(24), bg=HEADER, highlightthickness=0)
    round_rect(logo, 1, 1, 23 * k, 23 * k, r=6 * k, fill=ACCENT, outline="")
    logo.create_polygon(12 * k, 6 * k, 18 * k, 12 * k, 12 * k, 18 * k, 6 * k, 12 * k,
                        fill="#ffffff", outline="")
    logo.pack(side="left", padx=(0, px(10)))
    tk.Label(bar, text=title, bg=HEADER, fg=HEADER_TEXT, font=F_APP).pack(side="left")
    tk.Label(bar, text=subtitle, bg=HEADER, fg=HEADER_MUTED, font=F_BASE).pack(side="left", padx=(px(14), 0))
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
        self._title.pack(anchor="w", pady=(0, px(4)))
        super().__init__(self._outer, style="Card.TFrame", padding=pxs(padding), **kw)
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


def fit_font(text, max_width, size=9, bold=True, min_size=7):
    """Largest font (down to min_size) in which text fits max_width pixels."""
    for sz in range(size, min_size - 1, -1):
        key = (sz, bold)
        if key not in _font_cache:
            _font_cache[key] = tkfont.Font(family=FAMILY, size=sz, weight="bold" if bold else "normal")
        if _font_cache[key].measure(text) <= max_width:
            return (FAMILY, sz, "bold") if bold else (FAMILY, sz)
    return (FAMILY, min_size, "bold") if bold else (FAMILY, min_size)


class ScrollPanel(ttk.Frame):
    """A column that scrolls vertically when it is taller than the window.

    Put children into .body. The scrollbar only appears when needed.
    """

    def __init__(self, parent, width=None, **kw):
        super().__init__(parent, style="Page.TFrame", **kw)
        self._canvas = tk.Canvas(self, bg=PAGE, highlightthickness=0, bd=0)
        self._bar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._bar.set)
        self.body = ttk.Frame(self._canvas, style="Page.TFrame")
        self._win = self._canvas.create_window(0, 0, window=self.body, anchor="nw")
        self._canvas.pack(side="left", fill="both", expand=True)
        self.body.bind("<Configure>", self._on_body)
        self._canvas.bind("<Configure>", self._on_canvas)
        for w in (self._canvas, self.body):
            w.bind("<Enter>", lambda e: self._bind_wheel(True))
            w.bind("<Leave>", lambda e: self._bind_wheel(False))

    def _on_body(self, _e=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"),
                               width=self.body.winfo_reqwidth())
        self._update_bar()

    def _on_canvas(self, e):
        self._canvas.itemconfigure(self._win, width=e.width)
        self._update_bar()

    def _update_bar(self):
        need = self.body.winfo_reqheight() > self._canvas.winfo_height() > 1
        if need and not self._bar.winfo_ismapped():
            self._bar.pack(side="right", fill="y", before=self._canvas)
        elif not need and self._bar.winfo_ismapped():
            self._bar.pack_forget()
            self._canvas.yview_moveto(0)

    def _bind_wheel(self, on):
        if on:
            self._canvas.bind_all("<MouseWheel>", self._wheel)
            self._canvas.bind_all("<Button-4>", lambda e: self._scroll(-1))
            self._canvas.bind_all("<Button-5>", lambda e: self._scroll(1))
        else:
            self._canvas.unbind_all("<MouseWheel>")
            self._canvas.unbind_all("<Button-4>")
            self._canvas.unbind_all("<Button-5>")

    def _wheel(self, e):
        self._scroll(-1 if e.delta > 0 else 1)

    def _scroll(self, step):
        if self._bar.winfo_ismapped():
            self._canvas.yview_scroll(step * 2, "units")


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def fits(text, font):
    """True if text fits in one line in the given (family, size[, 'bold']) font."""
    key = (font[1], len(font) > 2)
    if key not in _font_cache:
        _font_cache[key] = tkfont.Font(family=FAMILY, size=font[1],
                                       weight="bold" if len(font) > 2 else "normal")
    return _font_cache[key]


def label_font(text, max_width, size=9):
    """Font and wrap width for a box label: shrink first, then wrap at spaces."""
    font = fit_font(text, max_width, size=size)
    if fits(text, font).measure(text) <= max_width:
        return font, 0
    words = text.split()
    if len(words) > 1:
        longest = max(words, key=len)
        font = fit_font(longest, max_width, size=size)
        if fits(longest, font).measure(longest) <= max_width:
            return font, max_width
    return fit_font(text, max_width, size=size), 0
