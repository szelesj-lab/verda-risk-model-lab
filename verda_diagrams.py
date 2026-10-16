"""
Graphical views for the VERDA Risk Model Lab.

Developer: József Szeles, Department of System Engineering, University of Pannonia

FaultTreeDiagram - the fault tree with AND/OR gate symbols. Basic events are
                   shaded by Fussell-Vesely importance; selecting a cut set
                   highlights its events and the path to the top event.
BayesDiagram     - the Bayesian network. Node colour shows how far the current
                   probability moved from the baseline; clicking a node cycles
                   its evidence: unknown -> yes -> no -> unknown.

Both views redraw automatically when the other tabs change, and both can be
saved as a vector image (.eps) for slides or reports.
"""

import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import verda_model as vm
import verda_theme as th
from verda_theme import round_rect

FONT = th.F_SMALL
FONT_B = th.F_SMALL_BOLD
FONT_T = th.F_TITLE
INK, QUIET, EDGE = th.INK, th.MUTED, th.FAINT
HILITE = th.ACCENT

FTA_SHORT = {
    "TOP": "Unsafe release", "CONTAM": "Contamination", "QCFAIL": "QC fails to detect",
    "PRES": "Poor preservation", "HOT": "Added above 40 C", "NOZZLE": "Nozzle contam.",
    "B1": "Under-weighed", "B2": "Material swapped", "B3": "Probe reads low",
    "B4": "No cross-check", "B5": "pH not corrected", "B6": "Sanitation skipped",
    "B7": "Sanitiser bad", "B8": "Bad sample", "B9": "Released early",
    "B10": "False pass",
}

BN_SHORT = {
    "TP": "Time pressure", "DI": "Instructions down", "PF": "Probe fault",
    "B1": "Under-weighed", "B2": "Material swap", "B4": "No cross-check",
    "HOT": "Added hot", "B5": "pH not fixed", "PRES": "Poor preservation",
    "SS": "Sanitation skipped", "B7": "Sanitiser bad", "NOZZLE": "Nozzle contam.",
    "C": "Contamination", "RB": "Released early", "B8": "Bad sample",
    "B10": "False pass", "QM": "QC misses it", "U": "Unsafe release",
}

# (column fraction of width, row) for each BN node
BN_LAYOUT = {
    "PF": (0.225, 0), "DI": (0.33, 0), "TP": (0.70, 0),
    "B1": (0.06, 1), "B2": (0.17, 1), "B4": (0.28, 1), "B5": (0.39, 1), "SS": (0.50, 1),
    "B7": (0.61, 1), "RB": (0.72, 1), "B8": (0.83, 1), "B10": (0.94, 1),
    "HOT": (0.225, 2),
    "PRES": (0.20, 3), "NOZZLE": (0.55, 3), "QM": (0.83, 3),
    "C": (0.38, 4),
    "U": (0.60, 5),
}


def mix(c1, c2, t):
    """Blend two #rrggbb colours, t in [0, 1]."""
    t = max(0.0, min(1.0, t))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def save_eps(canvas, parent, name):
    path = filedialog.asksaveasfilename(parent=parent, defaultextension=".eps",
                                        initialfile=name, filetypes=[("EPS image", "*.eps")])
    if path:
        canvas.update()
        canvas.postscript(file=path, colormode="color",
                          width=canvas.winfo_width(), height=canvas.winfo_height())
        messagebox.showinfo("Saved", f"Diagram saved to\n{path}", parent=parent)


