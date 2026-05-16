import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# The prototype is intentionally not packaged; tests import it from the local
# checker directory so they work in a fresh clone or zip.
sys.path.insert(0, str(ROOT / "checker"))

from story_checker import StoryChecker, StoryGraph, parse_rules
from story_checker.metrics import evaluate_against_ground_truth, load_ground_truth
from story_checker.schema import load_raw_story_graph, validate_story_graph
from story_checker.smv import build_smv


class DemoCheckerTests(unittest.TestCase):
    """End-to-end coverage for the seeded Unity chapter and export pipeline."""

    def test_demo_chapter_reports_core_defect_classes(self) -> None:
        graph = StoryGraph.load(ROOT / "examples" / "unity_chapter" / "story_graph.json")
        rules = parse_rules((ROOT / "examples" / "unity_chapter" / "rules.dsl").read_text(encoding="utf-8"))
        report = StoryChecker(graph, rules, theta=5).run()
        classes = {violation["class"] for violation in report["violations"]}
        self.assertIn("hard_lock", classes)
        self.assertIn("soft_lock", classes)
        self.assertIn("disposable_critical_resource", classes)
        self.assertIn("shortcut", classes)
        self.assertIn("dsl_invariant", classes)
        self.assertIn("recommended_asset_missing", classes)
        self.assertIn("root_causes", report)
        self.assertTrue(all("root_cause_key" in violation for violation in report["violations"]))
        self.assertTrue(all("parameters" in action for violation in report["violations"] for action in violation["trace"]["actions"]))

    def test_report_is_json_serializable(self) -> None:
        graph = StoryGraph.load(ROOT / "examples" / "unity_chapter" / "story_graph.json")
        rules = parse_rules((ROOT / "examples" / "unity_chapter" / "rules.dsl").read_text(encoding="utf-8"))
        report = StoryChecker(graph, rules, theta=5).run()
        json.dumps(report)

    def test_all_modes_and_metrics_cover_demo_ground_truth(self) -> None:
        graph = StoryGraph.load(ROOT / "examples" / "unity_chapter" / "story_graph.json")
        rules = parse_rules((ROOT / "examples" / "unity_chapter" / "rules.dsl").read_text(encoding="utf-8"))
        report = StoryChecker.run_all(graph, rules, theta=5)
        self.assertEqual({"SR", "AQ", "RA", "SC"}, set(report["runs"]))
        metrics = evaluate_against_ground_truth(
            report,
            load_ground_truth(ROOT / "examples" / "unity_chapter" / "ground_truth.json"),
        )
        self.assertEqual(6, metrics["runs"]["SC"]["detected_total"])
        self.assertEqual([], metrics["runs"]["SC"]["unmatched_ground_truth"])

    def test_smv_export_contains_core_ctl_properties(self) -> None:
        graph = StoryGraph.load(ROOT / "examples" / "unity_chapter" / "story_graph.json")
        rules = parse_rules((ROOT / "examples" / "unity_chapter" / "rules.dsl").read_text(encoding="utf-8"))
        checker = StoryChecker(graph, rules, theta=5)
        smv = build_smv(graph, rules, sorted(checker.relevant_assets))
        self.assertIn("MODULE main", smv)
        self.assertIn("TRANS", smv)
        self.assertIn("CTLSPEC AG((state = M7_Boss) -> has_SniperRifle);", smv)
        self.assertIn("CTLSPEC AG((state = M8_Ending) -> (has_WantedLevelBelow4 | !has_WantedLevelGE4));", smv)

    def test_schema_validation_accepts_demo_contract(self) -> None:
        raw = load_raw_story_graph(ROOT / "examples" / "unity_chapter" / "story_graph.json")
        rules = parse_rules((ROOT / "examples" / "unity_chapter" / "rules.dsl").read_text(encoding="utf-8"))
        validation = validate_story_graph(raw, rules)
        self.assertTrue(validation["valid"])
        self.assertEqual(0, validation["errors"])


if __name__ == "__main__":
    unittest.main()
