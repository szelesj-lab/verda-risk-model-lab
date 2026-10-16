"""
Tests for model files and the generic engine.

Developer: József Szeles, Department of System Engineering, University of Pannonia

Run from the project folder:

    python -m unittest discover -s tests
"""

import copy
import itertools
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import verda_model as vm          # noqa: E402
import generate_data              # noqa: E402

MODELS = os.path.join(ROOT, "models")
VERDA = os.path.join(MODELS, "verda.json")
PUMP = os.path.join(MODELS, "pump_station.json")
CONSULTANT = os.path.join(MODELS, "verda_consultant.json")


def read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def brute_force_top(p):
    """Exact top-event probability over all 2^n event states (any gate type)."""
    events = list(p)

    def val(n, s):
        if n not in vm.GATES:
            return s[n]
        kind, children, _ = vm.GATES[n]
        v = [val(c, s) for c in children]
        if kind == "AND":
            return all(v)
        if kind == "OR":
            return any(v)
        return sum(v) >= vm.GATE_K[n]

    total = 0.0
    for bits in itertools.product((False, True), repeat=len(events)):
        s = dict(zip(events, bits))
        w = 1.0
        for e in events:
            w *= p[e] if s[e] else 1 - p[e]
        if val(vm.TOP, s):
            total += w
    return total


class ModelFileTest(unittest.TestCase):
    def tearDown(self):
        vm.load_model()                       # leave the VERDA model active

    def test_bundled_models_are_valid(self):
        for name in os.listdir(MODELS):
            if name.endswith(".json"):
                with self.subTest(model=name):
                    self.assertEqual(vm.check_model(read(os.path.join(MODELS, name))), [])

    def test_default_model_is_verda(self):
        self.assertEqual(os.path.abspath(vm.DEFAULT_MODEL_PATH), os.path.abspath(VERDA))
        self.assertEqual(vm.TOP, "TOP")
        self.assertEqual(vm.QUERY, "U")

    def test_save_and_reload_gives_same_numbers(self):
        before = (vm.top_probability(vm.default_fta_probabilities()),
                  vm.bn_query(vm.build_bn(), {"DI": True, "TP": True}))
        with tempfile.TemporaryDirectory() as tmp:
            path = vm.save_model(os.path.join(tmp, "copy.json"))
            self.assertEqual(read(path), read(VERDA))
            vm.load_model(path)
        after = (vm.top_probability(vm.default_fta_probabilities()),
                 vm.bn_query(vm.build_bn(), {"DI": True, "TP": True}))
        self.assertEqual(before, after)

    def test_save_with_edited_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = vm.save_model(os.path.join(tmp, "audit.json"), fta_p={"B6": 0.025, "B8": 0.1},
                                 bn_params={**vm.DEFAULT_BN_PARAMS, "SS_11": 0.2})
            vm.load_model(path)
        self.assertAlmostEqual(vm.top_probability(vm.default_fta_probabilities()), 0.00496, places=5)
        self.assertEqual(vm.DEFAULT_BN_PARAMS["SS_11"], 0.2)

    def test_consultant_model(self):
        vm.load_model(CONSULTANT)
        self.assertAlmostEqual(vm.bn_query(vm.build_bn())["U"], 0.0237, places=4)

    def test_switching_models_does_not_mix_caches(self):
        u = vm.bn_query(vm.build_bn())["U"]
        vm.load_model(CONSULTANT)
        self.assertNotAlmostEqual(vm.bn_query(vm.build_bn())["U"], u, places=4)
        vm.load_model(VERDA)
        self.assertEqual(vm.bn_query(vm.build_bn())["U"], u)


