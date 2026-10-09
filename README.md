# VERDA Risk Model Teaching Lab

**Developer:** József Szeles, Department of System Engineering, University of Pannonia

Teaching software for the course *Risk and Resilience Modelling of Socio-Technical
Manufacturing Systems*. Students work with one ready model of the fictional VERDA
skincare production cell: a fault tree and a Bayesian network built on the same logic.
All probabilities are illustrative values per batch.

## Files

| File | Purpose |
| --- | --- |
| `verda_model.py` | The model: fault tree, cut sets, importance, sensitivity, Bayesian network (exact inference), validation. Standard library only. |
| `verda_app.py` | Desktop interface (tkinter) with four tabs. |
| `verda_diagrams.py` | Graphical fault tree and Bayesian network views. |
| `generate_data.py` | Creates fictional batch records for the validation exercise. |
| `verda_batch_records.csv` | 200 sample batch records (seed 2026). |
| `build_exe.bat` | Builds `VERDA_Risk_Lab.exe` on Windows with PyInstaller. |

## Run

```
python verda_app.py        # the interface
python verda_model.py      # text report in the terminal
python generate_data.py my_records.csv 500   # new data set
```

## Build the .exe (Windows)

Install Python 3.10+ from python.org, then double-click `build_exe.bat`.
The result is `dist\VERDA_Risk_Lab.exe` (single file, no Python needed on student PCs).

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
