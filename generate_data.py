"""
Generate fictional VERDA batch records for the validation exercise.

Developer: József Szeles, Department of System Engineering, University of Pannonia

The records are drawn from the Bayesian network, but the "real" cell has
more handover time pressure than the model assumes (0.35 instead of 0.2).
Students should find this mismatch on the Validation tab, recalibrate
P_TP and explain the effect on the top event.

    python generate_data.py [output.csv] [number_of_batches]
"""

import csv
import random
import sys

import verda_model as vm

TRUE_PARAMS = {**vm.DEFAULT_BN_PARAMS, "P_TP": 0.35}


def sample_batches(n=200, seed=2026, params=TRUE_PARAMS):
    rng = random.Random(seed)
    nodes = vm.build_bn(params)
    rows = []
    for i in range(n):
        s = {}
        for node in nodes:
            args = [s[x] for x in node["parents"]]
            if node["type"] == "det":
                s[node["name"]] = node["fn"](*args)
            else:
                s[node["name"]] = rng.random() < node["fn"](*args)
        row = {"batch_id": f"VB-{i + 1:04d}"}
        row.update({col: int(s[n_]) for col, n_ in vm.OBSERVABLES.items()})
        rows.append(row)
    return rows


def write_csv(path="verda_batch_records.csv", n=200, seed=2026):
    rows = sample_batches(n, seed)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "verda_batch_records.csv"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    print("Wrote", write_csv(out, n))