class GenericEngineTest(unittest.TestCase):
    def setUp(self):
        vm.load_model(PUMP)

    def tearDown(self):
        vm.load_model()

    def test_repeated_event_is_exact(self):
        p = vm.default_fta_probabilities()
        self.assertEqual(vm.repeated_events(), ["OP"])
        self.assertAlmostEqual(vm.top_probability(p), brute_force_top(p), places=14)

    def test_random_values_match_brute_force(self):
        import random
        rng = random.Random(3)
        for _ in range(20):
            p = {e: rng.random() for e in vm.BASIC_EVENTS}
            self.assertAlmostEqual(vm.top_probability(p), brute_force_top(p), places=12)

    def test_vote_gate(self):
        g = vm.gate_probabilities(vm.default_fta_probabilities())
        q = 0.02
        self.assertAlmostEqual(g["PUMPS"], 3 * q * q * (1 - q) + q ** 3, places=15)
        cuts = {frozenset(cs) for cs in vm.minimal_cut_sets("PUMPS")}
        self.assertEqual(cuts, {frozenset(("PA", "PB")), frozenset(("PA", "PC")), frozenset(("PB", "PC"))})

    def test_cut_sets_respect_repeated_event(self):
        sets = {frozenset(cs) for cs, _ in vm.ranked_cut_sets(vm.default_fta_probabilities())}
        self.assertIn(frozenset(("GRID", "OP")), sets)
        self.assertIn(frozenset(("CTRL", "OP")), sets)
        self.assertEqual(len(sets), 6)

    def test_network_reduces_to_fault_tree_without_heatwave(self):
        params = {**vm.DEFAULT_BN_PARAMS, "HEAT": 0.0}
        p = vm.default_fta_probabilities()
        self.assertAlmostEqual(vm.bn_query(vm.build_bn(params))["OUT"], vm.top_probability(p), places=14)

    def test_vote_logic_node(self):
        post = vm.bn_query(vm.build_bn(), {"PA": True, "PB": True})
        self.assertEqual(post["PUMPS"], 1.0)
        post = vm.bn_query(vm.build_bn(), {"PA": True, "PB": False, "PC": False})
        self.assertEqual(post["PUMPS"], 0.0)

    def test_automatic_parameter_names(self):
        self.assertEqual(vm.CPT_KEYS["PA"], {(False,): "PA_0", (True,): "PA_1"})
        self.assertEqual(vm.CPT_KEYS["HEAT"], {(): "HEAT"})

    def test_options(self):
        labels = [label for label, _ in vm.option_variants()]
        self.assertEqual(labels, ["Baseline", "Preventive pump maintenance", "Automatic generator start",
                                  "Both measures", "Hot summer (heatwave half the days)"])
        p = vm.apply_options(vm.DEFAULT_BN_PARAMS, {"auto_start": True, "hot_summer": True})
        self.assertAlmostEqual(p["OP"], 0.03)
        self.assertEqual(p["HEAT"], 0.5)
        rows = vm.compare_options()
        self.assertLess(rows[3][1], rows[0][1])
        self.assertGreater(rows[4][1], rows[0][1])

    def test_sample_data_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            records = vm.load_records(generate_data.write_csv(os.path.join(tmp, "x.csv")))
        self.assertEqual(len(records), 365)
        verdict = {r[0]: r[8] for r in vm.validate(records)}
        self.assertEqual(verdict["alarm_missed"], "CHECK MODEL")
        self.assertEqual(verdict["heatwave"], "consistent")


class CheckerTest(unittest.TestCase):
    def setUp(self):
        self.good = read(PUMP)

    def problems(self, change):
        data = copy.deepcopy(self.good)
        change(data)
        return " | ".join(vm.check_model(data))

    def test_unknown_input(self):
        def f(d):
            d["fault_tree"]["gates"][0]["inputs"].append("XX")
        self.assertIn("input XX is not defined", self.problems(f))

    def test_probability_out_of_range(self):
        def f(d):
            d["fault_tree"]["events"][0]["p"] = 1.5
        self.assertIn("between 0 and 1", self.problems(f))

    def test_missing_cpt_row(self):
        def f(d):
            d["bayesian_network"]["nodes"][1]["cpt"].pop()
        self.assertIn("needs 2 rows", self.problems(f))

    def test_cycle(self):
        def f(d):
            d["bayesian_network"]["nodes"][0]["parents"] = ["OUT"]
            d["bayesian_network"]["nodes"][0]["cpt"] = [{"when": {"OUT": False}, "p": 0.1},
                                                         {"when": {"OUT": True}, "p": 0.1}]
        self.assertIn("Cycle", self.problems(f))

    def test_disconnected_event(self):
        def f(d):
            d["fault_tree"]["events"].append({"id": "LOST", "p": 0.1})
        self.assertIn("LOST is not connected", self.problems(f))

    def test_bad_vote(self):
        def f(d):
            d["fault_tree"]["gates"][1]["k"] = 4
        self.assertIn("VOTE needs k", self.problems(f))

    def test_option_with_unknown_parameter(self):
        def f(d):
            d["bayesian_network"]["options"][0]["changes"][0]["param"] = "NOPE"
        self.assertIn("NOPE does not exist", self.problems(f))

    def test_invalid_file_raises_and_keeps_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "broken.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"format": "verda-risk-model", ')
            with self.assertRaises(vm.ModelError):
                vm.load_model(path)
        self.assertEqual(vm.QUERY, "U")


if __name__ == "__main__":
    unittest.main()
