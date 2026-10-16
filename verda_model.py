"""
VERDA risk model engine - fault tree (FTA) and Bayesian network (BN).

Developer: József Szeles, Department of System Engineering, University of Pannonia

Teaching tool for the course "Risk and Resilience Modelling of
Socio-Technical Manufacturing Systems".

The engine is generic: the system is described in a model file
(JSON, see models/verda.json). The VERDA production cell is the sample
model that is loaded at start-up; load_model() switches to another file.
After loading, the module-level tables (BASIC_EVENTS, GATES,
DEFAULT_BN_PARAMS, CPT_KEYS, ...) describe the active model.

No third-party dependencies, so it works from the GUI (verda_app.py),
a Jupyter notebook or the command line:

    python verda_model.py [model.json]
"""

from itertools import combinations, product
from math import prod, sqrt
import copy
import csv
import json
import os
import sys

FORMAT = "verda-risk-model"
FORMAT_VERSION = 1
GATE_TYPES = ("AND", "OR", "VOTE")
MAX_REPEATED_EVENTS = 16      # exact FTA: 2^k conditioning passes
MAX_FREE_BN_NODES = 22        # exact BN: 2^k joint states


def resource_path(*parts):
    """Path of a bundled file, also inside a PyInstaller one-file exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


DEFAULT_MODEL_PATH = resource_path("models", "verda.json")


class ModelError(ValueError):
    """The model file is not valid. .problems lists every problem found."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("Invalid model:\n  - " + "\n  - ".join(self.problems))


# ---------------------------------------------------------------------------
# Active model (filled by set_model)
# ---------------------------------------------------------------------------

MODEL = {}            # the raw model dictionary as loaded
MODEL_PATH = None
MODEL_NAME = ""
MODEL_DESCRIPTION = ""
UNIT = "per batch"    # how probabilities are counted, e.g. "per batch", "per demand"
ITEMS = "batches"     # plural noun for "about 1 in N ..."

# Fault tree
TOP = "TOP"
BASIC_EVENTS = {}     # id: (description, layer, probability)
GATES = {}            # id: (type, children, description)
GATE_K = {}           # VOTE gate id: k (at least k of the inputs)
FTA_SHORT = {}        # id: short label for diagrams

# Bayesian network
QUERY = "U"           # node whose probability is the headline result
SECOND = "C"          # second column in the option comparison
EVIDENCE_NODES = []
DEFAULT_BN_PARAMS = {}
BN_LABELS = {}        # id: description
BN_SHORT = {}         # id: short label for diagrams
BN_LAYOUT = {}        # id: (x fraction 0..1, row) or missing
BN_PARENTS = {}       # id: [parents]
CPT_KEYS = {}         # chance node: {parent value tuple: parameter name}
DET_LOGIC = {}        # logic node: gate type
DET_K = {}            # logic VOTE node: k
NODE_ORDER = []       # topological order
OPTIONS = {}          # option id: label
OPTION_KIND = {}      # option id: "measure" | "threat"
OPTION_CHANGES = {}   # option id: [change dicts]

# Validation
OBSERVABLES = {}      # CSV column: node
SAMPLE_DATA = {"n": 200, "seed": 2026, "overrides": {}}

_MODEL_ID = 0         # changes on every load, keeps caches apart


# ---------------------------------------------------------------------------
# Loading, checking and saving model files
# ---------------------------------------------------------------------------

