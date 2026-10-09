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

Uses only the Python standard library (tkinter), so it packs into a small
Windows .exe with PyInstaller (see build_exe.bat).
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import verda_model as vm
import generate_data
from verda_diagrams import FaultTreeDiagram, BayesDiagram, FTA_SHORT, BN_SHORT

APP_TITLE = "VERDA Risk Model Lab"
DEVELOPER = "József Szeles"
AFFILIATION = "Department of System Engineering, University of Pannonia"
MONO = ("Consolas", 10)


class FaultTreeTab(ttk.Frame):
    """Basic-event inputs on the left, the drawn fault tree on the right."""

    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.vars = {}
        self.entries = {}

        left = ttk.Frame(self)
        left.pack(side="left", fill="y")
        box = ttk.LabelFrame(left, text="Basic events (probability per batch)", padding=8)
        box.pack(fill="x")
        for row, (eid, (desc, layer, p)) in enumerate(vm.BASIC_EVENTS.items()):
            ttk.Label(box, text=eid, width=4).grid(row=row, column=0, sticky="w")
            ttk.Label(box, text=FTA_SHORT[eid], width=19).grid(row=row, column=1, sticky="w")
            ttk.Label(box, text=layer, width=12, foreground="#666").grid(row=row, column=2, sticky="w")
            v = tk.StringVar(value=str(p))
            e = ttk.Entry(box, textvariable=v, width=8)
            e.grid(row=row, column=3, pady=1)
            e.bind("<Return>", lambda _e: self.calculate())
            self.vars[eid] = v
            self.entries[eid] = e
        bar = ttk.Frame(box)
        bar.grid(row=len(vm.BASIC_EVENTS), column=0, columnspan=4, pady=(10, 0), sticky="w")
        ttk.Button(bar, text="Calculate", command=self.calculate).pack(side="left")
        ttk.Button(bar, text="Reset defaults", command=self.reset).pack(side="left", padx=6)
        ttk.Label(box, text="Type a value and press Enter or Calculate.", foreground="#666").grid(
            row=len(vm.BASIC_EVENTS) + 1, column=0, columnspan=4, sticky="w", pady=(4, 0))

        res = ttk.LabelFrame(left, text="Result", padding=8)
        res.pack(fill="x", pady=10)
        self.summary = ttk.Label(res, text="", font=("Segoe UI", 11, "bold"), wraplength=330)
        self.summary.pack(anchor="w")
        ttk.Button(res, text="Full report (gates, cut sets, importance)...",
                   command=self.show_report).pack(anchor="w", pady=(8, 0))

        self.diagram = FaultTreeDiagram(self, app)
        self.diagram.pack(side="left", fill="both", expand=True, padx=(12, 0))
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
        change = f"{(q / base - 1):+.0%} vs default" if base > 0 else ""
        one_in = f"about 1 in {1 / q:,.0f} batches" if q > 0 else "never"
        self.summary.config(text=f"P(unsafe batch released) = {q:.5f}\n{one_in}   ({change})")
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
        win.title("Fault tree report")
        win.geometry("760x620")
        text = tk.Text(win, font=MONO, wrap="none")
        sb = ttk.Scrollbar(win, command=text.yview)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.insert("1.0", vm.fta_report(p))


