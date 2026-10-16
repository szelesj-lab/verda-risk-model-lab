"""
Generate fictional batch records for the validation exercise.

Developer: József Szeles, Department of System Engineering, University of Pannonia

The records are drawn from the Bayesian network of the active model, with
the "true" parameter values given in the model file under
sample_data.overrides. For VERDA the real cell has more handover time
pressure than the model assumes (0.35 instead of 0.2). Students should
find this mismatch on the Validation tab, recalibrate P_TP and explain
the effect on the top event.

    python generate_data.py [output.csv] [number_of_batches] [--model file.json]
"""

import csv
import random
import sys

import verda_model as vm


def true_params():
    """Network parameters of the simulated 'real' system."""
    return {**vm.DEFAULT_BN_PARAMS, **vm.SAMPLE_DATA["overrides"]}


TRUE_PARAMS = true_params()   # for the bundled VERDA model


def sample_batches(n=None, seed=None, params=None):
    n = vm.SAMPLE_DATA["n"] if n is None else n
    seed = vm.SAMPLE_DATA["seed"] if seed is None else seed
    rng = random.Random(seed)
    nodes = vm.build_bn(params or true_params())
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


def write_csv(path="verda_batch_records.csv", n=None, seed=None):
    rows = sample_batches(n, seed)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--model" in args:
        i = args.index("--model")
        vm.load_model(args[i + 1])
        del args[i:i + 2]
    out = args[0] if args else "verda_batch_records.csv"
    n = int(args[1]) if len(args) > 1 else None
    print("Wrote", write_csv(out, n))