def _is_prob(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and 0.0 <= x <= 1.0


def _topo_order(ids, parents):
    """Stable topological order (keeps file order where possible)."""
    order, done, visiting = [], set(), set()

    def visit(n, path):
        if n in done:
            return
        if n in visiting:
            raise ModelError([f"Cycle in the network: {' -> '.join(path + [n])}"])
        visiting.add(n)
        for q in parents.get(n, []):
            if q in parents:
                visit(q, path + [n])
        visiting.discard(n)
        done.add(n)
        order.append(n)

    for n in ids:
        visit(n, [])
    return order


def check_model(data):
    """Return a list of problems in a model dictionary (empty = valid)."""
    errs = []
    if not isinstance(data, dict):
        return ["The file does not contain a JSON object."]
    if data.get("format") != FORMAT:
        errs.append(f'"format" must be "{FORMAT}".')
    if data.get("version", FORMAT_VERSION) > FORMAT_VERSION:
        errs.append("The file was written by a newer version of the program.")

    # Fault tree -----------------------------------------------------------
    ft = data.get("fault_tree")
    event_ids, gate_ids = [], []
    if not isinstance(ft, dict):
        errs.append('Missing "fault_tree" section.')
    else:
        for i, e in enumerate(ft.get("events", [])):
            eid = e.get("id")
            if not eid:
                errs.append(f"Fault tree event #{i + 1} has no id.")
                continue
            event_ids.append(eid)
            if not _is_prob(e.get("p")):
                errs.append(f"Event {eid}: probability p must be a number between 0 and 1.")
        for i, g in enumerate(ft.get("gates", [])):
            gid = g.get("id")
            if not gid:
                errs.append(f"Fault tree gate #{i + 1} has no id.")
                continue
            gate_ids.append(gid)
            t = g.get("type")
            ins = g.get("inputs") or []
            if t not in GATE_TYPES:
                errs.append(f"Gate {gid}: type must be one of {', '.join(GATE_TYPES)}.")
            if not ins:
                errs.append(f"Gate {gid} has no inputs.")
            if len(set(ins)) != len(ins):
                errs.append(f"Gate {gid} lists the same input twice.")
            if t == "VOTE":
                k = g.get("k")
                if not isinstance(k, int) or not 1 <= k <= len(ins):
                    errs.append(f"Gate {gid}: VOTE needs k between 1 and {len(ins)}.")
        all_ids = event_ids + gate_ids
        for x in {x for x in all_ids if all_ids.count(x) > 1}:
            errs.append(f"Fault tree id {x} is used more than once.")
        known = set(all_ids)
        for g in ft.get("gates", []):
            for c in g.get("inputs") or []:
                if c not in known:
                    errs.append(f"Gate {g.get('id')}: input {c} is not defined.")
        top = ft.get("top")
        if top not in gate_ids:
            errs.append(f'Fault tree "top" ({top}) must be one of the gates.')
        elif not errs:
            gparents = {g["id"]: list(g["inputs"]) for g in ft["gates"]}
            try:
                _topo_order(gate_ids, gparents)
            except ModelError as ex:
                errs += [p.replace("network", "fault tree") for p in ex.problems]
            else:
                reach, stack = set(), [top]
                while stack:
                    n = stack.pop()
                    if n not in reach:
                        reach.add(n)
                        stack += gparents.get(n, [])
                for x in all_ids:
                    if x not in reach:
                        errs.append(f"Fault tree element {x} is not connected to the top event.")

    # Bayesian network -----------------------------------------------------
    bn = data.get("bayesian_network")
    node_ids, params = [], {}
    if not isinstance(bn, dict):
        errs.append('Missing "bayesian_network" section.')
    else:
        nodes = bn.get("nodes", [])
        node_ids = [n.get("id") for n in nodes]
        if None in node_ids or "" in node_ids:
            errs.append("Every Bayesian network node needs an id.")
        for x in {x for x in node_ids if node_ids.count(x) > 1}:
            errs.append(f"Network node {x} is defined more than once.")
        known = set(node_ids)
        free = 0
        for n in nodes:
            nid = n.get("id")
            pars = n.get("parents") or []
            for q in pars:
                if q not in known:
                    errs.append(f"Node {nid}: parent {q} is not defined.")
            if len(set(pars)) != len(pars):
                errs.append(f"Node {nid} lists the same parent twice.")
            kind = n.get("kind")
            if kind == "logic":
                g = n.get("gate")
                if g not in GATE_TYPES:
                    errs.append(f"Logic node {nid}: gate must be one of {', '.join(GATE_TYPES)}.")
                if not pars:
                    errs.append(f"Logic node {nid} needs at least one parent.")
                if g == "VOTE" and not (isinstance(n.get("k"), int) and 1 <= n["k"] <= len(pars)):
                    errs.append(f"Logic node {nid}: VOTE needs k between 1 and {len(pars)}.")
            elif kind == "chance":
                free += 1
                rows = n.get("cpt") or []
                seen = set()
                for r in rows:
                    when = r.get("when") or {}
                    if set(when) != set(pars):
                        errs.append(f"Node {nid}: every CPT row must give a value for each "
                                    f"parent ({', '.join(pars) or 'none'}).")
                        continue
                    if not all(isinstance(v, bool) for v in when.values()):
                        errs.append(f"Node {nid}: parent values in the CPT must be true/false.")
                        continue
                    combo = tuple(when[q] for q in pars)
                    if combo in seen:
                        errs.append(f"Node {nid}: CPT row {_combo_text(pars, combo)} appears twice.")
                    seen.add(combo)
                    if not _is_prob(r.get("p")):
                        errs.append(f"Node {nid}: CPT probability must be between 0 and 1.")
                    name = r.get("param") or _auto_param(nid, combo)
                    if name in params:
                        errs.append(f"Parameter name {name} is used twice.")
                    params[name] = r.get("p")
                if len(seen) != 2 ** len(pars) and not any("CPT row" in e and nid in e for e in errs):
                    errs.append(f"Node {nid}: the CPT needs {2 ** len(pars)} rows "
                                f"(one per combination of parent values), found {len(seen)}.")
            else:
                errs.append(f'Node {nid}: kind must be "chance" or "logic".')
        if free > MAX_FREE_BN_NODES:
            errs.append(f"The network has {free} chance nodes; the exact solver "
                        f"supports at most {MAX_FREE_BN_NODES}.")
        if not any(e.startswith("Node") and "parent" in e and "not defined" in e for e in errs):
            try:
                _topo_order(node_ids, {n.get("id"): n.get("parents") or [] for n in nodes})
            except ModelError as ex:
                errs += ex.problems
        if bn.get("query") not in known:
            errs.append(f'Network "query" ({bn.get("query")}) must be one of the nodes.')
        for x in bn.get("compare", []):
            if x not in known:
                errs.append(f'"compare" node {x} is not in the network.')
        for x in bn.get("evidence_panel", []):
            if x not in known:
                errs.append(f'"evidence_panel" node {x} is not in the network.')
        oids = []
        for o in bn.get("options", []):
            oid = o.get("id")
            oids.append(oid)
            if not oid:
                errs.append("Every option needs an id.")
            if o.get("kind", "measure") not in ("measure", "threat"):
                errs.append(f'Option {oid}: kind must be "measure" or "threat".')
            for c in o.get("changes", []):
                op = c.get("op")
                if c.get("param") not in params:
                    errs.append(f"Option {oid}: parameter {c.get('param')} does not exist.")
                if op not in ("scale", "set", "relative"):
                    errs.append(f'Option {oid}: op must be "scale", "set" or "relative".')
                elif op == "set" and not _is_prob(c.get("value")):
                    errs.append(f"Option {oid}: set value must be between 0 and 1.")
                elif op in ("scale", "relative") and not isinstance(c.get("factor"), (int, float)):
                    errs.append(f"Option {oid}: {op} needs a numeric factor.")
                if op == "relative" and c.get("from") not in params:
                    errs.append(f"Option {oid}: parameter {c.get('from')} does not exist.")
        for x in {x for x in oids if oids.count(x) > 1}:
            errs.append(f"Option id {x} is used more than once.")

    # Validation and sample data -------------------------------------------
    cols = (data.get("validation") or {}).get("columns", [])
    for c in cols:
        if c.get("node") not in node_ids:
            errs.append(f"Validation column {c.get('column')}: node {c.get('node')} "
                        f"is not in the network.")
    for k, v in ((data.get("sample_data") or {}).get("overrides") or {}).items():
        if k not in params:
            errs.append(f"sample_data override {k} is not a network parameter.")
        elif not _is_prob(v):
            errs.append(f"sample_data override {k} must be between 0 and 1.")
    return errs


def _auto_param(node, combo):
    return node if not combo else f"{node}_{''.join(str(int(v)) for v in combo)}"


def _combo_text(parents, combo):
    return ", ".join(f"{q}={'yes' if v else 'no'}" for q, v in zip(parents, combo)) or "(no parents)"


def read_model(path):
    """Read and check a model file; returns the dictionary or raises ModelError."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as ex:
        raise ModelError([f"Not valid JSON (line {ex.lineno}, column {ex.colno}): {ex.msg}"])
    problems = check_model(data)
    if problems:
        raise ModelError(problems)
    return data


def load_model(path=DEFAULT_MODEL_PATH):
    """Load a model file and make it the active model."""
    data = read_model(path)
    set_model(data, path)
    return data


def _replace(target, items):
    """Update a module table in place (other modules keep valid references)."""
    target.clear()
    target.update(items)


def set_model(data, path=None):
    """Make an already checked model dictionary the active model."""
    global MODEL, MODEL_PATH, MODEL_NAME, MODEL_DESCRIPTION, UNIT, ITEMS
    global TOP, QUERY, SECOND, _MODEL_ID
    problems = check_model(data)
    if problems:
        raise ModelError(problems)
    MODEL = copy.deepcopy(data)
    MODEL_PATH = path
    meta = data.get("meta") or {}
    MODEL_NAME = meta.get("name") or (os.path.basename(path) if path else "Model")
    MODEL_DESCRIPTION = meta.get("description", "")
    UNIT = meta.get("unit", "per case")
    ITEMS = meta.get("items", "cases")
    _MODEL_ID += 1
    _WORLD_CACHE.clear()

    ft = data["fault_tree"]
    TOP = ft["top"]
    _replace(BASIC_EVENTS, {e["id"]: (e.get("description") or e.get("label") or e["id"],
                                      e.get("layer", ""), float(e["p"])) for e in ft["events"]})
    _replace(GATES, {g["id"]: (g["type"], list(g["inputs"]),
                               g.get("description") or g.get("label") or g["id"])
                     for g in ft["gates"]})
    _replace(GATE_K, {g["id"]: g["k"] for g in ft["gates"] if g["type"] == "VOTE"})
    _replace(FTA_SHORT, {x["id"]: x.get("label") or x["id"] for x in ft["events"] + ft["gates"]})

    bn = data["bayesian_network"]
    nodes = {n["id"]: n for n in bn["nodes"]}
    parents = {i: list(n.get("parents") or []) for i, n in nodes.items()}
    NODE_ORDER[:] = _topo_order(list(nodes), parents)
    _replace(BN_PARENTS, parents)
    _replace(BN_LABELS, {i: n.get("description") or n.get("label") or i for i, n in nodes.items()})
    _replace(BN_SHORT, {i: n.get("label") or i for i, n in nodes.items()})
    _replace(BN_LAYOUT, {i: tuple(n["layout"]) for i, n in nodes.items() if n.get("layout")})
    params, keys, logic, kk = {}, {}, {}, {}
    for i in NODE_ORDER:
        n = nodes[i]
        if n["kind"] == "logic":
            logic[i] = n["gate"]
            if n["gate"] == "VOTE":
                kk[i] = n["k"]
            continue
        table = {}
        for r in n["cpt"]:
            combo = tuple(r["when"][q] for q in parents[i])
            name = r.get("param") or _auto_param(i, combo)
            table[combo] = name
            params[name] = float(r["p"])
        keys[i] = dict(sorted(table.items()))
    _replace(DEFAULT_BN_PARAMS, params)
    _replace(CPT_KEYS, keys)
    _replace(DET_LOGIC, logic)
    _replace(DET_K, kk)
    QUERY = bn["query"]
    cmp_nodes = [x for x in bn.get("compare", []) if x != QUERY]
    SECOND = cmp_nodes[0] if cmp_nodes else QUERY
    EVIDENCE_NODES[:] = bn.get("evidence_panel") or [
        i for i in NODE_ORDER if i in keys or i == QUERY][:12]
    opts = bn.get("options", [])
    _replace(OPTIONS, {o["id"]: o.get("label") or o["id"] for o in opts})
    _replace(OPTION_KIND, {o["id"]: o.get("kind", "measure") for o in opts})
    _replace(OPTION_CHANGES, {o["id"]: list(o.get("changes", [])) for o in opts})

    _replace(OBSERVABLES, {c["column"]: c["node"]
                           for c in (data.get("validation") or {}).get("columns", [])})
    sd = data.get("sample_data") or {}
    _replace(SAMPLE_DATA, {"n": int(sd.get("n", 200)), "seed": sd.get("seed", 2026),
                           "overrides": dict(sd.get("overrides") or {})})


def top_label():
    """Description of the top event, lower case for use inside a sentence."""
    return _lower_first(GATES[TOP][2])


def query_label():
    """Description of the network's query node, for use inside a sentence."""
    return _lower_first(BN_LABELS[QUERY])


def _lower_first(s):
    return s if s[:2].isupper() else s[:1].lower() + s[1:]


def slug():
    """Short file-name friendly name of the active model."""
    base = os.path.splitext(os.path.basename(MODEL_PATH or ""))[0] or MODEL_NAME
    out = "".join(ch.lower() if ch.isalnum() else "_" for ch in base).strip("_")
    return out or "model"


def model_dict(fta_p=None, bn_params=None, meta=None):
    """The active model as a dictionary, with optional updated probabilities.

    fta_p:     {event: p} for the fault tree (e.g. values edited in the GUI)
    bn_params: {parameter: p} for the network CPTs
    """
    data = copy.deepcopy(MODEL)
    data["format"], data["version"] = FORMAT, FORMAT_VERSION
    if meta:
        data.setdefault("meta", {}).update(meta)
    for e in data["fault_tree"]["events"]:
        if fta_p and e["id"] in fta_p:
            e["p"] = fta_p[e["id"]]
    for n in data["bayesian_network"]["nodes"]:
        if n["kind"] != "chance":
            continue
        pars = n.get("parents") or []
        for r in n["cpt"]:
            name = r.get("param") or _auto_param(n["id"], tuple(r["when"][q] for q in pars))
            if bn_params and name in bn_params:
                r["p"] = bn_params[name]
    return data


def save_model(path, fta_p=None, bn_params=None, meta=None):
    """Write the active model (with optional new values) to a JSON file."""
    data = model_dict(fta_p, bn_params, meta)
    problems = check_model(data)
    if problems:
        raise ModelError(problems)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)
    return path


