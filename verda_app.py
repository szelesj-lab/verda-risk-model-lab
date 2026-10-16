"""
VERDA Risk Model Lab - desktop interface.

Developer: József Szeles, Department of System Engineering, University of Pannonia

Tabs:
  1. Fault tree        - edit basic-event probabilities next to the drawn tree;
                         cut sets, importance, full text report
  2. Sensitivity       - tornado chart: which events move the top event most
  3. Bayesian network  - evidence and system changes next to the drawn network;
                         CPT editor and option comparison underneath
  4. Validation        - compare the model with batch records from a CSV file

The system itself is described in a model file (models/*.json). The VERDA
production cell is the bundled default. "Export model…" (tab 3, or Ctrl+E)
writes the current values to a new file, e.g. for handing in. Opening another
model is an instructor function: Ctrl+Shift+O, or
    python verda_app.py models/pump_station.json

Uses only the Python standard library (tkinter), so it packs into a small
Windows .exe with PyInstaller (see build_exe.bat).
"""

import os
import tkinter as tk
from datetime import datetime
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont

import verda_model as vm
import generate_data
import verda_theme as th
from verda_diagrams import FaultTreeDiagram, BayesDiagram, FTA_SHORT, BN_SHORT

APP_TITLE = "VERDA Risk Model Lab"
DEVELOPER = "József Szeles"
AFFILIATION = "Department of System Engineering, University of Pannonia"
PAD = 12


class FaultTreeTab(ttk.Frame):
    """Basic-event inputs on the left, the drawn fault tree on the right."""

    def __init__(self, master, app):
        super().__init__(master, padding=PAD, style="Page.TFrame")
        self.app = app
        self.vars = {}
        self.entries = {}

        panel = th.ScrollPanel(self)
        panel.pack(side="left", fill="y")
        left = panel.body

        res = th.Card(left, text="RESULT", padding=(12, 10))
        res.pack(fill="x")
        ttk.Label(res, text=f"P({vm.top_label().upper()})", style="KpiCaption.TLabel",
                  wraplength=th.px(330)).pack(anchor="w")
        self.kpi = ttk.Label(res, text="", style="Kpi.TLabel")
        self.kpi.pack(anchor="w", pady=(2, 0))
        row = ttk.Frame(res)
        row.pack(anchor="w", fill="x")
        self.kpi_one_in = ttk.Label(row, text="", style="Muted.TLabel")
        self.kpi_one_in.pack(side="left")
        self.kpi_delta = tk.Label(row, text="", font=th.F_SMALL_BOLD, padx=th.px(8), pady=1,
                                  bg=th.SUBTLE, fg=th.MUTED)
        self.kpi_delta.pack(side="left", padx=(10, 0))
        ttk.Button(res, text="Full report (gates, cut sets, importance)…",
                   command=self.show_report).pack(anchor="w", pady=(8, 0))

        box = th.Card(left, text="BASIC EVENTS  ·  PROBABILITY PER BATCH", padding=(12, 8))
        box.pack(fill="x", pady=(PAD, 0))
        id_w = max([4] + [len(x) for x in vm.BASIC_EVENTS])
        lab_w = min(24, max([18] + [len(FTA_SHORT[x]) + 1 for x in vm.BASIC_EVENTS]))
        box.config(text=f"BASIC EVENTS  ·  PROBABILITY {vm.UNIT.upper()}")
        for r, (eid, (desc, layer, p)) in enumerate(vm.BASIC_EVENTS.items()):
            ttk.Label(box, text=eid, font=th.F_SMALL_BOLD, foreground=th.MUTED,
                      width=id_w + 1).grid(row=r, column=0, sticky="w")
            ttk.Label(box, text=FTA_SHORT[eid], width=lab_w).grid(row=r, column=1, sticky="w")
            ttk.Label(box, text=layer, style="Muted.TLabel", width=12).grid(row=r, column=2, sticky="w")
            v = tk.StringVar(value=str(p))
            e = ttk.Entry(box, textvariable=v, width=8, justify="right")
            e.grid(row=r, column=3, pady=1)
            e.bind("<Return>", lambda _e: self.calculate())
            self.vars[eid] = v
            self.entries[eid] = e
        bar = ttk.Frame(box)
        bar.grid(row=len(vm.BASIC_EVENTS), column=0, columnspan=4, pady=(10, 0), sticky="w")
        ttk.Button(bar, text="Calculate", style="Accent.TButton", command=self.calculate).pack(side="left")
        ttk.Button(bar, text="Reset defaults", command=self.reset).pack(side="left", padx=8)
        ttk.Label(box, text="Type a value and press Enter or Calculate.", style="Muted.TLabel").grid(
            row=len(vm.BASIC_EVENTS) + 1, column=0, columnspan=4, sticky="w", pady=(4, 0))

        self.diagram = FaultTreeDiagram(self, app)
        self.diagram.pack(side="left", fill="both", expand=True, padx=(PAD, 0))
        self.calculate()

    def probabilities(self):
        p = {}
        for eid, v in self.vars.items():
            try:
                x = float(v.get().replace(",", "."))
            except ValueError:
                raise ValueError(f"{eid}: '{v.get()}' is not a number")
            if not 0 <= x <= 1:
                raise ValueError(f"{eid}: probability must be between 0 and 1")
            p[eid] = x
        return p

    def calculate(self):
        try:
            p = self.probabilities()
        except ValueError as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        q = vm.top_probability(p)
        base = vm.top_probability(vm.default_fta_probabilities())
        self.kpi.config(text=f"{q:.5f}")
        self.kpi_one_in.config(text=f"about 1 in {1 / q:,.0f} {vm.ITEMS}" if q > 0 else "never")
        rel = q / base - 1 if base > 0 else 0.0
        if abs(rel) < 0.005:
            self.kpi_delta.config(text="default model", bg=th.SUBTLE, fg=th.MUTED)
        elif rel > 0:
            self.kpi_delta.config(text=f"{rel:+.0%} vs default", bg=th.RISK_SOFT, fg=th.RISK)
        else:
            self.kpi_delta.config(text=f"{rel:+.0%} vs default", bg=th.GOOD_SOFT, fg=th.GOOD)
        if hasattr(self.app, "sensitivity"):
            self.app.sensitivity.refresh()
        self.diagram.refresh()

    def reset(self):
        for eid, v in self.vars.items():
            v.set(str(vm.BASIC_EVENTS[eid][2]))
        self.calculate()

    def focus_event(self, eid):
        e = self.entries[eid]
        e.focus_set()
        e.select_range(0, "end")

    def show_report(self):
        try:
            p = self.probabilities()
        except ValueError as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        win = tk.Toplevel(self)
        th.style_toplevel(win)
        win.title("Fault tree report")
        win.geometry("780x640")
        text = tk.Text(win, font=th.F_MONO, wrap="none", bg=th.CARD, fg=th.INK, relief="flat",
                       padx=16, pady=12, highlightthickness=0)
        sb = ttk.Scrollbar(win, command=text.yview)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.insert("1.0", vm.fta_report(p))


