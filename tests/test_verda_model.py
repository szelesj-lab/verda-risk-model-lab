"""
Unit tests for the VERDA risk model.

Developer: József Szeles, Department of System Engineering, University of Pannonia

Run from the repository root:

    python -m unittest discover -s tests -v
    (or: python -m pytest tests)

The tests check three things:
  1. Reference values  - the numbers quoted in the course material and answer key.
  2. Independent checks - fault-tree results recomputed by brute-force enumeration,
                          and the Bayesian network reduced to the fault tree.
  3. Behaviour          - options, evidence, validation, sample data, error handling.
"""

import csv
import itertools
import math
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import verda_model as vm          # noqa: E402
import generate_data              # noqa: E402

DEFAULT_FTA = vm.default_fta_probabilities()
DEFAULT_BN = vm.DEFAULT_BN_PARAMS
SAMPLE_CSV = os.path.join(ROOT, "verda_batch_records.csv")


def top(**changes):
    return vm.top_probability({**DEFAULT_FTA, **changes})


def bn(evidence=None, options=None, params=None, do=None):
    return vm.bn_query(vm.build_bn(params or DEFAULT_BN, options), evidence, do)


def brute_force_top(p):
    """Exact top-event probability by enumerating all 2^10 basic-event states."""
    events = list(p)
    total = 0.0
    for states in itertools.product((False, True), repeat=len(events)):
        s = dict(zip(events, states))
        w = math.prod(p[e] if s[e] else 1 - p[e] for e in events)

        def val(node):
            if node in s:
                return s[node]
            kind, children, _ = vm.GATES[node]
            vals = [val(c) for c in children]
            return all(vals) if kind == "AND" else any(vals)

        if val("TOP"):
            total += w
    return total


# ---------------------------------------------------------------------------
# 1. Fault tree
# ---------------------------------------------------------------------------

class FaultTreeReferenceValues(unittest.TestCase):

    def test_default_top_event(self):
        q = top()
        self.assertAlmostEqual(q, 0.0018960, places=6)
        self.assertEqual(round(1 / q), 527)

    def test_default_gate_values(self):
        g = vm.gate_probabilities(DEFAULT_FTA)
        expected = {"HOT": 0.003, "PRES": 0.01393, "NOZZLE": 0.01198,
                    "CONTAM": 0.02574, "QCFAIL": 0.07366, "TOP": 0.00190}
        for gate, value in expected.items():
            with self.subTest(gate=gate):
                self.assertAlmostEqual(g[gate], value, places=5)

    def test_lab_scenarios(self):
        cases = {
            "B2 certain (Lab 1)": (dict(B2=1), 0.07366),
            "B2 and B8 certain (Lab 1)": (dict(B2=1, B8=1), 1.0),
            "perfect QC (Lab 1)": (dict(B2=1, B8=0, B9=0, B10=0), 0.0),
            "agency operator (Lab 2)": (dict(B1=0.015, B2=0.006, B4=0.5), 0.00304),
            "agency after burn (Lab 2)": (dict(B1=0.015, B2=0.006, B4=0.8), 0.00326),
            "tablet guidance (Lab 2)": (dict(B1=0.003, B2=0.001, B4=0.1), 0.00154),
            "audit findings (Lab 3)": (dict(B6=0.025, B8=0.1), 0.00496),
            "audit, fix sampling (Lab 3)": (dict(B6=0.025, B8=0.05), 0.00298),
            "audit, fix handover (Lab 3)": (dict(B6=0.0125, B8=0.1), 0.00345),
            "B10 x10 (Lab 6)": (dict(B10=0.05), 0.00297),
        }
        for name, (changes, expected) in cases.items():
            with self.subTest(case=name):
                self.assertAlmostEqual(top(**changes), expected, places=5)

    def test_largest_cut_set(self):
        rows = vm.ranked_cut_sets(DEFAULT_FTA)
        cs, p = rows[0]
        self.assertEqual(cs, ["B6", "B8"])
        self.assertAlmostEqual(p / top(), 0.264, places=3)

    def test_importance_ranking(self):
        imp = vm.importance(DEFAULT_FTA)
        fv = [r["event"] for r in imp][:3]
        self.assertEqual(fv, ["B8", "B6", "B9"])
        birnbaum = {r["event"]: r["birnbaum"] for r in imp}
        self.assertAlmostEqual(birnbaum["B4"], 0.00072, places=5)   # large p, tiny effect

    def test_sensitivity_top_three(self):
        base, rows = vm.sensitivity(DEFAULT_FTA)
        self.assertAlmostEqual(base, top(), places=12)
        self.assertEqual([r[0] for r in rows[:3]], ["B8", "B6", "B9"])
        e, lo, hi = rows[0]
        self.assertAlmostEqual(lo, 0.00127, places=5)
        self.assertAlmostEqual(hi, 0.00315, places=5)