# ---------------------------------------------------------------------------
# Fault tree
# ---------------------------------------------------------------------------

def default_fta_probabilities():
    return {k: v[2] for k, v in BASIC_EVENTS.items()}


def _gate(gates, node):
    g = gates[node]
    return g[0], g[1], (g[3] if len(g) > 3 else GATE_K.get(node))


def _vote(vals, k):
    """P(at least k of the independent events are true)."""
    dist = [1.0]                       # dist[j] = P(exactly j true so far)
    for v in vals:
        nxt = [0.0] * (len(dist) + 1)
        for j, pj in enumerate(dist):
            nxt[j] += pj * (1 - v)
            nxt[j + 1] += pj * v
        dist = nxt
    return sum(dist[k:])


def _combine(kind, vals, k=None):
    if kind == "AND":
        return prod(vals)
    if kind == "VOTE":
        return _vote(vals, k)
    return 1 - prod(1 - v for v in vals)


def repeated_events(gates=None, top=None):
    """Basic events reached from the top event along more than one path."""
    gates = GATES if gates is None else gates
    top = TOP if top is None else top
    order = []                         # gates in topological order from the top
    seen = set()

    def visit(n):
        if n in seen or n not in gates:
            return
        seen.add(n)
        for c in _gate(gates, n)[1]:
            visit(c)
        order.append(n)

    visit(top)
    paths = {top: 1}                   # number of paths from the top to each node
    for g in reversed(order):
        for c in _gate(gates, g)[1]:
            paths[c] = paths.get(c, 0) + paths[g]
    return [e for e, n in paths.items() if e not in gates and n > 1]