class FaultTreeDiagram(ttk.Frame):
    BOX_W, BOX_H = 118, 50

    def __init__(self, master, app):
        super().__init__(master, padding=0, style="Page.TFrame")
        self.app = app
        self.selected_cut = set()
        self.selected_event = None
        self._pending = None

        pane = ttk.Panedwindow(self, orient="vertical")
        pane.pack(fill="both", expand=True)
        top = ttk.Frame(pane, style="Page.TFrame")
        self.canvas = tk.Canvas(top, height=200)
        th.style_canvas(self.canvas)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.schedule_draw())
        self.canvas.tag_bind("event", "<Button-1>", self.on_click)

        bottom = ttk.Frame(pane, style="Page.TFrame")
        cutf = th.Card(bottom, text="MINIMAL CUT SETS  \u00b7  CLICK TO HIGHLIGHT", padding=8)
        cutf.pack(side="left", fill="both")
        self.cuts = tk.Listbox(cutf, height=6, width=34, font=th.F_MONO, activestyle="none",
                               exportselection=False, relief="flat", highlightthickness=0,
                               bg=th.CARD, fg=th.INK, selectbackground=th.ACCENT_SOFT,
                               selectforeground=th.ACCENT_DARK)
        sb = ttk.Scrollbar(cutf, command=self.cuts.yview)
        self.cuts.configure(yscrollcommand=sb.set)
        self.cuts.pack(side="left", fill="both")
        sb.pack(side="left", fill="y")
        self.cuts.bind("<<ListboxSelect>>", self.on_cut)
        infof = th.Card(bottom, text="SELECTED EVENT  \u00b7  CLICK A BASIC EVENT IN THE DIAGRAM",
                        padding=8)
        infof.pack(side="left", fill="both", expand=True, padx=12)
        self.info = tk.Text(infof, height=6, width=30, font=th.F_BASE, wrap="word", background=th.CARD,
                            foreground=th.INK, relief="flat", highlightthickness=0, padx=4, pady=2)
        self.info.pack(fill="both", expand=True)
        btns = ttk.Frame(bottom, style="Page.TFrame")
        btns.pack(side="left", fill="y", pady=(th.px(22), 0))
        ttk.Button(btns, text="Clear highlight", command=self.clear_highlight).pack(fill="x")
        ttk.Button(btns, text="Save diagram (.eps)",
                   command=lambda: save_eps(self.canvas, self, "verda_fault_tree.eps")).pack(fill="x", pady=6)

        pane.add(top, weight=1)
        pane.add(bottom, weight=0)
        self.cut_rows = []

    def schedule_draw(self):
        """Redraw once after a burst of resize events (keeps dragging smooth)."""
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(40, self._draw_now)

    def _draw_now(self):
        self._pending = None
        self.draw()

    # -- data -------------------------------------------------------------
    def probabilities(self):
        fta = getattr(self.app, "fta", None)
        if fta is None:
            return vm.default_fta_probabilities()
        try:
            return fta.probabilities()
        except ValueError:
            return vm.default_fta_probabilities()

    def refresh(self):
        p = self.probabilities()
        self.cut_rows = vm.ranked_cut_sets(p)
        q = vm.top_probability(p)
        self.cuts.delete(0, "end")
        for cs, pr in self.cut_rows:
            share = pr / q if q > 0 else 0
            self.cuts.insert("end", f"{' . '.join(cs):<16}{pr:.6f} {share:5.1%}")
        self.draw()
        self.show_info()

    # -- layout -----------------------------------------------------------
    def layout(self, width):
        """Leaves get evenly spaced columns; each gate sits above its children."""
        order, depth = [], {}

        def walk(n, d):
            depth[n] = d
            if n in vm.GATES:
                for c in vm.GATES[n][1]:
                    walk(c, d + 1)
            else:
                order.append(n)

        walk("TOP", 0)
        k = th.S
        slot = (width - 32 * k) / max(len(order), 1)
        self.box_w = th.clamp(slot - 8 * k, 56 * k, self.BOX_W * k)
        margin = 16 * k + slot / 2
        step = (width - 2 * margin) / max(len(order) - 1, 1)
        x = {leaf: margin + i * step for i, leaf in enumerate(order)}

        def place(n):
            if n in vm.GATES:
                xs = [place(c) for c in vm.GATES[n][1]]
                x[n] = sum(xs) / len(xs)
            return x[n]

        place("TOP")
        return x, depth

    def ancestors(self, events):
        parent = {c: g for g, (_, cs, _) in vm.GATES.items() for c in cs}
        out = set()
        for e in events:
            while e in parent:
                e = parent[e]
                out.add(e)
        return out

    # -- drawing ----------------------------------------------------------
    def gate_symbol(self, kind, cx, cy, colour, r=13):
        c = self.canvas
        k = r / 13
        if kind == "AND":
            pts = [cx - r, cy + 10 * k]
            for i in range(0, 181, 15):
                a = math.radians(180 - i)
                pts += [cx + r * math.cos(a), cy - r * math.sin(a) + 2 * k]
            pts += [cx + r, cy + 10 * k]
            c.create_polygon(pts, fill=th.CARD, outline=colour, width=1.5 * th.S)
        else:
            c.create_polygon(cx - r, cy + 10 * k, cx, cy + 4 * k, cx + r, cy + 10 * k, cx + r - 2 * k, cy - 2 * k,
                             cx, cy - 14 * k, cx - r + 2 * k, cy - 2 * k, smooth=True,
                             fill=th.CARD, outline=colour, width=1.5 * th.S)
        if r >= 10 * th.S:
            c.create_text(cx, cy + 3 * k, text=kind, font=(th.FAMILY, 6, "bold"), fill=colour)

    def draw(self):
        c = self.canvas
        c.delete("all")
        p = self.probabilities()
        g = vm.gate_probabilities(p)
        fv = {r["event"]: r["fussell_vesely"] for r in vm.importance(p)}
        k = th.S
        w = max(c.winfo_width(), 400 * k)
        h = max(c.winfo_height(), 260 * k)
        x, depth = self.layout(w)
        levels = max(depth.values()) + 1
        compact = h < 430 * k
        y0 = (62 if compact else 84) * k
        bottom = (40 if compact else 52) * k
        row = (h - y0 - bottom) / max(levels - 1, 1)
        bh = th.clamp(row * 0.45, 26 * k, self.BOX_H * k)
        y0 += bh / 2 - 22 * k
        Y = lambda n: y0 + depth[n] * row
        hl = self.selected_cut | self.ancestors(self.selected_cut)
        bw = self.box_w
        q = g["TOP"]
        gap = row - bh
        sym_r = th.clamp(gap * 0.2, 6 * k, 13 * k)
        lw, lw_hi = 1.2 * k, 2.5 * k

        c.create_text(20 * k, 20 * k, anchor="w", font=FONT_T, fill=INK,
                      text=f"Fault tree: P(unsafe batch released) = {q:.5f} per batch"
                           + (f"  (about 1 in {1 / q:,.0f})" if q > 0 else ""))
        if not compact:
            c.create_text(20 * k, 42 * k, anchor="w", font=FONT, fill=QUIET,
                          text="Basic events shaded by Fussell-Vesely importance. "
                               "Click an event for details; pick a cut set below to highlight it.")

        # connectors first, so boxes sit on top
        for gate, (kind, children, _) in vm.GATES.items():
            gx, gy = x[gate], Y(gate)
            sym_y = gy + bh / 2 + gap * 0.32
            bus_y = gy + bh / 2 + gap * 0.66
            col = HILITE if gate in hl else EDGE
            wid = lw_hi if gate in hl else lw
            c.create_line(gx, gy + bh / 2, gx, sym_y - sym_r, fill=col, width=wid)
            c.create_line(gx, sym_y + sym_r * 0.8, gx, bus_y, fill=col, width=wid)
            xs = [x[ch] for ch in children]
            c.create_line(min(xs), bus_y, max(xs), bus_y, fill=EDGE, width=lw, capstyle="round")
            for ch in children:
                on = ch in hl and gate in hl
                c.create_line(x[ch], bus_y, x[ch], Y(ch) - bh / 2,
                              fill=HILITE if on else EDGE, width=lw_hi if on else lw)
            if gate in hl:
                hx = [x[ch] for ch in children if ch in hl] + [gx]
                c.create_line(min(hx), bus_y, max(hx), bus_y, fill=HILITE, width=lw_hi)
            self.gate_symbol(kind, gx, sym_y, col, sym_r)

        two_lines = bh >= 34 * k
        name_size = 9 if bh >= 40 * k else 8
        for n in x:
            cx, cy = x[n], Y(n)
            is_gate = n in vm.GATES
            on = n in hl
            if is_gate:
                fill = th.ACCENT_SOFT if n == "TOP" else "#f1f5f9"
                sub = f"{vm.GATES[n][0]}  {g[n]:.5f}"
            else:
                fill = mix("#ffffff", th.RISK_FILL, 0.9 * math.sqrt(fv.get(n, 0)))
                sub = f"{n}  p={p[n]:g}"
            sel = on or n == self.selected_event
            outline = HILITE if sel else ("#94a3b8" if is_gate else "#cbd5e1")
            tags = ("node", n) if is_gate else ("node", "event", n)
            bw = min(self.box_w * 1.45, (self.BOX_W + 12) * k) if is_gate else self.box_w
            round_rect(c, cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2, r=min(10 * k, bh / 3),
                       fill=fill, outline=outline, width=lw_hi if sel else lw, tags=tags)
            name_font, wrap = th.label_font(FTA_SHORT[n], bw - 8 * k, size=name_size)
            if two_lines and not wrap:
                c.create_text(cx, cy - bh * 0.17, text=FTA_SHORT[n], font=name_font, fill=INK, tags=tags)
                c.create_text(cx, cy + bh * 0.2, text=sub, font=th.fit_font(sub, bw - 8 * k, size=9, bold=False),
                              fill=INK if is_gate else QUIET, tags=tags)
            else:
                c.create_text(cx, cy, text=FTA_SHORT[n], font=name_font, fill=INK, tags=tags,
                              width=wrap or 0, justify="center")

        # legend
        lx, ly = 20 * k, h - 22 * k
        c.create_text(lx, ly, anchor="w", font=FONT, fill=QUIET, text="Importance:")
        for i in range(6):
            round_rect(c, lx + (80 + i * 22) * k, ly - 7 * k, lx + (100 + i * 22) * k, ly + 7 * k, r=4 * k,
                       fill=mix("#ffffff", th.RISK_FILL, 0.9 * math.sqrt(i / 5)), outline="#cbd5e1")
        if w > 620 * k:
            c.create_text(lx + 228 * k, ly, anchor="w", font=FONT, fill=QUIET,
                          text="(low to high).   Gates assume independent events. All values illustrative.")

    # -- interaction ------------------------------------------------------
    def on_click(self, event):
        item = self.canvas.find_withtag("current")
        if not item:
            return
        tags = self.canvas.gettags(item[0])
        ev = next((t for t in tags if t in vm.BASIC_EVENTS), None)
        if ev:
            self.selected_event = ev
            self.draw()
            self.show_info()
            fta = getattr(self.app, "fta", None)
            if fta is not None and hasattr(fta, "focus_event"):
                fta.focus_event(ev)

    def on_cut(self, _event):
        sel = self.cuts.curselection()
        if sel:
            self.selected_cut = set(self.cut_rows[sel[0]][0])
            self.draw()

    def clear_highlight(self):
        self.selected_cut = set()
        self.selected_event = None
        self.cuts.selection_clear(0, "end")
        self.draw()
        self.show_info()

    def show_info(self):
        self.info.delete("1.0", "end")
        e = self.selected_event
        if not e:
            self.info.insert("1.0", "Click a basic event in the diagram.")
            return
        p = self.probabilities()
        desc, layer, _ = vm.BASIC_EVENTS[e]
        imp = next(r for r in vm.importance(p) if r["event"] == e)
        cuts = [" . ".join(cs) for cs, _ in self.cut_rows if e in cs]
        self.info.insert("1.0",
                         f"{e}: {desc}   |   Layer: {layer}   |   Probability: {p[e]:g} per batch\n\n"
                         f"Fussell-Vesely: {imp['fussell_vesely']:.3f}  "
                         f"(share of top-event risk that involves {e})\n"
                         f"Birnbaum: {imp['birnbaum']:.5f}  "
                         f"(top-event change if {e} goes from never to certain)\n\n"
                         f"In cut sets: {', '.join(cuts)}\n\n"
                         f"Edit its probability in the field on the left (now selected).")