class FaultTreeIndependentChecks(unittest.TestCase):

    def test_gate_formulas_match_brute_force(self):
        scenarios = [DEFAULT_FTA,
                     {**DEFAULT_FTA, "B6": 0.025, "B8": 0.1},
                     {e: 0.3 for e in DEFAULT_FTA},
                     {e: 0.0 for e in DEFAULT_FTA}]
        for i, p in enumerate(scenarios):
            with self.subTest(scenario=i):
                self.assertAlmostEqual(vm.top_probability(p), brute_force_top(p), places=12)

    def test_cut_sets_are_minimal_and_complete(self):
        sets = [frozenset(cs) for cs, _ in vm.ranked_cut_sets(DEFAULT_FTA)]
        self.assertEqual(len(sets), len(set(sets)), "duplicate cut sets")
        for a in sets:
            for b in sets:
                if a != b:
                    self.assertFalse(a < b, f"{sorted(b)} is not minimal")
        # every cut set alone must cause the top event; removing any event must not
        for cs in sets:
            p = {e: (1.0 if e in cs else 0.0) for e in DEFAULT_FTA}
            self.assertEqual(vm.top_probability(p), 1.0)
            for e in cs:
                self.assertEqual(vm.top_probability({**p, e: 0.0}), 0.0)
        # 6 contamination paths (B1, B2, B3.B4, B5, B6, B7) x 3 QC failures (B8, B9, B10)
        self.assertEqual(len(sets), 18)

    def test_rare_event_approximation_is_close(self):
        approx = sum(p for _, p in vm.ranked_cut_sets(DEFAULT_FTA))
        self.assertLess(abs(approx - top()) / top(), 0.05)

    def test_monotonic(self):
        for e, p in DEFAULT_FTA.items():
            with self.subTest(event=e):
                self.assertGreaterEqual(top(**{e: min(1.0, p * 2)}), top())
                self.assertLessEqual(top(**{e: p / 2}), top())

    def test_report_runs(self):
        text = vm.fta_report(DEFAULT_FTA)
        self.assertIn("Top event probability", text)
        self.assertIn("B6 . B8", text)


# ---------------------------------------------------------------------------
# 2. Bayesian network
# ---------------------------------------------------------------------------