def gate_probabilities(p, gates=None, top=None):
    """Probability of every gate, assuming independent basic events.

    Exact also when a basic event appears in more than one branch: the
    repeated events are conditioned on (Shannon decomposition).
    """
    gates = GATES if gates is None else gates

    def bottom_up(q):
        cache = {}

        def prob(node):
            if node in q:
                return q[node]
            if node in cache:
                return cache[node]
            kind, children, k = _gate(gates, node)
            r = _combine(kind, [prob(c) for c in children], k)
            cache[node] = r
            return r

        for g in gates:
            prob(g)
        return cache

    if top is not None:
        roots = [top]
    elif gates is GATES:
        roots = [TOP]
    else:                              # custom gate table: check every root
        children = {c for g in gates for c in _gate(gates, g)[1]}
        roots = [g for g in gates if g not in children]
    shared = sorted({e for r in roots for e in repeated_events(gates, r)}, key=_event_order)
    if not shared:
        return bottom_up(p)
    if len(shared) > MAX_REPEATED_EVENTS:
        raise ValueError(f"{len(shared)} repeated events: too many for the exact method.")
    total = {}
    for values in product((False, True), repeat=len(shared)):
        w = 1.0
        for e, v in zip(shared, values):
            w *= p[e] if v else 1 - p[e]
        if w == 0:
            continue
        res = bottom_up({**p, **{e: float(v) for e, v in zip(shared, values)}})
        for g, r in res.items():
            total[g] = total.get(g, 0.0) + w * r
    return {g: total.get(g, 0.0) for g in gates}


