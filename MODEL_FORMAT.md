# VERDA Risk Model Lab - model file format

**Developer:** József Szeles, Department of System Engineering, University of Pannonia

One model is one JSON file. It holds the system description, the fault tree, the
Bayesian network, the scenarios (options), the validation columns and the node positions.
**Export model…** (tab 3, or Ctrl+E) writes the current model, including the values
you edited on tabs 1 and 3, to a new file. Instructors open a model file with
**Ctrl+Shift+O**, or start the program with the file name:
`python verda_app.py models/pump_station.json`.

The program checks a file before loading it and lists every problem it finds, such as
an unknown input, a probability outside 0-1, a missing CPT row or a cycle. If the file
has problems, the model that was open before stays open.

Bundled examples in the `models` folder:

| File | What it shows |
| --- | --- |
| `verda.json` | The VERDA production cell used in the course (the default model). |
| `verda_consultant.json` | VERDA as "delivered by a consultant", with three planted errors for the final assignment. |
| `pump_station.json` | A small second system with a 2-out-of-3 (VOTE) gate, an event that appears in two branches, and automatic network layout. |

The easiest way to start a new model is to copy `pump_station.json` and edit it in any
text editor.

## Top level

```json
{
  "format": "verda-risk-model",
  "version": 1,
  "meta": { ... },
  "fault_tree": { ... },
  "bayesian_network": { ... },
  "validation": { ... },
  "sample_data": { ... }
}
```

`validation` and `sample_data` are optional.

## meta

| Key | Meaning |
| --- | --- |
| `name` | Shown in the header and the window title. |
| `description`, `author`, `notes` | Free text. |
| `exported`, `exported_from` | Added by *Export model…*: date and time, and the model it was made from. |
| `unit` | How probabilities are counted, e.g. `"per batch"`, `"per day"`. |
| `items` | Plural noun for "about 1 in N …", e.g. `"batches"`, `"days"`. |

## fault_tree

```json
"fault_tree": {
  "top": "TOP",
  "events": [
    {"id": "B1", "label": "Under-weighed", "description": "Preservative under-weighed",
     "layer": "Human", "p": 0.005}
  ],
  "gates": [
    {"id": "TOP", "label": "Unsafe release", "description": "Unsafe batch released",
     "type": "AND", "inputs": ["CONTAM", "QCFAIL"]},
    {"id": "PUMPS", "label": "Too few pumps", "type": "VOTE", "k": 2, "inputs": ["PA", "PB", "PC"]}
  ]
}
```

- `label` is the short text in the diagram. `description` is the long text used in
  reports and as the result caption (for the top gate).
- `layer` is optional. Suggested values are Human, Technology, Organisation, Process
  and Data.
- `type` is one of the following:
  - `AND`: all inputs must occur.
  - `OR`: at least one input occurs.
  - `VOTE`: at least `k` of the inputs occur.
- An input is either an event id or a gate id. Every element must be connected to the
  top gate.
- An event may appear under several gates (a *repeated event*). The program still
  computes the top event exactly by conditioning on the repeated events. In the diagram
  these events have a dashed frame.

## bayesian_network

```json
"bayesian_network": {
  "query": "U",
  "compare": ["U", "C"],
  "evidence_panel": ["TP", "DI", "PF", "U"],
  "nodes": [ ... ],
  "options": [ ... ]
}
```

| Key | Meaning |
| --- | --- |
| `query` | The node whose probability is the headline result (usually the hazard). |
| `compare` | Columns of the option comparison table. The second entry is optional. |
| `evidence_panel` | Nodes that get yes/no/unknown buttons on the left. You can set evidence on any other node by right-clicking it in the diagram. |

All nodes are binary (yes/no). There are two kinds:

**Chance node.** Its probability table (CPT) has one row per combination of parent
values:

```json
{"id": "SS", "label": "Sanitation skipped", "description": "Sanitation skipped (B6)",
 "kind": "chance", "parents": ["TP", "DI"],
 "cpt": [
   {"when": {"TP": false, "DI": false}, "p": 0.005, "param": "SS_00"},
   {"when": {"TP": false, "DI": true},  "p": 0.02,  "param": "SS_01"},
   {"when": {"TP": true,  "DI": false}, "p": 0.02,  "param": "SS_10"},
   {"when": {"TP": true,  "DI": true},  "p": 0.08,  "param": "SS_11"}
 ],
 "layout": [0.50, 1]}
```

- `p` is P(node = yes) for that row.
- `param` is the parameter name shown in the editors, used by options and
  `sample_data`. It is optional. Without it, the name is the node id for a root node,
  or the id plus the parent values, for example `PA_0` and `PA_1`.
- A root node (no parents) has a single row: `{"when": {}, "p": 0.2}`.

**Logic node.** Its table is fixed by a gate. The gate types are the same as in the
fault tree (`AND`, `OR`, `VOTE` with `k`):

```json
{"id": "U", "label": "Unsafe release", "kind": "logic", "gate": "AND", "parents": ["C", "QM"]}
```

`layout` is optional: `[x, row]`, where x is between 0 (left) and 1 (right) and row is
0 for the top row. If any node has no layout, the program arranges the nodes
automatically by depth.

The order of the nodes in the file does not matter.

### options

Options are changes to the system: improvement measures or threats. Each one is a
tick box on tab 3, and each one is a row of the comparison table.

```json
{"id": "second_probe", "label": "Second temperature probe", "kind": "measure",
 "changes": [{"param": "P_PF", "op": "scale", "factor": 0.05}]}
```

| `op` | Effect |
| --- | --- |
| `scale` | parameter × `factor` |
| `set` | parameter = `value` |
| `relative` | parameter = parameter `from` × `factor` (e.g. "with the paper fallback, instructions-down behaves like instructions-up × 1.5") |

Results are capped to 0-1. `kind` is `measure` or `threat`. When there are two or more
measures, the comparison table also has a "Both measures" or "All measures" row.

## validation

Maps CSV columns (0/1 per row) to network nodes for tab 4:

```json
"validation": {"columns": [{"column": "wifi_down", "node": "DI"}]}
```

## sample_data

Settings for **Generate sample data…** on tab 4. The records are drawn from the network
with some parameters replaced by "true" values, so students have a mismatch to find:

```json
"sample_data": {"n": 200, "seed": 2026, "overrides": {"P_TP": 0.35}}
```

## Limits

- The Bayesian network is solved exactly by enumeration, with at most 22 chance nodes.
  Logic nodes are free.
- The fault tree is exact with up to 16 repeated events.
- Basic events are independent. To model a common cause, use a shared parent node in
  the network, or a repeated event in the fault tree.