class BayesReferenceValues(unittest.TestCase):

    def test_default_marginals(self):
        post = bn()
        self.assertAlmostEqual(post["U"], 0.00202, places=5)
        self.assertAlmostEqual(post["SS"], 0.0092, places=6)
        self.assertAlmostEqual(post["C"], 0.02562, places=5)

    def test_wifi_outage(self):
        post = bn({"DI": True})
        self.assertAlmostEqual(post["U"], 0.00491, places=5)
        self.assertAlmostEqual(post["SS"], 0.032, places=6)
        self.assertAlmostEqual(post["B1"], 0.015, places=6)
        self.assertAlmostEqual(bn({"DI": False})["U"], 0.00186, places=5)

    def test_friday_handover(self):
        self.assertAlmostEqual(bn({"TP": True})["U"], 0.00437, places=5)
        self.assertAlmostEqual(bn({"TP": True, "DI": True})["U"], 0.01196, places=5)
        self.assertAlmostEqual(
            bn({"TP": True, "DI": True}, {"paper_fallback": True})["U"], 0.00544, places=5)

    def test_diagnosis(self):
        c = bn({"C": True})
        self.assertAlmostEqual(c["PF"], 0.1233, places=4)
        self.assertAlmostEqual(c["SS"], 0.3591, places=4)
        u = bn({"U": True})
        self.assertAlmostEqual(u["TP"], 0.4333, places=4)
        self.assertAlmostEqual(u["B8"], 0.6357, places=4)

    def test_option_comparison(self):
        rows = {label: u for label, u, _ in vm.compare_options({"DI": True})}
        self.assertAlmostEqual(rows["Baseline"], 0.00491, places=5)
        self.assertAlmostEqual(rows[vm.OPTIONS["second_probe"]], 0.00472, places=5)
        self.assertAlmostEqual(rows[vm.OPTIONS["paper_fallback"]], 0.00246, places=5)
        self.assertAlmostEqual(rows["Both measures"], 0.00226, places=5)
        self.assertAlmostEqual(rows[vm.OPTIONS["cyber_incident"]], 0.00744, places=5)

    def test_cyber_incident(self):
        self.assertAlmostEqual(bn(options={"cyber_incident": True})["U"], 0.00308, places=5)
        # QC always fails -> unsafe release equals contamination
        post = bn(params={**DEFAULT_BN, "B10": 1.0})
        self.assertAlmostEqual(post["U"], post["C"], places=12)

    def test_wifi_break_even(self):
        no_digital = {**DEFAULT_BN, "B1_ok": 0.008, "B1_down": 0.008, "B2_ok": 0.004,
                      "B2_down": 0.004, "SS_00": 0.008, "SS_01": 0.008,
                      "SS_10": 0.03, "SS_11": 0.03}
        target = bn(params=no_digital)["U"]
        self.assertAlmostEqual(target, 0.00259, places=5)
        self.assertLess(bn(params={**DEFAULT_BN, "P_DI_DOWN": 0.2})["U"], target)
        self.assertGreater(bn(params={**DEFAULT_BN, "P_DI_DOWN": 0.3})["U"], target)


class BayesIndependentChecks(unittest.TestCase):

    def test_reduces_to_fault_tree(self):
        """With the root causes switched off, the network must equal the fault tree."""
        p = DEFAULT_FTA
        flat = {**DEFAULT_BN, "P_TP": 0.0, "P_DI_DOWN": 0.0, "P_PF": p["B3"],
                "B1_ok": p["B1"], "B2_ok": p["B2"], "SS_00": p["B6"], "RB_0": p["B9"]}
        self.assertAlmostEqual(bn(params=flat)["U"], vm.top_probability(p), places=12)

    def test_probabilities_are_valid(self):
        for ev in ({}, {"DI": True}, {"C": True}, {"U": True}, {"TP": False, "QM": True}):
            with self.subTest(evidence=ev):
                for node, val in bn(ev).items():
                    self.assertGreaterEqual(val, 0.0)
                    self.assertLessEqual(val, 1.0)
                for node, val in ev.items():
                    self.assertAlmostEqual(bn(ev)[node], 1.0 if val else 0.0, places=12)

    def test_law_of_total_probability(self):
        p_tp = DEFAULT_BN["P_TP"]
        mix = p_tp * bn({"TP": True})["U"] + (1 - p_tp) * bn({"TP": False})["U"]
        self.assertAlmostEqual(mix, bn()["U"], places=12)

    def test_bayes_rule(self):
        # P(TP | U) = P(U | TP) P(TP) / P(U)
        lhs = bn({"U": True})["TP"]
        rhs = bn({"TP": True})["U"] * DEFAULT_BN["P_TP"] / bn()["U"]
        self.assertAlmostEqual(lhs, rhs, places=12)

    def test_intervention_differs_from_observation(self):
        # observing contamination raises time pressure; forcing it does not
        self.assertGreater(bn({"C": True})["TP"], DEFAULT_BN["P_TP"])
        self.assertAlmostEqual(bn(do={"C": True})["TP"], DEFAULT_BN["P_TP"], places=12)

    def test_cpt_keys_cover_all_parameters(self):
        keys = {k for table in vm.CPT_KEYS.values() for k in table.values()}
        self.assertEqual(keys, set(DEFAULT_BN))
        nodes = {n["name"]: n for n in vm.build_bn()}
        for node, table in vm.CPT_KEYS.items():
            with self.subTest(node=node):
                self.assertEqual(nodes[node]["type"], "cpt")
                for combo in table:
                    self.assertEqual(len(combo), len(nodes[node]["parents"]))
        for node in vm.DET_LOGIC:
            self.assertEqual(nodes[node]["type"], "det")

    def test_options_do_not_change_defaults(self):
        before = dict(DEFAULT_BN)
        vm.apply_options(DEFAULT_BN, {k: True for k in vm.OPTIONS})
        self.assertEqual(DEFAULT_BN, before)

    def test_impossible_evidence_raises(self):
        with self.assertRaises(ValueError):
            bn({"U": True, "C": False})


