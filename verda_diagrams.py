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

FONT = ("Segoe UI", 9)
FONT_B = ("Segoe UI", 9, "bold")
FONT_T = ("Segoe UI", 12, "bold")
INK, QUIET, EDGE = "#222222", "#666666", "#8a8a8a"
HILITE = "#1f5fbf"

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
        super().__init__(master, padding=0)
        self.app = app
        self.selected_cut = set()
        self.selected_event = None

        bottom = ttk.Frame(self)
        bottom.pack(side="bottom", fill="x", pady=(8, 0))
        cutf = ttk.LabelFrame(bottom, text="Minimal cut sets (click to highlight)", padding=6)
        cutf.pack(side="left", fill="y")
        self.cuts = tk.Listbox(cutf, height=7, width=34, font=("Consolas", 10), activestyle="none",
                               exportselection=False)
        sb = ttk.Scrollbar(cutf, command=self.cuts.yview)
        self.cuts.configure(yscrollcommand=sb.set)
        self.cuts.pack(side="left", fill="y")
        sb.pack(side="left", fill="y")
        self.cuts.bind("<<ListboxSelect>>", self.on_cut)
        infof = ttk.LabelFrame(bottom, text="Selected event (click a basic event in the diagram)", padding=6)
        infof.pack(side="left", fill="both", expand=True, padx=8)
        self.info = tk.Text(infof, height=8, font=FONT, wrap="word", background="#f7f7f7", relief="flat")
        self.info.pack(fill="both", expand=True)
        btns = ttk.Frame(bottom)
        btns.pack(side="left", fill="y")
        ttk.Button(btns, text="Clear highlight", command=self.clear_highlight).pack(fill="x")
        ttk.Button(btns, text="Save diagram (.eps)",
                   command=lambda: save_eps(self.canvas, self, "verda_fault_tree.eps")).pack(fill="x", pady=6)

        self.canvas = tk.Canvas(self, background="white", highlightthickness=0)
        self.canvas.pack(side="top", fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.draw())
        self.canvas.tag_bind("event", "<Button-1>", self.on_click)
        self.cut_rows = []

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
        margin = 20 + self.BOX_W / 2
        step = (width - 2 * margin) / max(len(order) - 1, 1)
        self.leaf_step = step
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
    def gate_symbol(self, kind, cx, cy, colour):
        c = self.canvas
        r = 13
        if kind == "AND":
            pts = [cx - r, cy + 10]
            for i in range(0, 181, 15):
                a = math.radians(180 - i)
                pts += [cx + r * math.cos(a), cy - r * math.sin(a) + 2]
            pts += [cx + r, cy + 10]
            c.create_polygon(pts, fill="white", outline=colour, width=1.5)
        else:
            c.create_polygon(cx - r, cy + 10, cx, cy + 4, cx + r, cy + 10, cx + r - 2, cy - 2,
                             cx, cy - 14, cx - r + 2, cy - 2, smooth=True,
                             fill="white", outline=colour, width=1.5)
        c.create_text(cx, cy + 3, text=kind, font=("Segoe UI", 6, "bold"), fill=colour)

    def draw(self):
        c = self.canvas
        c.delete("all")
        p = self.probabilities()
        g = vm.gate_probabilities(p)
        fv = {r["event"]: r["fussell_vesely"] for r in vm.importance(p)}
        w = max(c.winfo_width(), 1000)
        h = max(c.winfo_height(), 560)
        x, depth = self.layout(w)
        levels = max(depth.values()) + 1
        y0 = 100
        row = (h - y0 - 80) / max(levels - 1, 1)
        Y = lambda n: y0 + depth[n] * row
        hl = self.selected_cut | self.ancestors(self.selected_cut)
        bw, bh = min(self.BOX_W, self.leaf_step - 10), self.BOX_H
        q = g["TOP"]

        c.create_text(16, 20, anchor="w", font=FONT_T, fill=INK,
                      text=f"Fault tree: P(unsafe batch released) = {q:.5f} per batch"
                           + (f"  (about 1 in {1 / q:,.0f})" if q > 0 else ""))
        c.create_text(16, 42, anchor="w", font=FONT, fill=QUIET,
                      text="Basic events shaded by Fussell-Vesely importance. "
                           "Click an event for details; pick a cut set below to highlight it.")

        # connectors first, so boxes sit on top
        for gate, (kind, children, _) in vm.GATES.items():
            gx, gy = x[gate], Y(gate)
            sym_y = gy + bh / 2 + 16
            bus_y = sym_y + 10 + (row - bh - 26) / 2
            col = HILITE if gate in hl else EDGE
            wid = 2.5 if gate in hl else 1.2
            c.create_line(gx, gy + bh / 2, gx, sym_y - 14, fill=col, width=wid)
            c.create_line(gx, sym_y + 10, gx, bus_y, fill=col, width=wid)
            xs = [x[ch] for ch in children]
            c.create_line(min(xs), bus_y, max(xs), bus_y, fill=EDGE, width=1.2)
            for ch in children:
                on = ch in hl and gate in hl
                c.create_line(x[ch], bus_y, x[ch], Y(ch) - bh / 2,
                              fill=HILITE if on else EDGE, width=2.5 if on else 1.2)
            if gate in hl:
                hx = [x[ch] for ch in children if ch in hl] + [gx]
                c.create_line(min(hx), bus_y, max(hx), bus_y, fill=HILITE, width=2.5)
            self.gate_symbol(kind, gx, sym_y, col)

        for n in x:
            cx, cy = x[n], Y(n)
            is_gate = n in vm.GATES
            on = n in hl
            if is_gate:
                fill = "#dfe8f5" if n == "TOP" else "#eef1f5"
                val = g[n]
                sub = f"{vm.GATES[n][0]}  {val:.5f}"
            else:
                fill = mix("#ffffff", "#e06666", math.sqrt(fv.get(n, 0)))
                sub = f"{n}  p={p[n]:g}"
            outline = HILITE if on or n == self.selected_event else ("#555555" if is_gate else "#777777")
            tags = ("node", n) if is_gate else ("node", "event", n)
            c.create_rectangle(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2,
                               fill=fill, outline=outline, width=2.5 if on else 1.2, tags=tags)
            c.create_text(cx, cy - 8, text=FTA_SHORT[n], font=FONT_B, fill=INK, tags=tags)
            c.create_text(cx, cy + 10, text=sub, font=FONT, fill=INK if is_gate else QUIET, tags=tags)

        # legend
        lx, ly = 16, h - 30
        c.create_text(lx, ly, anchor="w", font=FONT, fill=QUIET, text="Importance:")
        for i in range(6):
            c.create_rectangle(lx + 80 + i * 22, ly - 7, lx + 100 + i * 22, ly + 7,
                               fill=mix("#ffffff", "#e06666", math.sqrt(i / 5)), outline="#aaaaaa")
        c.create_text(lx + 80, ly + 16, anchor="w", font=("Segoe UI", 8), fill=QUIET, text="low")
        c.create_text(lx + 212, ly + 16, anchor="e", font=("Segoe UI", 8), fill=QUIET, text="high")
        c.create_text(lx + 240, ly, anchor="w", font=FONT, fill=QUIET,
                      text="Gates assume independent events. All values illustrative.")

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
        super().__init__(master, padding=0)
        self.app = app
        self.selected = "SS"
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text="Left-click a node: select it and edit its table below.   "
                            "Right-click a node: cycle its evidence (unknown -> yes -> no).",
                  foreground=QUIET).pack(side="left")
        ttk.Button(bar, text="Save diagram (.eps)",
                   command=lambda: save_eps(self.canvas, self, "verda_bayes_net.eps")).pack(side="right")

        bottom = ttk.Frame(self)
        bottom.pack(side="bottom", fill="x", pady=(8, 0))
        self.extra = ttk.LabelFrame(bottom, text="Compare improvement options (same evidence)",
                                    padding=(8, 6))
        self.extra.pack(side="right", fill="y", padx=(8, 0))
        self.panel = ttk.LabelFrame(bottom, text="Selected node", padding=(10, 6))
        self.panel.pack(side="left", fill="both", expand=True)

        self.canvas = tk.Canvas(self, background="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, pady=(8, 0))
        self.canvas.bind("<Configure>", lambda e: self.draw())
        self.canvas.tag_bind("node", "<Button-1>", self.on_select)
        self.canvas.tag_bind("node", "<Button-3>", self.on_cycle)
        self.canvas.tag_bind("node", "<Button-2>", self.on_cycle)   # macOS right button

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
        self.panel.config(text=f"Selected node: {n} - {vm.BN_LABELS[n]}")

        # left column: summary and evidence
        info = ttk.Frame(self.panel)
        info.pack(side="left", fill="y", padx=(0, 16))
        kind = ("root cause (no parents)" if not parents else
                f"logic node: {vm.DET_LOGIC[n]} of its parents" if n in vm.DET_LOGIC else
                "probabilistic node")
        ttk.Label(info, text=f"Type: {kind}").pack(anchor="w")
        ttk.Label(info, text="Parents: " + (", ".join(f"{p} ({BN_SHORT[p]})" for p in parents)
                                            if parents else "none")).pack(anchor="w")
        ttk.Label(info, text=f"P(yes) now: {post[n]:.5f}   without evidence: {prior[n]:.5f}",
                  font=FONT_B).pack(anchor="w", pady=(4, 6))
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
            e = ttk.Entry(tab, textvariable=v, width=8)
            e.grid(row=i, column=len(parents), sticky="w", padx=2, pady=1)
            e.bind("<Return>", lambda _e: self.apply_cpt())
            v.trace_add("write", lambda *_a, k=key: self.update_no(k))
            no = ttk.Label(tab, text=f"{1 - bt.params[key]:g}", foreground=QUIET)
            no.grid(row=i, column=len(parents) + 1, sticky="w", padx=2)
            ttk.Label(tab, text=key, foreground="#999999").grid(row=i, column=len(parents) + 2,
                                                                 sticky="w", padx=(12, 0))
            self.cpt_vars[key] = v
            self.cpt_no[key] = no

        btns = ttk.Frame(tab)
        btns.grid(row=len(keys) + 1, column=0, columnspan=len(cols) + 1, sticky="w", pady=(6, 0))
        ttk.Button(btns, text="Apply", command=self.apply_cpt).pack(side="left")
        ttk.Button(btns, text="Reset this node", command=self.reset_node).pack(side="left", padx=6)
        self.cpt_msg = ttk.Label(btns, text="Enter or Apply to use.", foreground=QUIET)
        self.cpt_msg.pack(side="left", padx=10)
        if any(opts.values()):
            ttk.Label(tab, text="Note: ticked system changes (left) adjust some of these base values "
                                "in the calculation.", wraplength=380,
                      foreground="#b06000").grid(row=len(keys) + 2, column=0, columnspan=len(cols) + 1,
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
                self.cpt_msg.config(text=f"'{v.get()}' is not a number.", foreground="#b00020")
                return
            if not 0 <= x <= 1:
                self.cpt_msg.config(text="Probabilities must be between 0 and 1.", foreground="#b00020")
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
        w = max(c.winfo_width(), 1100)
        h = max(c.winfo_height(), 470)
        y0, y1 = 85, h - 62
        row = (y1 - y0) / 5
        pos = {n: (fx * w, y0 + r * row) for n, (fx, r) in BN_LAYOUT.items()}
        bw, bh = self.BOX_W, self.BOX_H
        parents = {nd["name"]: nd["parents"] for nd in vm.build_bn(bt.params)}

        active = [vm.OPTIONS[k] for k, v in opts.items() if v]
        c.create_text(16, 20, anchor="w", font=FONT_T, fill=INK,
                      text=f"Bayesian network: P(unsafe batch released) = {post['U']:.5f}"
                           f"   (no evidence {prior['U']:.5f}, x{post['U'] / prior['U']:.2f})")
        if bt.params != vm.DEFAULT_BN_PARAMS:
            d = vm.bn_query(vm.build_bn())["U"]
            changed = [k for k in bt.params if bt.params[k] != vm.DEFAULT_BN_PARAMS[k]]
            c.create_text(w - 16, 20, anchor="e", font=FONT_B, fill="#b06000",
                          text=f"Edited model ({len(changed)} values changed) - default model: {d:.5f}")
        c.create_text(16, 42, anchor="w", font=FONT, fill=QUIET,
                      text="System changes: " + (", ".join(active) if active else "none")
                           + "   |   Evidence: "
                           + (", ".join(f"{BN_SHORT[k]}={'yes' if v else 'no'}" for k, v in ev.items())
                              if ev else "none"))

        for child, ps in parents.items():
            cx, cy = pos[child]
            for par in ps:
                px, py = pos[par]
                c.create_line(px, py + bh / 2, cx, cy - bh / 2, fill=EDGE, width=1.2,
                              arrow="last", arrowshape=(9, 10, 4))

        for n, (cx, cy) in pos.items():
            ratio = post[n] / prior[n] if prior[n] > 0 else 1.0
            if n in ev:
                fill, outline, width = ("#f4c7c3", "#b3261e", 3) if ev[n] else ("#c8e6c9", "#1b7a3a", 3)
            else:
                t = min(abs(math.log2(ratio)) / 3, 1) if ratio > 0 else 1
                fill = mix("#ffffff", "#e57373" if ratio > 1 else "#81c784", 0.8 * t)
                outline, width = ("#555555", 1.2)
            root = not parents[n]
            tags = ("node", n)
            if n == self.selected:
                c.create_rectangle(cx - bw / 2 - 5, cy - bh / 2 - 5, cx + bw / 2 + 5, cy + bh / 2 + 5,
                                   outline=HILITE, width=2.5)
            c.create_rectangle(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2, fill=fill,
                               outline=outline, width=width, dash=(4, 2) if root and n not in ev else None,
                               tags=tags)
            c.create_text(cx, cy - 13, text=BN_SHORT[n], font=FONT_B, fill=INK, tags=tags)
            c.create_text(cx, cy + 2, text=f"P = {post[n]:.4f}", font=FONT, fill=INK, tags=tags)
            sub = ("observed: " + ("yes" if ev[n] else "no")) if n in ev else f"change x{ratio:.2f}"
            c.create_text(cx, cy + 15, text=sub, font=("Segoe UI", 8), fill=QUIET, tags=tags)

        lx, ly = 16, h - 22
        items = [("#f4c7c3", "#b3261e", "observed yes"), ("#c8e6c9", "#1b7a3a", "observed no"),
                 (mix("#ffffff", "#e06666", 0.7), "#555555", "more likely"),
                 (mix("#ffffff", "#66bb6a", 0.7), "#555555", "less likely")]
        for i, (f, o, label) in enumerate(items):
            x0 = lx + i * 150
            c.create_rectangle(x0, ly - 7, x0 + 18, ly + 7, fill=f, outline=o)
            c.create_text(x0 + 24, ly, anchor="w", font=FONT, fill=QUIET, text=label)
        c.create_text(lx + 600, ly, anchor="w", font=FONT, fill=QUIET, text="change = vs no evidence   |   dashed border = root cause   |   blue frame = selected")
