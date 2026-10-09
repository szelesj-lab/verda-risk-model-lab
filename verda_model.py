"""
VERDA risk model - fault tree (FTA) and Bayesian network (BN).

Developer: József Szeles, Department of System Engineering, University of Pannonia

Teaching model for the course "Risk and Resilience Modelling of
Socio-Technical Manufacturing Systems". All probabilities are
illustrative values per batch, not data from a real plant.

The module has no third-party dependencies, so it can be used from the
GUI (verda_app.py), from a Jupyter notebook or from the command line:

    python verda_model.py
"""

from itertools import product
from math import prod, sqrt
import csv

# ---------------------------------------------------------------------------
# Fault tree
# ---------------------------------------------------------------------------

# id: (description, layer, probability per batch)
BASIC_EVENTS = {
    "B1": ("Preservative under-weighed", "Human", 0.005),
    "B2": ("Raw material swapped at weighing", "Human", 0.002),
    "B3": ("Temperature probe reads low", "Technology", 0.01),
    "B4": ("Operator does not cross-check temperature", "Human", 0.3),
    "B5": ("pH outside 5.0-5.5 not corrected", "Process", 0.004),
    "B6": ("Nozzle sanitation skipped at shift handover", "Organisation", 0.01),
    "B7": ("Sanitiser expired or ineffective", "Process", 0.002),
    "B8": ("QC sample not representative", "Process", 0.05),
    "B9": ("Batch released before micro result", "Organisation", 0.02),
    "B10": ("False 'pass' in electronic batch record", "Data", 0.005),
}

# gate id: (gate type, children, description)
GATES = {
    "TOP": ("AND", ["CONTAM", "QCFAIL"], "Unsafe batch released"),
    "CONTAM": ("OR", ["PRES", "NOZZLE"], "Contamination occurs"),
    "QCFAIL": ("OR", ["B8", "B9", "B10"], "QC fails to detect"),
    "PRES": ("OR", ["B1", "B2", "HOT", "B5"], "Inadequate preservation"),
    "HOT": ("AND", ["B3", "B4"], "Preservative added above 40 C"),
    "NOZZLE": ("OR", ["B6", "B7"], "Nozzle contamination"),
}


def default_fta_probabilities():
    return {k: v[2] for k, v in BASIC_EVENTS.items()}


def gate_probabilities(p, gates=GATES):
    """Probability of every gate, assuming independent basic events.

    Exact for this tree because no basic event appears twice.
    """
    cache = {}

    def prob(node):
        if node in p:
            return p[node]
        if node in cache:
            return cache[node]
        kind, children, _ = gates[node]
        vals = [prob(c) for c in children]
        if kind == "AND":
            r = prod(vals)
        else:
            r = 1 - prod(1 - v for v in vals)
        cache[node] = r
        return r

    for g in gates:
        prob(g)
    return cache


def top_probability(p, gates=GATES, top="TOP"):
    return gate_probabilities(p, gates)[top]


def minimal_cut_sets(node="TOP", gates=GATES):
    """Minimal cut sets by top-down expansion (MOCUS)."""
    if node not in gates:
        return [frozenset([node])]
    kind, children, _ = gates[node]
    child_sets = [minimal_cut_sets(c, gates) for c in children]
    if kind == "OR":
        sets = [s for cs in child_sets for s in cs]
    else:
        sets = [frozenset()]
        for cs in child_sets:
            sets = [a | b for a in sets for b in cs]
    sets = list(set(sets))
    return [s for s in sets if not any(o < s for o in sets)]


def ranked_cut_sets(p, gates=GATES):
    """Cut sets with their probabilities, largest first."""
    rows = [(sorted(cs, key=_event_order), prod(p[e] for e in cs))
            for cs in minimal_cut_sets("TOP", gates)]
    return sorted(rows, key=lambda r: -r[1])


def importance(p, gates=GATES):
    """Birnbaum and Fussell-Vesely importance of each basic event."""
    q = top_probability(p, gates)
    rows = []
    for e in p:
        q1 = top_probability({**p, e: 1.0}, gates)
        q0 = top_probability({**p, e: 0.0}, gates)
        rows.append({
            "event": e,
            "birnbaum": q1 - q0,
            "fussell_vesely": (q - q0) / q if q > 0 else 0.0,
        })
    return sorted(rows, key=lambda r: -r["fussell_vesely"])


def sensitivity(p, low=0.5, high=2.0, gates=GATES):
    """Top-event probability with each event scaled by low and high."""
    base = top_probability(p, gates)
    rows = []
    for e, v in p.items():
        q_lo = top_probability({**p, e: min(1.0, v * low)}, gates)
        q_hi = top_probability({**p, e: min(1.0, v * high)}, gates)
        rows.append((e, q_lo, q_hi))
    rows.sort(key=lambda r: -(r[2] - r[1]))
    return base, rows


def _event_order(e):
    return int(e[1:]) if e[1:].isdigit() else 999