# ---------------------------------------------------------------------------
# 3. Validation and sample data
# ---------------------------------------------------------------------------

class ValidationAndData(unittest.TestCase):

    def test_wilson_interval(self):
        lo, hi = vm.wilson_interval(0, 200)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.0188, places=4)
        lo, hi = vm.wilson_interval(79, 200)
        self.assertAlmostEqual(lo, 0.330, places=3)
        self.assertAlmostEqual(hi, 0.464, places=3)
        self.assertEqual(vm.wilson_interval(0, 0), (0.0, 1.0))

    def test_planted_finding(self):
        records = vm.load_records(SAMPLE_CSV)
        self.assertEqual(len(records), 200)
        rows = {r[0]: r for r in vm.validate(records)}
        self.assertEqual(rows["shift_handover_pressure"][2], 79)
        self.assertEqual(rows["shift_handover_pressure"][8], "CHECK MODEL")
        others = [r[8] for col, r in rows.items() if col != "shift_handover_pressure"]
        self.assertTrue(all(v == "consistent" for v in others))

    def test_calibration_fixes_validation(self):
        records = vm.load_records(SAMPLE_CSV)
        rows = vm.validate(records, {**DEFAULT_BN, "P_TP": 0.395})
        self.assertTrue(all(r[8] == "consistent" for r in rows))
        self.assertAlmostEqual(bn(params={**DEFAULT_BN, "P_TP": 0.395})["U"], 0.00259, places=5)

    def test_final_assignment_model(self):
        flawed = {**DEFAULT_BN, "B8": 0.95, "SS_11": 0.008, "RB_1": 0.006}
        self.assertAlmostEqual(bn(params=flawed)["U"], 0.0237, places=4)
        failing = {r[0] for r in vm.validate(vm.load_records(SAMPLE_CSV), flawed)
                   if r[8] != "consistent"}
        self.assertEqual(failing, {"shift_handover_pressure", "released_before_result",
                                   "unsafe_release"})

    def test_sample_file_is_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = generate_data.write_csv(os.path.join(tmp, "x.csv"))
            with open(path, newline="", encoding="utf-8") as f:
                fresh = list(csv.DictReader(f))
        self.assertEqual(fresh, vm.load_records(SAMPLE_CSV))

    def test_generated_records_are_consistent(self):
        for row in generate_data.sample_batches(500, seed=7):
            if row["unsafe_release"]:
                self.assertEqual(row["contaminated"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