def top_probability(p, gates=None, top=None):
    top = TOP if top is None else top
    return gate_probabilities(p, gates, top)[top]


def minimal_cut_sets(node=None, gates=None):
    """Minimal cut sets by top-down expansion (MOCUS)."""
    gates = GATES if gates is None else gates
    node = TOP if node is None else node
    if node not in gates:
        return [frozenset([node])]
    kind, children, k = _gate(gates, node)
    child_sets = [minimal_cut_sets(c, gates) for c in children]
    if kind == "OR":
        sets = [s for cs in child_sets for s in cs]
    elif kind == "AND":
        sets = _and_sets(child_sets)
    else:                               # VOTE k/n = OR of the AND of every k-subset
        sets = [s for sub in combinations(child_sets, k) for s in _and_sets(sub)]
    sets = list(set(sets))
    return [s for s in sets if not any(o < s for o in sets)]


def _and_sets(child_sets):
    sets = [frozenset()]
    for cs in child_sets:
        sets = [a | b for a in sets for b in cs]
    return sets


def ranked_cut_sets(p, gates=None):
    """Cut sets with their probabilities, largest first."""
    rows = [(sorted(cs, key=_event_order), prod(p[e] for e in cs))
            for cs in minimal_cut_sets(None, gates)]
    return sorted(rows, key=lambda r: -r[1])


