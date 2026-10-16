# VERDA Risk Model Teaching Lab

**Developer:** József Szeles, Department of System Engineering, University of Pannonia

Teaching software for the course *Risk and Resilience Modelling of Socio-Technical
Manufacturing Systems*. Students work with a ready model of the fictional VERDA
skincare production cell: a fault tree and a Bayesian network built on the same logic.
All probabilities are illustrative values per batch.

The system is described in a **model file** (`models/*.json`). VERDA is the bundled
default. Students can **export** their current values (*Export model…* on tab 3, or
Ctrl+E) to a model file, e.g. to hand it in. Opening another model is deliberately not on
screen (instructor function): press **Ctrl+Shift+O**, or start the program with the file
name. See [MODEL_FORMAT.md](MODEL_FORMAT.md).

## Files

| File | Purpose |
| --- | --- |
| `verda_model.py` | The engine: loads and checks model files; fault tree (exact, also with repeated events and k-out-of-n gates), cut sets, importance, sensitivity, Bayesian network (exact inference), validation. Standard library only. |
| `models/verda.json` | The VERDA model (default). |
| `models/verda_consultant.json` | VERDA with three planted errors (final assignment). |
| `models/pump_station.json` | Small second example: 2-out-of-3 gate, repeated event, automatic layout. |
| `MODEL_FORMAT.md` | How to write a model file. |
| `verda_app.py` | Desktop interface (tkinter) with four tabs. |
| `verda_diagrams.py` | Graphical fault tree and Bayesian network views. |
| `verda_theme.py` | Visual theme: colours, fonts, cards (standard library only). |
| `generate_data.py` | Creates fictional batch records for the validation exercise. |
| `verda_batch_records.csv` | 200 sample batch records (seed 2026). |
| `build_exe.bat` | Builds `VERDA_Risk_Lab.exe` on Windows with PyInstaller (the VERDA model is built in). |
| `tests/` | Unit tests (`python -m unittest discover -s tests`). |

## Run

```
python verda_app.py                          # the interface (VERDA model)
python verda_app.py models/pump_station.json # the interface with another model
python verda_model.py [model.json]           # text report in the terminal
python generate_data.py my_records.csv 500   # new data set
python generate_data.py out.csv --model models/pump_station.json
```

## Build the .exe (Windows)

Install Python 3.10+ from python.org, then double-click `build_exe.bat`.
The result is `dist\VERDA_Risk_Lab.exe` (single file, no Python needed on student PCs).
Copy the `models` folder next to the .exe so the other models are at hand with Ctrl+Shift+O,
or start it as `VERDA_Risk_Lab.exe models\pump_station.json`.

## The four tabs

1. **Fault tree** - basic-event probabilities on the left (type a value, press Enter or
   *Calculate*), the drawn tree on the right with AND/OR gate symbols and basic events
   shaded by importance. Underneath: the minimal cut sets (click one to highlight its
   path) and details of the selected event (click an event in the diagram; its input
   field on the left is selected too). *Full report* opens the gate values, cut sets
   and Fussell-Vesely / Birnbaum importance as text.
2. **Sensitivity** - tornado chart: top event with each event scaled down and up.
3. **Bayesian network** - evidence (yes / no / unknown) and system changes (second
   temperature probe, paper fallback, cyber incident) on the left, the drawn network on
   the right. **Left-click** a node to select it: the panel underneath shows its CPT,
   editable row by row (Enter or *Apply*; *Reset this node*). Logic nodes (AND/OR) show
   their fixed rule. **Right-click** a node to cycle its evidence. Next to the CPT
   editor: all improvement options compared under the same evidence. *Edit all
   parameters* opens every CPT value at once; *Node probability table* shows all node
   values as a table.
4. **Validation** - load batch records and compare observed frequencies (95 % Wilson
   interval) with the model's predictions.

Both diagrams can be saved as `.eps` vector images for slides and reports.

## Planted finding for instructors

The sample data come from a cell with handover time pressure of 0.35, while the model
assumes 0.2. The Validation tab flags `shift_handover_pressure` as **CHECK MODEL**
(observed 0.395, interval 0.33-0.46). Students should recalibrate `P_TP` under
*Edit all parameters* (tab 3) and explain how the top event changes. All other columns are
consistent, which is itself a lesson: rare events (unsafe release, probe fault) cannot
be validated with 200 batches.

## Reference values (defaults)

| Query | Value |
| --- | --- |
| FTA top event | 0.0019 per batch (about 1 in 527) |
| Largest cut set | B6 . B8, 26 % of top event |
| BN top event | 0.0020 |
| BN, Wi-Fi down: sanitation skipped | 0.032 (baseline 0.0092) |
| BN, Wi-Fi down: unsafe release | 0.0049 |
| BN, Wi-Fi down + paper fallback | 0.0025 |

## Final assignment model

`models/verda_consultant.json` is the VERDA model "as delivered by a consultant". It contains three
planted errors in the network: `B8` = 0.95, `SS_11` = 0.008 and `RB_1` = 0.006. With these errors,
P(unsafe release) is 0.0237. Against the sample batch records, three columns are flagged CHECK
MODEL: `shift_handover_pressure`, `released_before_result` and `unsafe_release`. Students must find
the errors, fix them and justify each change.

Keep this section out of the copy you give to students.

## Checking an exported model

A student's export is an ordinary model file. Its `meta` block records `exported` (date and time)
and `exported_from` (the model it was made from). Open it with Ctrl+Shift+O to check it, or compare it
with the original in any text or diff tool: only the changed `p` values differ.