class BayesDiagram(ttk.Frame):
    BOX_W, BOX_H = 112, 50
    CYCLE = {"unknown": "yes", "yes": "no", "no": "unknown"}

    def __init__(self, master, app):
        super().__init__(master, padding=0, style="Page.TFrame")
        self.app = app
        self.selected = "SS"
        bar = ttk.Frame(self, style="Page.TFrame")
        bar.pack(fill="x")
        ttk.Label(bar, text="Left-click a node: select it and edit its table below.   "
                            "Right-click a node: cycle its evidence (unknown \u2192 yes \u2192 no).",
                  style="Page.TLabel").pack(side="left")
        ttk.Button(bar, text="Save diagram (.eps)",
                   command=lambda: save_eps(self.canvas, self, "verda_bayes_net.eps")).pack(side="right")

        pane = ttk.Panedwindow(self, orient="vertical")
        pane.pack(fill="both", expand=True, pady=(8, 0))
        top = ttk.Frame(pane, style="Page.TFrame")
        self.canvas = tk.Canvas(top, height=200)
        th.style_canvas(self.canvas)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.schedule_draw())
        self.canvas.tag_bind("node", "<Button-1>", self.on_select)
        self.canvas.tag_bind("node", "<Button-3>", self.on_cycle)
        self.canvas.tag_bind("node", "<Button-2>", self.on_cycle)   # macOS right button
        self._pending = None

        bottom = ttk.Frame(pane, style="Page.TFrame")
        self.extra = th.Card(bottom, text="COMPARE OPTIONS  \u00b7  SAME EVIDENCE",
                             padding=10)
        self.extra.pack(side="right", fill="both", padx=(12, 0))
        self.panel = th.Card(bottom, text="SELECTED NODE", padding=(12, 8))
        self.panel.pack(side="left", fill="both", expand=True)
        pane.add(top, weight=1)
        pane.add(bottom, weight=0)

    def schedule_draw(self):
        """Redraw once after a burst of resize events (keeps dragging smooth)."""
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(40, self._draw_now)

    def _draw_now(self):
        self._pending = None
        self.draw()

    # -- interaction ------------------------------------------------------
    def refresh(self):
        self.draw()
        self.show_node()

    def clear(self):
        self.app.bayes.clear()

    def node_at_cursor(self):
        item = self.canvas.find_withtag("current")
        if not item:
            return None
        return next((t for t in self.canvas.gettags(item[0]) if t in BN_LAYOUT), None)

    def on_select(self, _event):
        node = self.node_at_cursor()
        if node:
            self.selected = node
            self.draw()
            self.show_node()

    def on_cycle(self, _event):
        node = self.node_at_cursor()
        if node:
            self.selected = node
            self.set_evidence(node, self.CYCLE[self.app.bayes.get_state(node)])

    def set_evidence(self, node, state):
        bt = self.app.bayes
        old = bt.get_state(node)
        bt.set_state(node, state)
        if not bt.calculate():          # impossible evidence: undo
            bt.set_state(node, old)
            bt.calculate()

    # -- CPT panel --------------------------------------------------------
    def show_node(self):
        bt = getattr(self.app, "bayes", None)
        if bt is None or not hasattr(bt, "last"):
            return
        for w in self.panel.winfo_children():
            w.destroy()
        n = self.selected
        prior, post, ev, opts = bt.last
        parents = {nd["name"]: nd["parents"] for nd in vm.build_bn(bt.params)}[n]
        self.panel.config(text=f"SELECTED NODE  \u00b7  {n}  {vm.BN_LABELS[n].upper()}")

        # left column: summary and evidence
        info = ttk.Frame(self.panel)
        info.pack(side="left", fill="y", padx=(0, 12))
        kind = ("root cause (no parents)" if not parents else
                f"logic node: {vm.DET_LOGIC[n]} of its parents" if n in vm.DET_LOGIC else
                "probabilistic node")
        ttk.Label(info, text=f"Type: {kind}", style="Muted.TLabel", wraplength=th.px(190)).pack(anchor="w")
        ttk.Label(info, text="Parents: " + (", ".join(f"{p} ({BN_SHORT[p]})" for p in parents)
                                            if parents else "none"), style="Muted.TLabel",
                  wraplength=th.px(190), justify="left").pack(anchor="w")
        ttk.Label(info, text=f"P(yes) now: {post[n]:.5f}", font=th.F_BOLD).pack(anchor="w", pady=(4, 0))
        ttk.Label(info, text=f"without evidence: {prior[n]:.5f}", style="Muted.TLabel").pack(anchor="w", pady=(0, 4))
        evrow = ttk.Frame(info)
        evrow.pack(anchor="w")
        ttk.Label(evrow, text="Evidence:").pack(side="left")
        var = tk.StringVar(value=bt.get_state(n))
        for s in ("unknown", "yes", "no"):
            ttk.Radiobutton(evrow, text=s, value=s, variable=var,
                            command=lambda: self.set_evidence(n, var.get())).pack(side="left", padx=3)

        # right column: the table
        tab = ttk.Frame(self.panel)
        tab.pack(side="left", fill="both", expand=True)
        if n in vm.DET_LOGIC:
            rule = "all parents are yes" if vm.DET_LOGIC[n] == "AND" else "at least one parent is yes"
            ttk.Label(tab, text=f"This is a logic ({vm.DET_LOGIC[n]}) node, so its table is fixed:\n"
                                f"P(yes) = 1 if {rule}, otherwise 0.\n\n"
                                "To change the risk here, edit the tables of its parent nodes.",
                      foreground=QUIET, justify="left").pack(anchor="w")
            return

        keys = vm.CPT_KEYS[n]
        cols = [f"{p}" for p in parents] + ["P(yes)", "P(no)"]
        for j, title in enumerate(cols):
            ttk.Label(tab, text=title, font=FONT_B, width=7 if j < len(parents) else 8,
                      anchor="w").grid(row=0, column=j, sticky="w", padx=2)
        self.cpt_vars = {}
        self.cpt_no = {}
        for i, (combo, key) in enumerate(keys.items(), start=1):
            for j, val in enumerate(combo):
                ttk.Label(tab, text="yes" if val else "no").grid(row=i, column=j, sticky="w", padx=2)
            v = tk.StringVar(value=f"{bt.params[key]:g}")
            e = ttk.Entry(tab, textvariable=v, width=8, justify="right")
            e.grid(row=i, column=len(parents), sticky="w", padx=2, pady=0)
            e.bind("<Return>", lambda _e: self.apply_cpt())
            v.trace_add("write", lambda *_a, k=key: self.update_no(k))
            no = ttk.Label(tab, text=f"{1 - bt.params[key]:g}", style="Muted.TLabel")
            no.grid(row=i, column=len(parents) + 1, sticky="w", padx=2)
            ttk.Label(tab, text=key, style="Code.TLabel").grid(row=i, column=len(parents) + 2,
                                                                 sticky="w", padx=(8, 0))
            self.cpt_vars[key] = v
            self.cpt_no[key] = no

        btns = ttk.Frame(tab)
        btns.grid(row=len(keys) + 1, column=0, columnspan=len(cols) + 1, sticky="w", pady=(4, 0))
        ttk.Button(btns, text="Apply", style="Accent.TButton", command=self.apply_cpt).pack(side="left")
        ttk.Button(btns, text="Reset this node", command=self.reset_node).pack(side="left", padx=8)
        self.cpt_msg = ttk.Label(btns, text="Enter = apply", style="Muted.TLabel")
        self.cpt_msg.pack(side="left", padx=10)
        if any(opts.values()):
            ttk.Label(tab, text="Note: ticked system changes (left) adjust some of these base values "
                                "in the calculation.", wraplength=th.px(380),
                      foreground=th.WARN).grid(row=len(keys) + 2, column=0, columnspan=len(cols) + 1,
                                                 sticky="w", pady=(4, 0))

    def update_no(self, key):
        try:
            x = float(self.cpt_vars[key].get().replace(",", "."))
            self.cpt_no[key].config(text=f"{1 - x:g}" if 0 <= x <= 1 else "-")
        except (ValueError, KeyError, tk.TclError):
            if key in self.cpt_no:
                self.cpt_no[key].config(text="-")

    def apply_cpt(self):
        bt = self.app.bayes
        new = {}
        for key, v in self.cpt_vars.items():
            try:
                x = float(v.get().replace(",", "."))
            except ValueError:
                self.cpt_msg.config(text=f"'{v.get()}' is not a number.", foreground=th.RISK)
                return
            if not 0 <= x <= 1:
                self.cpt_msg.config(text="Probabilities must be between 0 and 1.", foreground=th.RISK)
                return
            new[key] = x
        if all(bt.params[k] == x for k, x in new.items()):
            return
        old = dict(bt.params)
        bt.params.update(new)
        if not bt.calculate():          # the new table makes the evidence impossible
            bt.params = old
            bt.calculate()

    def reset_node(self):
        bt = self.app.bayes
        for key in vm.CPT_KEYS[self.selected].values():
            bt.params[key] = vm.DEFAULT_BN_PARAMS[key]
        bt.calculate()

    def draw(self):
        c = self.canvas
        c.delete("all")
        bt = getattr(self.app, "bayes", None)
        if bt is None or not hasattr(bt, "last"):
            return
        prior, post, ev, opts = bt.last
        k = th.S
        w = max(c.winfo_width(), 500 * k)
        h = max(c.winfo_height(), 280 * k)
        compact = h < 420 * k
        y0 = (62 if compact else 84) * k
        y1 = h - (34 if compact else 46) * k
        row = (y1 - y0) / 5
        bh = th.clamp(row * 0.62, 26 * k, self.BOX_H * k)
        bw = th.clamp(w * 0.11 - 10 * k, 64 * k, self.BOX_W * k)
        y0 += bh / 2
        y1 -= bh / 2
        row = (y1 - y0) / 5
        m = bw / 2 + 10 * k
        X = lambda fx: m + (fx - 0.06) / 0.88 * (w - 2 * m)
        pos = {n: (X(fx), y0 + r * row) for n, (fx, r) in BN_LAYOUT.items()}
        parents = {nd["name"]: nd["parents"] for nd in vm.build_bn(bt.params)}

        active = [vm.OPTIONS[k] for k, v in opts.items() if v]
        c.create_text(20 * k, 20 * k, anchor="w", font=FONT_T, fill=INK,
                      text=f"Bayesian network: P(unsafe batch released) = {post['U']:.5f}"
                           f"   (no evidence {prior['U']:.5f}, x{post['U'] / prior['U']:.2f})")
        status = ("System changes: " + (", ".join(active) if active else "none")
                  + "   |   Evidence: "
                  + (", ".join(f"{BN_SHORT[k]}={'yes' if v else 'no'}" for k, v in ev.items())
                     if ev else "none"))
        if bt.params != vm.DEFAULT_BN_PARAMS:
            d = vm.bn_query(vm.build_bn())["U"]
            changed = [k for k in bt.params if bt.params[k] != vm.DEFAULT_BN_PARAMS[k]]
            c.create_text(w - 20 * k, 42 * k, anchor="e", font=FONT_B, fill=th.WARN,
                          text=f"Edited model ({len(changed)} values changed) - default model: {d:.5f}")
        c.create_text(20 * k, 42 * k, anchor="w", font=FONT, fill=QUIET, text=status)

        for child, ps in parents.items():
            cx, cy = pos[child]
            for par in ps:
                px, py = pos[par]
                c.create_line(px, py + bh / 2, cx, cy - bh / 2, fill="#b6c2d1", width=1.3 * k,
                              arrow="last", arrowshape=(9 * k, 10 * k, 4 * k))

        kb = bh / (self.BOX_H * k)
        three = bh >= 40 * k
        name_size = 9 if bh >= 40 * k else 8
        for n, (cx, cy) in pos.items():
            ratio = post[n] / prior[n] if prior[n] > 0 else 1.0
            if n in ev:
                fill, outline, width = ((th.RISK_SOFT, th.RISK, 2.5 * k) if ev[n]
                                        else (th.GOOD_SOFT, th.GOOD, 2.5 * k))
            else:
                t = min(abs(math.log2(ratio)) / 3, 1) if ratio > 0 else 1
                fill = mix("#ffffff", th.RISK_FILL if ratio > 1 else th.GOOD_FILL, 0.85 * t)
                outline, width = ("#94a3b8", 1.2 * k)
            root = not parents[n]
            tags = ("node", n)
            if n == self.selected:
                round_rect(c, cx - bw / 2 - 5 * k, cy - bh / 2 - 5 * k, cx + bw / 2 + 5 * k, cy + bh / 2 + 5 * k,
                           r=min(13 * k, bh / 3 + 4 * k), fill="", outline=HILITE, width=2.5 * k)
            round_rect(c, cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2, r=min(10 * k, bh / 3), fill=fill,
                       outline=outline, width=width, dash=(4, 2) if root and n not in ev else None,
                       tags=tags)
            name_font = th.fit_font(BN_SHORT[n], bw - 6 * k, size=name_size)
            ptxt = f"P = {post[n]:.4f}"
            if three:
                c.create_text(cx, cy - 13 * k * kb, text=BN_SHORT[n], font=name_font, fill=INK, tags=tags)
                c.create_text(cx, cy + 2 * k * kb, text=ptxt, font=FONT, fill=INK, tags=tags)
                sub = ("observed: " + ("yes" if ev[n] else "no")) if n in ev else f"change x{ratio:.2f}"
                c.create_text(cx, cy + 15 * k * kb, text=sub, font=th.F_TINY, fill=QUIET, tags=tags)
            else:
                c.create_text(cx, cy - bh * 0.18, text=BN_SHORT[n], font=name_font, fill=INK, tags=tags)
                c.create_text(cx, cy + bh * 0.22, text=ptxt, font=th.F_TINY, fill=INK, tags=tags)

        lx, ly = 20 * k, h - 18 * k
        step = th.clamp(w / 8, 105 * k, 150 * k)
        items = [(th.RISK_SOFT, th.RISK, "observed yes"), (th.GOOD_SOFT, th.GOOD, "observed no"),
                 (mix("#ffffff", th.RISK_FILL, 0.7), "#94a3b8", "more likely"),
                 (mix("#ffffff", th.GOOD_FILL, 0.7), "#94a3b8", "less likely")]
        for i, (f, o, label) in enumerate(items):
            x0 = lx + i * step
            round_rect(c, x0, ly - 7 * k, x0 + 18 * k, ly + 7 * k, r=4 * k, fill=f, outline=o)
            c.create_text(x0 + 24 * k, ly, anchor="w", font=FONT, fill=QUIET, text=label)
        if w > 4 * step + 420 * k:
            c.create_text(lx + 4 * step, ly, anchor="w", font=FONT, fill=QUIET,
                          text="change = vs no evidence  |  dashed = root cause  |  blue frame = selected")