def importance(p, gates=None):
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


def sensitivity(p, low=0.5, high=2.0, gates=None):
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
    keys = list(BASIC_EVENTS)
    return keys.index(e) if e in BASIC_EVENTS else len(keys)


def fta_report(p):
    """Text report: gate tree, cut sets and importance."""
    g = gate_probabilities(p)
    shared = repeated_events()
    w = max([7] + [len(x) + 1 for x in list(GATES) + list(BASIC_EVENTS)])
    lines = ["FAULT TREE - " + MODEL_NAME, ""]

    def walk(node, depth):
        pad = "    " * depth
        if node in GATES:
            kind, children, k = _gate(GATES, node)
            desc = GATES[node][2]
            label = f"{k}/{len(children)}" if kind == "VOTE" else kind
            lines.append(f"{pad}{node:<{w}}{label:<4}{desc:<44}{g[node]:.5f}")
            for c in children:
                walk(c, depth + 1)
        else:
            desc = BASIC_EVENTS[node][0]
            if node in shared:
                desc = desc[:43 - 11] + " (repeated)"
            lines.append(f"{pad}{node:<{w}}{'':<4}{desc:<44}{p[node]:.5f}")

    walk(TOP, 0)
    q = g[TOP]
    lines += ["", f"Top event probability: {q:.5f} {UNIT} "
                  f"(about 1 in {1 / q:,.0f} {ITEMS})" if q > 0 else
              "Top event probability: 0", "",
              "MINIMAL CUT SETS (largest first)"]
    for cs, pr in ranked_cut_sets(p)[:12]:
        lines.append(f"  {' . '.join(cs):<18}{pr:.6f}   {pr / q:6.1%} of top" if q > 0
                     else f"  {' . '.join(cs):<18}{pr:.6f}")
    lines += ["", "IMPORTANCE", f"  {'Event':<{w}}{'Fussell-Vesely':>16}{'Birnbaum':>12}"]
    for r in importance(p):
        lines.append(f"  {r['event']:<{w}}{r['fussell_vesely']:>16.3f}{r['birnbaum']:>12.5f}")
    if shared:
        lines += ["", "Repeated events (handled exactly): " + ", ".join(shared)]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Bayesian network