class SensitivityTab(ttk.Frame):
    DEFAULT_LOW, DEFAULT_HIGH = "0.5", "2"

    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Each event is scaled by").pack(side="left")
        self.low = tk.StringVar(value=self.DEFAULT_LOW)
        self.high = tk.StringVar(value=self.DEFAULT_HIGH)
        for var, label in ((self.low, "and"), (self.high, None)):
            e = ttk.Entry(top, textvariable=var, width=5)
            e.pack(side="left", padx=4)
            e.bind("<Return>", lambda _e: self.refresh())
            if label:
                ttk.Label(top, text=label).pack(side="left")
        ttk.Button(top, text="Update", command=self.refresh).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="Reset defaults", command=self.reset).pack(side="left", padx=6)
        ttk.Label(top, text="Uses the probabilities currently set on tab 1 (Fault tree).",
                  foreground="#666").pack(side="left", padx=10)
        self.canvas = tk.Canvas(self, background="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, pady=(10, 0))
        self.canvas.bind("<Configure>", lambda e: self.refresh())

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
        w, h = max(c.winfo_width(), 600), max(c.winfo_height(), 300)
        left, right, y0 = 330, w - 150, 50
        row_h = min(34, (h - 90) / max(len(rows), 1))
        vmin = min(min(r[1] for r in rows), base)
        vmax = max(max(r[2] for r in rows), base)
        span = (vmax - vmin) or 1e-9
        X = lambda v: left + (v - vmin) / span * (right - left)
        c.create_text(20, 20, anchor="w", font=("Segoe UI", 12, "bold"),
                      text=f"Top event with each event x{lo:g} (blue) and x{hi:g} (red)")
        for i, (e, q_lo, q_hi) in enumerate(rows):
            y = y0 + i * row_h + row_h / 2
            c.create_text(20, y, anchor="w", font=("Segoe UI", 10),
                          text=f"{e}  {vm.BASIC_EVENTS[e][0]}")
            c.create_rectangle(X(min(q_lo, base)), y - row_h * 0.3, X(base), y + row_h * 0.3,
                               fill="#6c9bd2", outline="")
            c.create_rectangle(X(base), y - row_h * 0.3, X(max(q_hi, base)), y + row_h * 0.3,
                               fill="#d96c6c", outline="")
            c.create_text(X(max(q_hi, base)) + 6, y, anchor="w", font=("Segoe UI", 9),
                          fill="#444", text=f"{q_lo:.5f} - {q_hi:.5f}")
        yb = y0 + len(rows) * row_h
        c.create_line(X(base), y0 - 5, X(base), yb + 5, fill="#333", dash=(3, 3))
        c.create_text(X(base), yb + 18, font=("Segoe UI", 9), text=f"baseline {base:.5f}")


class BayesTab(ttk.Frame):
    """Evidence and system changes on the left, the drawn network on the right."""
    EVIDENCE_NODES = ["TP", "DI", "PF", "SS", "RB", "B8", "B10", "C", "U"]
    STATES = ["unknown", "yes", "no"]

    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.params = dict(vm.DEFAULT_BN_PARAMS)
        self.extra_evidence = {}   # evidence set on the diagram for nodes without radio buttons

        left = ttk.Frame(self)
        left.pack(side="left", fill="y")
        ev = ttk.LabelFrame(left, text="Evidence (what we observe)", padding=8)
        ev.pack(fill="x")
        self.evidence = {}
        for r, n in enumerate(self.EVIDENCE_NODES):
            ttk.Label(ev, text=BN_SHORT[n], width=17).grid(row=r, column=0, sticky="w")
            v = tk.StringVar(value="unknown")
            for c, st in enumerate(self.STATES):
                ttk.Radiobutton(ev, text=st, value=st, variable=v,
                                command=self.calculate).grid(row=r, column=c + 1, padx=1)
            self.evidence[n] = v
        ttk.Label(ev, text="Other nodes: right-click them in the diagram.",
                  foreground="#666").grid(row=len(self.EVIDENCE_NODES), column=0, columnspan=4,
                                          sticky="w", pady=(4, 0))

        op = ttk.LabelFrame(left, text="Changes to the system", padding=8)
        op.pack(fill="x", pady=8)
        self.options = {}
        for k, label in vm.OPTIONS.items():
            v = tk.BooleanVar(value=False)
            ttk.Checkbutton(op, text=label, variable=v, command=self.calculate).pack(anchor="w")
            self.options[k] = v

        bar = ttk.LabelFrame(left, text="Model", padding=8)
        bar.pack(fill="x")
        ttk.Button(bar, text="Clear evidence and changes", command=self.clear).pack(fill="x")
        ttk.Button(bar, text="Edit all parameters...", command=self.edit_params).pack(fill="x", pady=4)
        ttk.Button(bar, text="Node probability table...", command=self.show_table).pack(fill="x")

        self.diagram = BayesDiagram(self, app)
        self.diagram.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.cmp = ttk.Treeview(self.diagram.extra, columns=("opt", "u", "c"), show="headings", height=5)
        for col, txt, wd in [("opt", "Option", 205), ("u", "P(unsafe)", 80),
                             ("c", "P(contam.)", 80)]:
            self.cmp.heading(col, text=txt)
            self.cmp.column(col, width=wd, anchor="w" if col == "opt" else "e")
        self.cmp.pack(fill="both", expand=True)
        ttk.Label(self.diagram.extra, text="Each option alone, not combined\nwith the ticked changes.",
                  foreground="#666").pack(anchor="w", pady=(4, 0))
        self.calculate()

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
        for label, u, c in rows:
            self.cmp.insert("", "end", values=(label, f"{u:.5f}", f"{c:.5f}"))
        self.diagram.refresh()
        return True

    def show_table(self):
        prior, post, ev, _ = self.last
        win = tk.Toplevel(self)
        win.title("Node probabilities (snapshot)")
        tree = ttk.Treeview(win, columns=("node", "label", "prior", "post", "ratio"),
                            show="headings", height=len(vm.BN_LABELS))
        for col, txt, wd in [("node", "Node", 70), ("label", "Meaning", 240),
                             ("prior", "Without evidence", 120), ("post", "Now", 100), ("ratio", "Change", 80)]:
            tree.heading(col, text=txt)
            tree.column(col, width=wd, anchor="w" if col in ("node", "label") else "e")
        for n in vm.BN_LABELS:
            ratio = post[n] / prior[n] if prior[n] > 0 else float("nan")
            tag = "ev" if n in ev else ("up" if ratio > 1.5 else ("down" if ratio < 0.67 else ""))
            tree.insert("", "end", values=(n, vm.BN_LABELS[n], f"{prior[n]:.5f}",
                                           f"{post[n]:.5f}", f"x{ratio:.2f}"), tags=(tag,))
        tree.tag_configure("up", foreground="#b00020")
        tree.tag_configure("down", foreground="#1b7a3a")
        tree.tag_configure("ev", background="#eef3fb")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Label(win, text="Snapshot of the current state; reopen after changes.",
                  foreground="#666").pack(anchor="w", padx=8, pady=(0, 8))

    def clear(self):
        self.extra_evidence.clear()
        for v in self.evidence.values():
            v.set("unknown")
        for v in self.options.values():
            v.set(False)
        self.calculate()

    def edit_params(self):
        win = tk.Toplevel(self)
        win.title("Bayesian network parameters")
        entries = {}
        for r, (k, val) in enumerate(self.params.items()):
            ttk.Label(win, text=k, width=12).grid(row=r, column=0, sticky="w", padx=8)
            v = tk.StringVar(value=str(val))
            ttk.Entry(win, textvariable=v, width=10).grid(row=r, column=1, pady=1)
            entries[k] = v
        ttk.Label(win, text="P_* = root node probabilities;  _ok/_down = instructions up/down;\n"
                            "SS_xy: x = time pressure, y = instructions down;  RB_x: x = time pressure",
                  foreground="#666").grid(row=len(entries), column=0, columnspan=2, padx=8, pady=6)

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

        bar = ttk.Frame(win)
        bar.grid(row=len(entries) + 1, column=0, columnspan=2, pady=8)
        ttk.Button(bar, text="Apply", command=apply).pack(side="left")
        ttk.Button(bar, text="Reset defaults", command=reset).pack(side="left", padx=6)


class ValidationTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Button(bar, text="Load batch records (CSV)...", command=self.load).pack(side="left")
        ttk.Button(bar, text="Generate sample data...", command=self.generate).pack(side="left", padx=6)
        self.status = ttk.Label(bar, text="No data loaded.", foreground="#666")
        self.status.pack(side="left", padx=10)

        ttk.Label(self, text="Observed frequency with 95 % confidence interval vs the model's "
                             "prediction without evidence (Bayesian network tab parameters).",
                  wraplength=900).pack(anchor="w", pady=8)
        self.tree = ttk.Treeview(self, columns=("col", "node", "k", "obs", "ci", "model", "v"),
                                 show="headings", height=10)
        for col, txt, wd in [("col", "Data column", 200), ("node", "Node", 60), ("k", "Events / batches", 120),
                             ("obs", "Observed", 90), ("ci", "95 % interval", 150),
                             ("model", "Model", 90), ("v", "Verdict", 120)]:
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=wd, anchor="w" if col in ("col", "v") else "e")
        self.tree.pack(fill="x")
        self.tree.tag_configure("bad", foreground="#b00020")
        ttk.Label(self, text="A 'CHECK MODEL' verdict means the data contradict the model: "
                             "question the structure or recalibrate the parameter, then justify the change.",
                  foreground="#666", wraplength=900).pack(anchor="w", pady=8)

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
        self.status.config(text=f"{len(records)} batches from {path}")
        self.tree.delete(*self.tree.get_children())
        for col, node, k, n, obs, lo, hi, m, verdict in rows:
            self.tree.insert("", "end", tags=("bad",) if verdict != "consistent" else (),
                             values=(col, node, f"{k} / {n}", f"{obs:.4f}",
                                     f"{lo:.4f} - {hi:.4f}", f"{m:.4f}", verdict))

    def generate(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            initialfile="verda_batch_records.csv",
                                            filetypes=[("CSV files", "*.csv")])
        if path:
            generate_data.write_csv(path)
            messagebox.showinfo(APP_TITLE, f"Saved 200 sample batch records to\n{path}")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1500x920")   # size when not maximised
        self.minsize(1280, 820)
        try:
            ttk.Style().theme_use("vista")
        except tk.TclError:
            pass
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.notebook = nb
        self.fta = FaultTreeTab(nb, self)
        self.fta_diagram = self.fta.diagram
        self.sensitivity = SensitivityTab(nb, self)
        self.bayes = BayesTab(nb, self)
        self.bn_diagram = self.bayes.diagram
        self.validation = ValidationTab(nb, self)
        nb.add(self.fta, text="  1. Fault tree  ")
        nb.add(self.sensitivity, text="  2. Sensitivity  ")
        nb.add(self.bayes, text="  3. Bayesian network  ")
        nb.add(self.validation, text="  4. Validation  ")
        self.fta.calculate()
        self.bayes.calculate()
        foot = ttk.Frame(self, padding=(10, 4))
        foot.pack(fill="x")
        ttk.Label(foot, text="Teaching model - all probabilities are illustrative, per batch.",
                  foreground="#666").pack(side="left")
        ttk.Label(foot, text=f"Developer: {DEVELOPER}, {AFFILIATION}",
                  foreground="#666").pack(side="right")
        self.maximize()

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
    App().mainloop()