class SensitivityTab(ttk.Frame):
    DEFAULT_LOW, DEFAULT_HIGH = "0.5", "2"
    BLUE, RED = "#60a5fa", th.RISK_FILL

    def __init__(self, master, app):
        super().__init__(master, padding=PAD, style="Page.TFrame")
        self.app = app
        top = th.Card(self, text="SCALE FACTORS", padding=12)
        top.pack(fill="x")
        ttk.Label(top, text="Each event is scaled by").pack(side="left")
        self.low = tk.StringVar(value=self.DEFAULT_LOW)
        self.high = tk.StringVar(value=self.DEFAULT_HIGH)
        for var, label in ((self.low, "and"), (self.high, None)):
            e = ttk.Entry(top, textvariable=var, width=5, justify="right")
            e.pack(side="left", padx=6)
            e.bind("<Return>", lambda _e: self.refresh())
            if label:
                ttk.Label(top, text=label).pack(side="left")
        ttk.Button(top, text="Update", style="Accent.TButton", command=self.refresh).pack(side="left", padx=(12, 0))
        ttk.Button(top, text="Reset defaults", command=self.reset).pack(side="left", padx=8)
        ttk.Label(top, text="Uses the probabilities currently set on tab 1 (Fault tree).",
                  style="Muted.TLabel").pack(side="left", padx=12)
        self.canvas = tk.Canvas(self)
        th.style_canvas(self.canvas)
        self.canvas.pack(fill="both", expand=True, pady=(PAD, 0))
        self._pending = None
        self.canvas.bind("<Configure>", lambda e: self._schedule())

    def _schedule(self):
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(40, self._redraw)

    def _redraw(self):
        self._pending = None
        self.refresh()

    def reset(self):
        self.low.set(self.DEFAULT_LOW)
        self.high.set(self.DEFAULT_HIGH)
        self.refresh()

    def refresh(self):
        if not hasattr(self.app, "fta"):
            return
        try:
            p = self.app.fta.probabilities()
            lo, hi = float(self.low.get()), float(self.high.get())
        except ValueError:
            return
        base, rows = vm.sensitivity(p, lo, hi)
        c = self.canvas
        c.delete("all")
        k = th.S
        w, h = max(c.winfo_width(), 600 * k), max(c.winfo_height(), 300 * k)
        left, right, y0 = th.clamp(w * 0.3, 330 * k, 380 * k), w - 160 * k, 80 * k
        row_h = min(40 * k, (h - y0 - 50 * k) / max(len(rows), 1))
        vmin = min(min(r[1] for r in rows), base)
        vmax = max(max(r[2] for r in rows), base)
        span = (vmax - vmin) or 1e-9
        X = lambda v: left + (v - vmin) / span * (right - left)

        c.create_text(24 * k, 22 * k, anchor="w", font=th.F_TITLE, fill=th.INK,
                      text=f"Top event with each event x{lo:g} (blue) and x{hi:g} (red)")
        c.create_text(24 * k, 44 * k, anchor="w", font=th.F_SMALL, fill=th.MUTED,
                      text="Longest bar first: the event that moves the risk most.")
        for i, (e, q_lo, q_hi) in enumerate(rows):
            y = y0 + i * row_h + row_h / 2
            if i % 2 == 0:
                c.create_rectangle(16 * k, y - row_h / 2, w - 16 * k, y + row_h / 2, fill=th.SUBTLE, outline="")
            c.create_text(28 * k, y, anchor="w", font=th.F_SMALL_BOLD, fill=th.MUTED, text=e)
            c.create_text(70 * k, y, anchor="w", font=th.F_BASE, fill=th.INK, text=vm.BASIC_EVENTS[e][0])
            bh = row_h * 0.28
            th.round_rect(c, X(min(q_lo, base)), y - bh, X(base), y + bh, r=4,
                          fill=self.BLUE, outline="")
            th.round_rect(c, X(base), y - bh, X(max(q_hi, base)), y + bh, r=4,
                          fill=self.RED, outline="")
            c.create_text(X(max(q_hi, base)) + 10 * k, y, anchor="w", font=th.F_SMALL,
                          fill=th.MUTED, text=f"{q_lo:.5f} - {q_hi:.5f}")
        yb = y0 + len(rows) * row_h
        c.create_line(X(base), y0 - 8 * k, X(base), yb + 8 * k, fill=th.INK, dash=(4, 3))
        c.create_text(X(base), yb + 18 * k, font=th.F_SMALL_BOLD, fill=th.INK, text=f"baseline {base:.5f}")