# ---------------------------------------------------------------------------

def apply_options(params, options):
    """Parameters after switching on the selected options (in model order)."""
    p = dict(params)
    for oid, changes in OPTION_CHANGES.items():
        if not options.get(oid):
            continue
        for c in changes:
            op, name = c["op"], c["param"]
            if op == "scale":
                v = p[name] * c["factor"]
            elif op == "relative":
                v = p[c["from"]] * c["factor"]
            else:
                v = c["value"]
            p[name] = min(1.0, max(0.0, v))
    return p


class _Network(list):
    """Node list in topological order, tagged with its effective parameters.

    The tag lets bn_query reuse the joint distribution table between queries.
    """
    key = None


def _logic_fn(kind, k=None):
    if kind == "AND":
        return lambda *x: all(x)
    if kind == "VOTE":
        return lambda *x: sum(x) >= k
    return lambda *x: any(x)


def _cpt_fn(table, p):
    return lambda *x: p[table[x]]


def build_bn(params=None, options=None):
    """Return the node list in topological order."""
    p = apply_options(params or DEFAULT_BN_PARAMS, options or {})
    nodes = _Network()
    for name in NODE_ORDER:
        if name in DET_LOGIC:
            nodes.append({"name": name, "type": "det", "parents": BN_PARENTS[name],
                          "fn": _logic_fn(DET_LOGIC[name], DET_K.get(name))})
        else:
            nodes.append({"name": name, "type": "cpt", "parents": BN_PARENTS[name],
                          "fn": _cpt_fn(CPT_KEYS[name], p)})
    nodes.key = (_MODEL_ID, tuple(sorted(p.items())))
    return nodes


