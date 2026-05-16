from __future__ import annotations

import argparse
from pathlib import Path

from .analysis import StoryChecker
from .dsl import parse_rules
from .metrics import evaluate_against_ground_truth, load_ground_truth, metrics_summary, write_metrics
from .models import StoryGraph
from .reporting import write_json_report, write_markdown_report, write_trace_files, write_triage_csv
from .schema import load_raw_story_graph, validate_story_graph
from .smv import run_nusmv, write_smv


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line surface used by docs, tests, and CI scripts."""

    parser = argparse.ArgumentParser(description="Check a resource-annotated story graph for continuity defects.")
    parser.add_argument("story_graph", help="Path to story_graph.json")
    parser.add_argument("rules", help="Path to rules.dsl")
    parser.add_argument("--mode", choices=["sr", "aq", "ra", "sc", "all"], default="sc", help="Analysis mode")
    parser.add_argument("--theta", type=int, default=5, help="Soft-lock transition threshold")
    parser.add_argument("--out", default="story_report.json", help="JSON report output path")
    parser.add_argument("--markdown", default=None, help="Optional Markdown report output path")
    parser.add_argument("--trace-dir", default=None, help="Optional directory for per-violation Unity replay traces")
    parser.add_argument("--emit-smv", default=None, help="Optional NuSMV model output path")
    parser.add_argument("--nusmv", default=None, help="Optional NuSMV executable path to run against --emit-smv")
    parser.add_argument("--nusmv-out", default=None, help="Optional path for NuSMV stdout/stderr")
    parser.add_argument("--ground-truth", default=None, help="Optional ground_truth.json path for detection metrics")
    parser.add_argument("--metrics-out", default=None, help="Optional metrics JSON output path")
    parser.add_argument("--schema-report", default=None, help="Optional schema validation JSON output path")
    parser.add_argument("--triage-csv", default=None, help="Optional CSV export for QA triage")
    parser.add_argument("--primary-only", action="store_true", help="Only write root-cause primary violations to Markdown, trace files, and triage CSV")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    raw_graph = load_raw_story_graph(args.story_graph)
    rules_text = Path(args.rules).read_text(encoding="utf-8")
    rules = parse_rules(rules_text)

    # Validate the exported contract before constructing typed models. This
    # keeps schema errors reportable as JSON instead of failing deep in analysis.
    schema_validation = validate_story_graph(raw_graph, rules)
    if args.schema_report:
        write_json_report(schema_validation, args.schema_report)
    if not schema_validation["valid"]:
        print(f"Schema validation failed with {schema_validation['errors']} errors.")
        return 2
    graph = StoryGraph.from_dict(raw_graph)
    if args.mode == "all":
        report = StoryChecker.run_all(graph, rules, theta=args.theta)
    else:
        report = StoryChecker(graph, rules, theta=args.theta, mode=args.mode).run()
    report["schema_validation"] = schema_validation

    # JSON is always the source-of-truth report. Markdown, traces, and CSV are
    # review conveniences and can be limited to root-cause primaries.
    write_json_report(report, args.out)
    if args.markdown:
        write_markdown_report(report, args.markdown, primary_only=args.primary_only)
    if args.trace_dir:
        write_trace_files(report, args.trace_dir, primary_only=args.primary_only)
    if args.triage_csv:
        write_triage_csv(report, args.triage_csv, primary_only=args.primary_only)
    if args.emit_smv:
        # NuSMV execution is optional so the checker remains usable in pure
        # Python environments.
        write_smv(graph, rules, args.emit_smv)
        if args.nusmv:
            nusmv_out = args.nusmv_out or str(Path(args.emit_smv).with_suffix(".nusmv.txt"))
            completed = run_nusmv(args.nusmv, args.emit_smv, nusmv_out)
            print(f"NuSMV exited with code {completed.returncode}; output written to {nusmv_out}.")
    if args.ground_truth:
        # Metrics are demo-facing: they show how each mode covers the seeded
        # defects without making them part of the checker core.
        metrics = evaluate_against_ground_truth(report, load_ground_truth(args.ground_truth))
        metrics_out = args.metrics_out or str(Path(args.out).with_name(Path(args.out).stem + "_metrics.json"))
        write_metrics(metrics, metrics_out)
        print(f"Metrics written to {metrics_out}: {metrics_summary(metrics)}.")
    mode_label = report["analysis"]["mode"]
    if "runs" in report:
        config_count = report["runs"]["SC"]["analysis"]["reachable_abstract_configurations"]
        violation_count = len(report["runs"]["SC"]["violations"])
        print(
            f"{mode_label} checked SR/AQ/RA/SC; SC visited {config_count} configurations and "
            f"wrote {violation_count} SC violations to {args.out}."
        )
    else:
        config_count = report["analysis"]["reachable_abstract_configurations"]
        violation_count = len(report["violations"])
        print(
            f"{mode_label} checked {config_count} configurations; "
            f"{violation_count} violations written to {args.out}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