class BayesTab(ttk.Frame):
    """Evidence and system changes on the left, the drawn network on the right."""
    STATES = ["unknown", "yes", "no"]

    def __init__(self, master, app):
        super().__init__(master, padding=PAD, style="Page.TFrame")
        self.app = app
        self.params = dict(vm.DEFAULT_BN_PARAMS)
        self.extra_evidence = {}   # evidence set on the diagram for nodes without radio buttons

        panel = th.ScrollPanel(self)
        panel.pack(side="left", fill="y")
        left = panel.body
        ev = th.Card(left, text="EVIDENCE  ·  WHAT WE OBSERVE", padding=(12, 8))
        ev.pack(fill="x")
        self.evidence = {}
        self.EVIDENCE_NODES = list(vm.EVIDENCE_NODES)
        for r, n in enumerate(self.EVIDENCE_NODES):
            ttk.Label(ev, text=BN_SHORT[n], width=17).grid(row=r, column=0, sticky="w")
            v = tk.StringVar(value="unknown")
            for c, st in enumerate(self.STATES):
                ttk.Radiobutton(ev, text=st, value=st, variable=v,
                                command=self.calculate).grid(row=r, column=c + 1, padx=1, sticky="w")
            self.evidence[n] = v
        ttk.Label(ev, text="Other nodes: right-click them in the diagram.",
                  style="Muted.TLabel").grid(row=len(self.EVIDENCE_NODES), column=0, columnspan=4,
                                             sticky="w", pady=(4, 0))

        op = th.Card(left, text="CHANGES TO THE SYSTEM", padding=(12, 8))
        op.pack(fill="x", pady=(PAD, 0))
        self.options = {}
        for k, label in vm.OPTIONS.items():
            v = tk.BooleanVar(value=False)
            ttk.Checkbutton(op, text=label, variable=v, command=self.calculate).pack(anchor="w")
            self.options[k] = v
        if not vm.OPTIONS:
            ttk.Label(op, text="This model defines no changes.", style="Muted.TLabel").pack(anchor="w")

        bar = th.Card(left, text="MODEL", padding=(12, 8))
        bar.pack(fill="x", pady=(PAD, 0))
        ttk.Button(bar, text="Clear evidence and changes", command=self.clear).pack(fill="x")
        ttk.Button(bar, text="Edit all parameters…", command=self.edit_params).pack(fill="x", pady=4)
        ttk.Button(bar, text="Node probability table…", command=self.show_table).pack(fill="x")
        ttk.Button(bar, text="Export model…", command=self.app.export_model).pack(fill="x", pady=(4, 0))
        ttk.Label(bar, text="Saves the values from tabs 1 and 3 to a model file.",
                  style="Muted.TLabel", wraplength=th.px(260)).pack(anchor="w", pady=(4, 0))

        self.diagram = BayesDiagram(self, app)
        self.diagram.pack(side="left", fill="both", expand=True, padx=(PAD, 0))
        two = vm.SECOND != vm.QUERY
        self.cmp = ttk.Treeview(self.diagram.extra, columns=("opt", "u", "c") if two else ("opt", "u"),
                                show="headings", height=min(max(len(vm.option_variants()), 2), 7))
        measure = tkfont.nametofont("TkDefaultFont").measure
        head_font = ttk.Style().lookup("Treeview.Heading", "font") or "TkHeadingFont"
        head_measure = tkfont.Font(font=head_font).measure
        opt_w = max([measure("Option")] + [measure(label) for label, _ in vm.option_variants()])
        cols = [("opt", "Option", min(opt_w + th.px(14), th.px(260))),
                ("u", f"P({self.short(vm.QUERY)})", 0), ("c", f"P({self.short(vm.SECOND)})", 0)]
        for col, txt, wd in cols[:3 if two else 2]:
            wd = wd or max(th.px(80), head_measure(txt) + th.px(22))
            self.cmp.heading(col, text=txt, anchor="w" if col == "opt" else "e")
            self.cmp.column(col, width=wd, anchor="w" if col == "opt" else "e")
        self.cmp.tag_configure("best", foreground=th.GOOD)
        self.cmp.pack(fill="both", expand=True)
        ttk.Label(self.diagram.extra, text="Each option alone, not combined with the ticked changes.",
                  style="Muted.TLabel", wraplength=th.px(300)).pack(anchor="w", pady=(6, 0))
        self.calculate()

    @staticmethod
    def short(node, limit=18):
        s = vm.BN_SHORT[node]
        s = s if s[:2].isupper() else s[:1].lower() + s[1:]
        return s if len(s) <= limit else s[:limit - 1].rstrip() + "."

    def current_evidence(self):
        ev = {n: v.get() == "yes" for n, v in self.evidence.items() if v.get() != "unknown"}
        ev.update({n: s == "yes" for n, s in self.extra_evidence.items()})
        return ev

    def get_state(self, node):
        if node in self.evidence:
            return self.evidence[node].get()
        return self.extra_evidence.get(node, "unknown")

    def set_state(self, node, state):
        if node in self.evidence:
            self.evidence[node].set(state)
        elif state == "unknown":
            self.extra_evidence.pop(node, None)
        else:
            self.extra_evidence[node] = state

    def calculate(self):
        """Recompute everything; returns False if the evidence is impossible."""
        ev = self.current_evidence()
        opts = {k: v.get() for k, v in self.options.items()}
        try:
            prior = vm.bn_query(vm.build_bn(self.params))
            post = vm.bn_query(vm.build_bn(self.params, opts), ev)
            rows = vm.compare_options(ev, self.params)
        except ValueError as e:
            messagebox.showwarning(APP_TITLE, str(e))
            return False
        self.last = (prior, post, ev, opts)
        self.cmp.delete(*self.cmp.get_children())
        kinds = [vm.variant_kind(o) for _, o in vm.option_variants()]
        best = min(u for (_, u, _), kind in zip(rows, kinds) if kind != "threat")
        for (label, u, c), kind in zip(rows, kinds):
            self.cmp.insert("", "end", values=(label, f"{u:.5f}", f"{c:.5f}"),
                            tags=("best",) if u == best and kind != "baseline" else ())
        self.diagram.refresh()
        return True

    def show_table(self):
        prior, post, ev, _ = self.last
        win = tk.Toplevel(self)
        th.style_toplevel(win)
        win.title("Node probabilities (snapshot)")
        tree = ttk.Treeview(win, columns=("node", "label", "prior", "post", "ratio"),
                            show="headings", height=len(vm.BN_LABELS))
        for col, txt, wd in [("node", "Node", 70), ("label", "Meaning", 240),
                             ("prior", "Without evidence", 130), ("post", "Now", 100), ("ratio", "Change", 80)]:
            tree.heading(col, text=txt)
            tree.column(col, width=th.px(wd), anchor="w" if col in ("node", "label") else "e")
        for n in vm.BN_LABELS:
            ratio = post[n] / prior[n] if prior[n] > 0 else float("nan")
            tag = "ev" if n in ev else ("up" if ratio > 1.5 else ("down" if ratio < 0.67 else ""))
            tree.insert("", "end", values=(n, vm.BN_LABELS[n], f"{prior[n]:.5f}",
                                           f"{post[n]:.5f}", f"x{ratio:.2f}"), tags=(tag,))
        tree.tag_configure("up", foreground=th.RISK)
        tree.tag_configure("down", foreground=th.GOOD)
        tree.tag_configure("ev", background=th.ACCENT_SOFT)
        tree.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(win, text="Snapshot of the current state; reopen after changes.",
                  style="Muted.TLabel").pack(anchor="w", padx=12, pady=(0, 12))

    def clear(self):
        self.extra_evidence.clear()
        for v in self.evidence.values():
            v.set("unknown")
        for v in self.options.values():
            v.set(False)
        self.calculate()

    def edit_params(self):
        win = tk.Toplevel(self)
        th.style_toplevel(win)
        win.title("Bayesian network parameters")
        body = ttk.Frame(win, padding=16)
        body.pack(fill="both", expand=True)
        entries = {}
        where = {key: (node, combo) for node, table in vm.CPT_KEYS.items()
                 for combo, key in table.items()}
        for j, title in enumerate(("Parameter", "P(yes) of node", "when", "")):
            ttk.Label(body, text=title, font=th.F_SMALL_BOLD, foreground=th.MUTED).grid(
                row=0, column=j, sticky="w", padx=(0, 10))
        for r, (k, val) in enumerate(self.params.items(), start=1):
            node, combo = where[k]
            cond = ", ".join(f"{q} {'yes' if x else 'no'}" for q, x in zip(vm.BN_PARENTS[node], combo))
            ttk.Label(body, text=k, font=th.F_SMALL_BOLD).grid(row=r, column=0, sticky="w", padx=(0, 10))
            ttk.Label(body, text=f"{node}  {vm.BN_SHORT[node]}").grid(row=r, column=1, sticky="w", padx=(0, 10))
            ttk.Label(body, text=cond or "always", style="Muted.TLabel").grid(row=r, column=2, sticky="w",
                                                                              padx=(0, 10))
            v = tk.StringVar(value=str(val))
            ttk.Entry(body, textvariable=v, width=10, justify="right").grid(row=r, column=3, pady=2)
            entries[k] = v
        r = len(entries) + 1

        def apply():
            try:
                new = {k: float(v.get().replace(",", ".")) for k, v in entries.items()}
            except ValueError:
                messagebox.showerror(APP_TITLE, "All parameters must be numbers.", parent=win)
                return
            if any(not 0 <= x <= 1 for x in new.values()):
                messagebox.showerror(APP_TITLE, "Probabilities must be between 0 and 1.", parent=win)
                return
            self.params = new
            self.calculate()
            win.destroy()

        def reset():
            for k, v in entries.items():
                v.set(str(vm.DEFAULT_BN_PARAMS[k]))

        bar = ttk.Frame(body)
        bar.grid(row=r, column=0, columnspan=4, pady=(12, 0))
        ttk.Button(bar, text="Apply", style="Accent.TButton", command=apply).pack(side="left")
        ttk.Button(bar, text="Reset defaults", command=reset).pack(side="left", padx=8)


class ValidationTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=PAD, style="Page.TFrame")
        self.app = app
        bar = th.Card(self, text="BATCH RECORDS", padding=12)
        bar.pack(fill="x")
        ttk.Button(bar, text="Load batch records (CSV)…", style="Accent.TButton",
                   command=self.load).pack(side="left")
        ttk.Button(bar, text="Generate sample data…", command=self.generate).pack(side="left", padx=8)
        self.status = ttk.Label(bar, text="No data loaded.", style="Muted.TLabel")
        self.status.pack(side="left", padx=12)

        card = th.Card(self, text="OBSERVED VS PREDICTED", padding=12)
        card.pack(fill="x", pady=(PAD, 0))
        ttk.Label(card, text="Observed frequency with 95 % confidence interval vs the model's "
                             "prediction without evidence (Bayesian network tab parameters).",
                  style="Muted.TLabel", wraplength=th.px(1000)).pack(anchor="w", pady=(0, 10))
        self.tree = ttk.Treeview(card, columns=("col", "node", "k", "obs", "ci", "model", "v"),
                                 show="headings", height=8)
        for col, txt, wd in [("col", "Data column", 220), ("node", "Node", 70), ("k", "Events / batches", 140),
                             ("obs", "Observed", 100), ("ci", "95 % interval", 170),
                             ("model", "Model", 100), ("v", "Verdict", 140)]:
            anchor = "w" if col in ("col", "v") else "e"
            self.tree.heading(col, text=txt, anchor=anchor)
            self.tree.column(col, width=th.px(wd), anchor=anchor)
        self.tree.pack(fill="x")
        self.tree.tag_configure("bad", foreground=th.RISK, background=th.RISK_SOFT)
        self.tree.tag_configure("good", foreground=th.INK)
        ttk.Label(card, text="A 'CHECK MODEL' verdict means the data contradict the model: "
                             "question the structure or recalibrate the parameter, then justify the change.",
                  style="Muted.TLabel", wraplength=th.px(1000)).pack(anchor="w", pady=(10, 0))

    def load(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            records = vm.load_records(path)
            rows = vm.validate(records, self.app.bayes.params)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not read the file:\n{e}")
            return
        if not rows:
            messagebox.showwarning(APP_TITLE, "No column of this file matches the model.\n\n"
                                   "Expected columns: " + (", ".join(vm.OBSERVABLES) or
                                                           "(the model defines none)"))
            return
        self.status.config(text=f"{len(records)} batches from {path}")
        self.tree.delete(*self.tree.get_children())
        for col, node, k, n, obs, lo, hi, m, verdict in rows:
            self.tree.insert("", "end", tags=("bad",) if verdict != "consistent" else ("good",),
                             values=(col, node, f"{k} / {n}", f"{obs:.4f}",
                                     f"{lo:.4f} - {hi:.4f}", f"{m:.4f}",
                                     verdict))

    def generate(self):
        if not vm.OBSERVABLES:
            messagebox.showinfo(APP_TITLE, "This model defines no validation columns.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            initialfile=f"{vm.slug()}_records.csv",
                                            filetypes=[("CSV files", "*.csv")])
        if path:
            generate_data.write_csv(path)
            messagebox.showinfo(APP_TITLE, f"Saved {vm.SAMPLE_DATA['n']} sample records to\n{path}")


class App(tk.Tk):
    def __init__(self):
        th.enable_dpi_awareness()
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1500x920")   # size when not maximised (scaled below)
        self.minsize(1000, 600)
        th.apply(self)
        global PAD
        PAD = th.px(12)
        bar = th.header(self, APP_TITLE, "", f"Developer: {DEVELOPER}\n{AFFILIATION}")
        bar.pack(fill="x")
        self.subtitle = bar.subtitle
        self.bind_all("<Control-O>", lambda _e: self.open_model())    # Ctrl+Shift+O, instructors only
        self.bind_all("<Control-e>", lambda _e: self.export_model())
        self.notebook = None
        self.build_tabs()
        self.geometry(f"{th.px(1500)}x{th.px(920)}")
        self.minsize(th.px(1000), th.px(600))
        self.maximize()

    def build_tabs(self):
        """(Re)create the four tabs for the active model."""
        current = 0
        if self.notebook is not None:
            current = self.notebook.index("current")
            self.notebook.destroy()
            for name in ("fta", "sensitivity", "bayes", "validation"):
                self.__dict__.pop(name, None)
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.notebook = nb
        self.fta = FaultTreeTab(nb, self)
        self.fta_diagram = self.fta.diagram
        self.sensitivity = SensitivityTab(nb, self)
        self.bayes = BayesTab(nb, self)
        self.bn_diagram = self.bayes.diagram
        self.validation = ValidationTab(nb, self)
        nb.add(self.fta, text="1. Fault tree")
        nb.add(self.sensitivity, text="2. Sensitivity")
        nb.add(self.bayes, text="3. Bayesian network")
        nb.add(self.validation, text="4. Validation")
        nb.select(current)
        self.fta.calculate()
        self.bayes.calculate()
        self.subtitle.config(text=f"Model: {vm.MODEL_NAME}")
        self.title(f"{APP_TITLE} - {vm.MODEL_NAME}")

    def model_dir(self):
        """Folder offered in the Open / Save dialogs."""
        if vm.MODEL_PATH and os.path.dirname(vm.MODEL_PATH) != os.path.dirname(vm.DEFAULT_MODEL_PATH):
            return os.path.dirname(vm.MODEL_PATH)
        here = os.path.join(os.getcwd(), "models")      # models folder next to the program
        return here if os.path.isdir(here) else os.getcwd()

    def open_model(self, path=None):
        path = path or filedialog.askopenfilename(
            parent=self, title="Open model", initialdir=self.model_dir(),
            filetypes=[("Model files", "*.json"), ("All files", "*.*")])
        if not path:
            return False
        old_data, old_path = vm.MODEL, vm.MODEL_PATH
        try:
            vm.load_model(path)
            self.build_tabs()
        except vm.ModelError as e:
            vm.set_model(old_data, old_path)
            shown = e.problems[:15] + ([f"… and {len(e.problems) - 15} more"] if len(e.problems) > 15 else [])
            messagebox.showerror(APP_TITLE, f"{os.path.basename(path)} is not a valid model:\n\n- "
                                 + "\n- ".join(shown), parent=self)
            return False
        except Exception as e:                      # unreadable file or a bug: keep the old model
            vm.set_model(old_data, old_path)
            self.build_tabs()
            messagebox.showerror(APP_TITLE, f"Could not open {os.path.basename(path)}:\n{e}", parent=self)
            return False
        return True

    def export_model(self, path=None):
        """Write the model with the values currently set on tabs 1 and 3.

        The program keeps working with the open model; the file is for handing
        in or checking later (it records when and from which model it was made).
        """
        try:
            fta_p = self.fta.probabilities()
        except ValueError as e:
            messagebox.showerror(APP_TITLE, f"Fix the fault tree values first:\n{e}", parent=self)
            return False
        path = path or filedialog.asksaveasfilename(
            parent=self, title="Export model", defaultextension=".json",
            initialdir=os.path.expanduser("~"), initialfile=f"{vm.slug()}_export.json",
            filetypes=[("Model files", "*.json")])
        if not path:
            return False
        if os.path.abspath(path) == os.path.abspath(vm.DEFAULT_MODEL_PATH):
            messagebox.showerror(APP_TITLE, "The bundled sample model cannot be overwritten. "
                                 "Choose another file name.", parent=self)
            return False
        meta = {"exported": datetime.now().isoformat(timespec="seconds"),
                "exported_from": vm.MODEL_NAME}
        try:
            vm.save_model(path, fta_p, self.bayes.params, meta)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not export the model:\n{e}", parent=self)
            return False
        messagebox.showinfo(APP_TITLE, f"Model exported to\n{path}", parent=self)
        return True

    def maximize(self):
        """Open maximised (Windows: 'zoomed'; Linux: -zoomed; macOS keeps the default size)."""
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                pass


if __name__ == "__main__":
    import sys
    app = App()
    if len(sys.argv) > 1:                     # python verda_app.py my_model.json
        app.open_model(sys.argv[1])
    app.mainloop()