def fta_report(p):
    """Text report: gate tree, cut sets and importance."""
    g = gate_probabilities(p)
    lines = ["FAULT TREE (independent events)", ""]

    def walk(node, depth):
        pad = "    " * depth
        if node in GATES:
            kind, children, desc = GATES[node]
            lines.append(f"{pad}{node:<7}{kind:<4}{desc:<44}{g[node]:.5f}")
            for c in children:
                walk(c, depth + 1)
        else:
            desc = BASIC_EVENTS[node][0]
            lines.append(f"{pad}{node:<7}{'':<4}{desc:<44}{p[node]:.5f}")

    walk("TOP", 0)
    q = g["TOP"]
    lines += ["", f"Top event probability: {q:.5f} per batch "
                  f"(about 1 in {1 / q:,.0f} batches)" if q > 0 else
              "Top event probability: 0", "",
              "MINIMAL CUT SETS (largest first)"]
    for cs, pr in ranked_cut_sets(p)[:12]:
        lines.append(f"  {' . '.join(cs):<18}{pr:.6f}   {pr / q:6.1%} of top" if q > 0
                     else f"  {' . '.join(cs):<18}{pr:.6f}")
    lines += ["", "IMPORTANCE", f"  {'Event':<7}{'Fussell-Vesely':>16}{'Birnbaum':>12}"]
    for r in importance(p):
        lines.append(f"  {r['event']:<7}{r['fussell_vesely']:>16.3f}{r['birnbaum']:>12.5f}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Bayesian network
# ---------------------------------------------------------------------------

DEFAULT_BN_PARAMS = {
    "P_TP": 0.2,            # handover time pressure
    "P_DI_DOWN": 0.05,      # digital work instructions down (Wi-Fi loss)
    "P_PF": 0.01,           # temperature probe fault (= B3)
    "B1_ok": 0.005, "B1_down": 0.015,   # under-weighing, instructions up/down
    "B2_ok": 0.002, "B2_down": 0.006,   # material swap, instructions up/down
    "B4": 0.3,              # no manual cross-check
    "B5": 0.004,
    "SS_00": 0.005,         # sanitation skipped: no pressure, instructions up
    "SS_01": 0.02,          #                     no pressure, instructions down
    "SS_10": 0.02,          #                     pressure,    instructions up
    "SS_11": 0.08,          #                     pressure,    instructions down
    "B7": 0.002,
    "RB_0": 0.01,           # released before result: no pressure
    "RB_1": 0.06,           #                         pressure
    "B8": 0.05,
    "B10": 0.005,
}

# name: label shown in the UI
BN_LABELS = {
    "TP": "Handover time pressure",
    "DI": "Instructions down (Wi-Fi)",
    "PF": "Probe fault (B3)",
    "B1": "Preservative under-weighed",
    "B2": "Raw material swapped",
    "B4": "No manual cross-check",
    "HOT": "Added above 40 C",
    "B5": "pH not corrected",
    "PRES": "Inadequate preservation",
    "SS": "Sanitation skipped (B6)",
    "B7": "Sanitiser ineffective",
    "NOZZLE": "Nozzle contamination",
    "C": "Contamination",
    "RB": "Released before result (B9)",
    "B8": "Sample not representative",
    "B10": "False pass recorded",
    "QM": "QC misses it",
    "U": "Unsafe batch released",
}

# Which parameter holds P(node = yes) for each combination of parent values.
# Keys are tuples of parent values in the order of the node's parent list.
CPT_KEYS = {
    "TP": {(): "P_TP"},
    "DI": {(): "P_DI_DOWN"},
    "PF": {(): "P_PF"},
    "B1": {(False,): "B1_ok", (True,): "B1_down"},
    "B2": {(False,): "B2_ok", (True,): "B2_down"},
    "B4": {(): "B4"},
    "B5": {(): "B5"},
    "SS": {(False, False): "SS_00", (False, True): "SS_01",
           (True, False): "SS_10", (True, True): "SS_11"},
    "B7": {(): "B7"},
    "RB": {(False,): "RB_0", (True,): "RB_1"},
    "B8": {(): "B8"},
    "B10": {(): "B10"},
}

# Logic nodes: their table is fixed by the gate type.
DET_LOGIC = {"HOT": "AND", "PRES": "OR", "NOZZLE": "OR", "C": "OR", "QM": "OR", "U": "AND"}

OPTIONS = {
    "second_probe": "Second temperature probe",
    "paper_fallback": "Paper fallback for work instructions",
    "cyber_incident": "Cyber incident (B10 x10)",
}


def apply_options(params, options):
    p = dict(params)
    if options.get("second_probe"):
        p["P_PF"] = p["P_PF"] * 0.05          # both probes wrong, incl. common cause
    if options.get("paper_fallback"):
        p["B1_down"] = p["B1_ok"] * 1.5
        p["B2_down"] = p["B2_ok"] * 1.5
        p["SS_01"] = p["SS_00"] * 1.5
        p["SS_11"] = p["SS_10"] * 1.5
    if options.get("cyber_incident"):
        p["B10"] = min(1.0, p["B10"] * 10)
    return p


def build_bn(params=None, options=None):
    """Return the node list in topological order."""
    p = apply_options(params or DEFAULT_BN_PARAMS, options or {})

    def cpt(name, parents, fn):
        return {"name": name, "type": "cpt", "parents": parents, "fn": fn}

    def det(name, parents, fn):
        return {"name": name, "type": "det", "parents": parents, "fn": fn}

    return [
        cpt("TP", [], lambda: p["P_TP"]),
        cpt("DI", [], lambda: p["P_DI_DOWN"]),
        cpt("PF", [], lambda: p["P_PF"]),
        cpt("B1", ["DI"], lambda di: p["B1_down"] if di else p["B1_ok"]),
        cpt("B2", ["DI"], lambda di: p["B2_down"] if di else p["B2_ok"]),
        cpt("B4", [], lambda: p["B4"]),
        det("HOT", ["PF", "B4"], lambda a, b: a and b),
        cpt("B5", [], lambda: p["B5"]),
        det("PRES", ["B1", "B2", "HOT", "B5"], lambda *x: any(x)),
        cpt("SS", ["TP", "DI"], lambda tp, di: p[f"SS_{int(tp)}{int(di)}"]),
        cpt("B7", [], lambda: p["B7"]),
        det("NOZZLE", ["SS", "B7"], lambda *x: any(x)),
        det("C", ["PRES", "NOZZLE"], lambda *x: any(x)),
        cpt("RB", ["TP"], lambda tp: p["RB_1"] if tp else p["RB_0"]),
        cpt("B8", [], lambda: p["B8"]),
        cpt("B10", [], lambda: p["B10"]),
        det("QM", ["RB", "B8", "B10"], lambda *x: any(x)),
        det("U", ["C", "QM"], lambda a, b: a and b),
    ]


def bn_query(nodes, evidence=None, do=None):
    """Exact inference by enumeration.

    evidence: {node: bool} observed values (conditioning).
    do:       {node: bool} forced values (intervention, ignores the node's CPT).
    Returns {node: P(node = True | evidence, do)}.
    """
    evidence = evidence or {}
    do = do or {}
    free = [n["name"] for n in nodes if n["type"] == "cpt" and n["name"] not in do]
    totals = {n["name"]: 0.0 for n in nodes}
    z = 0.0
    for values in product((False, True), repeat=len(free)):
        draw = dict(zip(free, values))
        state, w = {}, 1.0
        for n in nodes:
            name = n["name"]
            args = [state[x] for x in n["parents"]]
            if name in do:
                v = do[name]
            elif n["type"] == "det":
                v = n["fn"](*args)
            else:
                v = draw[name]
                pt = n["fn"](*args)
                w *= pt if v else 1 - pt
            state[name] = v
        if w == 0 or any(state[k] != val for k, val in evidence.items()):
            continue
        z += w
        for k, v in state.items():
            if v:
                totals[k] += w
    if z == 0:
        raise ValueError("The evidence is impossible under this model.")
    return {k: v / z for k, v in totals.items()}


def compare_options(evidence=None, params=None):
    """P(unsafe release) for each improvement option under the same evidence."""
    variants = [
        ("Baseline", {}),
        (OPTIONS["second_probe"], {"second_probe": True}),
        (OPTIONS["paper_fallback"], {"paper_fallback": True}),
        ("Both measures", {"second_probe": True, "paper_fallback": True}),
        (OPTIONS["cyber_incident"], {"cyber_incident": True}),
    ]
    rows = []
    for label, opts in variants:
        post = bn_query(build_bn(params, opts), evidence)
        rows.append((label, post["U"], post["C"]))
    return rows


# ---------------------------------------------------------------------------
# Validation against batch records
# ---------------------------------------------------------------------------

# CSV column -> BN node
OBSERVABLES = {
    "shift_handover_pressure": "TP",
    "wifi_down": "DI",
    "probe_fault": "PF",
    "sanitation_skipped": "SS",
    "released_before_result": "RB",
    "contaminated": "C",
    "unsafe_release": "U",
}


def wilson_interval(k, n, z=1.96):
    if n == 0:
        return 0.0, 1.0
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def load_records(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def validate(records, params=None):
    """Compare observed frequencies with model predictions.

    Returns rows: (column, node, k, n, observed, ci_low, ci_high, model, verdict).
    """
    prior = bn_query(build_bn(params))
    rows = []
    n = len(records)
    for col, node in OBSERVABLES.items():
        if not records or col not in records[0]:
            continue
        k = sum(int(r[col]) for r in records)
        lo, hi = wilson_interval(k, n)
        m = prior[node]
        verdict = "consistent" if lo <= m <= hi else "CHECK MODEL"
        rows.append((col, node, k, n, k / n if n else 0.0, lo, hi, m, verdict))
    return rows


if __name__ == "__main__":
    print(fta_report(default_fta_probabilities()))
    print()
    post = bn_query(build_bn())
    print(f"BN: P(unsafe release) = {post['U']:.5f}, "
          f"P(sanitation skipped) = {post['SS']:.4f}")
    post = bn_query(build_bn(), evidence={"DI": True})
    print(f"BN, Wi-Fi down: P(sanitation skipped) = {post['SS']:.4f}, "
          f"P(unsafe release) = {post['U']:.5f}")