_WORLD_CACHE = {}


def _worlds(nodes):
    """All joint states with non-zero weight, as (weight, bitmask) pairs.

    Bit i of the mask is set when node i is True. Cached per parameter set,
    so evidence queries only filter this table instead of re-enumerating.
    """
    key = getattr(nodes, "key", None)
    if key is not None and key in _WORLD_CACHE:
        return _WORLD_CACHE[key]
    names = [n["name"] for n in nodes]
    index = {name: i for i, name in enumerate(names)}
    free = [n["name"] for n in nodes if n["type"] == "cpt"]
    worlds = []
    for values in product((False, True), repeat=len(free)):
        draw = dict(zip(free, values))
        state, w, mask = {}, 1.0, 0
        for n in nodes:
            name = n["name"]
            args = [state[x] for x in n["parents"]]
            if n["type"] == "det":
                v = n["fn"](*args)
            else:
                v = draw[name]
                pt = n["fn"](*args)
                w *= pt if v else 1 - pt
            state[name] = v
            if v:
                mask |= 1 << index[name]
        if w > 0:
            worlds.append((w, mask))
    result = (names, index, worlds)
    if key is not None:
        if len(_WORLD_CACHE) > 64:
            _WORLD_CACHE.clear()
        _WORLD_CACHE[key] = result
    return result


def bn_query(nodes, evidence=None, do=None):
    """Exact inference by enumeration.

    evidence: {node: bool} observed values (conditioning).
    do:       {node: bool} forced values (intervention, ignores the node's CPT).
    Returns {node: P(node = True | evidence, do)}.
    """
    evidence = evidence or {}
    do = do or {}
    if not do:
        names, index, worlds = _worlds(nodes)
        ev_mask = ev_val = 0
        for k, val in evidence.items():
            ev_mask |= 1 << index[k]
            if val:
                ev_val |= 1 << index[k]
        totals = [0.0] * len(names)
        z = 0.0
        for w, m in worlds:
            if m & ev_mask != ev_val:
                continue
            z += w
            while m:
                low = m & -m
                totals[low.bit_length() - 1] += w
                m ^= low
        if z == 0:
            raise ValueError("The evidence is impossible under this model.")
        return {name: totals[i] / z for i, name in enumerate(names)}
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


def option_variants():
    """(label, options) pairs: baseline, each measure, all measures, each threat."""
    measures = [o for o, k in OPTION_KIND.items() if k == "measure"]
    threats = [o for o, k in OPTION_KIND.items() if k == "threat"]
    variants = [("Baseline", {})]
    variants += [(OPTIONS[o], {o: True}) for o in measures]
    if len(measures) >= 2:
        variants.append(("Both measures" if len(measures) == 2 else "All measures",
                         {o: True for o in measures}))
    variants += [(OPTIONS[o], {o: True}) for o in threats]
    return variants


def variant_kind(options):
    """"baseline", "measure" or "threat" for a set of switched-on options."""
    kinds = {OPTION_KIND[o] for o, on in options.items() if on}
    return "threat" if "threat" in kinds else "measure" if kinds else "baseline"


def compare_options(evidence=None, params=None):
    """P(query node) for each option variant under the same evidence.

    Rows: (label, P(QUERY), P(SECOND)) in the order of option_variants().
    """
    rows = []
    for label, opts in option_variants():
        post = bn_query(build_bn(params, opts), evidence)
        rows.append((label, post[QUERY], post[SECOND]))
    return rows


# ---------------------------------------------------------------------------
# Validation against batch records
# ---------------------------------------------------------------------------

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


# The bundled VERDA model is the default.
load_model()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        load_model(sys.argv[1])
    print(fta_report(default_fta_probabilities()))
    print()
    post = bn_query(build_bn())
    print(f"BN: P({BN_LABELS[QUERY]}) = {post[QUERY]:.5f}")
