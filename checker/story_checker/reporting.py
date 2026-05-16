from __future__ import annotations

import json
import csv
from pathlib import Path
from typing import Mapping


def write_json_report(report: Mapping, path: str | Path) -> None:
    """Write the full machine-readable checker output."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=False)
        handle.write("\n")


def write_markdown_report(report: Mapping, path: str | Path, primary_only: bool = False) -> None:
    """Write a human review report for either one mode or an ALL-mode run."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if "runs" in report:
        write_aggregate_markdown_report(report, target, primary_only=primary_only)
        return
    graph = report["graph"]
    analysis = report["analysis"]
    violations = filtered_violations(report["violations"], primary_only)
    lines = [
        f"# Story Continuity Report: {graph['name']}",
        "",
        "## Summary",
        "",
        f"- States: {graph['states']}",
        f"- Assets: {graph['assets']}",
        f"- Quests: {graph['quests']}",
        f"- Transitions: {graph['transitions']}",
        f"- Reachable abstract configurations: {analysis['reachable_abstract_configurations']}",
        f"- Violations: {len(violations)}",
        f"- Root causes: {len(report.get('root_causes', []))}",
        "",
    ]
    append_schema_validation(lines, report.get("schema_validation"))
    append_root_causes(lines, report.get("root_causes", []))
    lines.extend(["## Violations", ""])
    if not violations:
        lines.append("No violations detected.")
    for violation in violations:
        lines.extend(
            [
                f"### {violation['id']} {violation['class']}",
                "",
                f"- Severity: {violation['severity']}",
                f"- State: {violation['state']}",
                f"- Rule: {violation['rule'] or 'pattern'}",
                f"- Root cause: {violation.get('root_cause_key', 'n/a')}",
                f"- Duplicate of: {violation.get('duplicate_of') or 'none'}",
                f"- Message: {violation['message']}",
                f"- Missing assets: {', '.join(violation['missing_assets']) if violation['missing_assets'] else 'none'}",
                f"- Trace length: {len(violation['trace']['actions'])}",
                "",
            ]
        )
        if violation["trace"]["actions"]:
            lines.append("| Step | Transition | From | To |")
            lines.append("| ---: | --- | --- | --- |")
            for action in violation["trace"]["actions"]:
                lines.append(
                    f"| {action['index']} | `{action['transition_id']}` | `{action['from']}` | `{action['to']}` |"
                )
            lines.append("")
        if violation["repair_suggestions"]:
            lines.append("Repair suggestions:")
            for suggestion in violation["repair_suggestions"]:
                quests = ", ".join(suggestion["support_quests"]) or "none"
                lines.append(f"- `{suggestion['asset']}` via {quests}: {suggestion['suggestion']}")
            lines.append("")
    with target.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(lines).rstrip() + "\n")


def write_trace_files(report: Mapping, directory: str | Path, primary_only: bool = False) -> None:
    """Write one Unity replay trace per selected SC violation."""

    if "runs" in report:
        report = report["runs"]["SC"]
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    # Remove stale traces so switching --primary-only cannot leave old reports
    # that look current to a reviewer.
    for stale in target.glob("V*_trace.json"):
        stale.unlink()
    for violation in filtered_violations(report["violations"], primary_only):
        trace = dict(violation["trace"])
        trace["violation_id"] = violation["id"]
        trace["violation_class"] = violation["class"]
        with (target / f"{violation['id']}_trace.json").open("w", encoding="utf-8") as handle:
            json.dump(trace, handle, indent=2)
            handle.write("\n")


def write_triage_csv(report: Mapping, path: str | Path, primary_only: bool = False) -> None:
    """Write a compact spreadsheet-friendly defect list."""

    if "runs" in report:
        report = report["runs"]["SC"]
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "class",
                "severity",
                "rule",
                "state",
                "missing_assets",
                "root_cause_key",
                "duplicate_of",
                "trace_length",
                "message",
            ],
        )
        writer.writeheader()
        for violation in filtered_violations(report["violations"], primary_only):
            writer.writerow(
                {
                    "id": violation["id"],
                    "class": violation["class"],
                    "severity": violation["severity"],
                    "rule": violation.get("rule") or "",
                    "state": violation["state"],
                    "missing_assets": ",".join(violation.get("missing_assets", [])),
                    "root_cause_key": violation.get("root_cause_key", ""),
                    "duplicate_of": violation.get("duplicate_of") or "",
                    "trace_length": len(violation["trace"]["actions"]),
                    "message": violation["message"],
                }
            )


def write_aggregate_markdown_report(report: Mapping, target: Path, primary_only: bool = False) -> None:
    """Write the Markdown form for --mode all."""

    graph = report["graph"]
    lines = [
        f"# Story Continuity Report: {graph['name']}",
        "",
        "## Mode Summary",
        "",
        "| Mode | Configurations | Transitions | Violations | Root Causes | Description |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for mode, run in report["runs"].items():
        analysis = run["analysis"]
        lines.append(
            f"| {mode} | {analysis['reachable_abstract_configurations']} | "
            f"{analysis['induced_abstract_transitions']} | {len(run['violations'])} | "
            f"{len(run.get('root_causes', []))} | "
            f"{analysis['description']} |"
        )
    lines.append("")
    append_schema_validation(lines, report.get("schema_validation"))
    append_root_causes(lines, sc_report_root_causes(report))
    title = "## SC Primary Violations" if primary_only else "## SC Violations"
    lines.extend([title, ""])
    sc_report = report["runs"]["SC"]
    violations = filtered_violations(sc_report["violations"], primary_only)
    if not violations:
        lines.append("No SC violations detected.")
    for violation in violations:
        lines.extend(
            [
                f"### {violation['id']} {violation['class']}",
                "",
                f"- Severity: {violation['severity']}",
                f"- State: {violation['state']}",
                f"- Rule: {violation['rule'] or 'pattern'}",
                f"- Root cause: {violation.get('root_cause_key', 'n/a')}",
                f"- Duplicate of: {violation.get('duplicate_of') or 'none'}",
                f"- Message: {violation['message']}",
                f"- Missing assets: {', '.join(violation['missing_assets']) if violation['missing_assets'] else 'none'}",
                f"- Trace length: {len(violation['trace']['actions'])}",
                "",
            ]
        )
    with target.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(lines).rstrip() + "\n")


def append_schema_validation(lines: list[str], validation: Mapping | None) -> None:
    """Append schema diagnostics if the CLI added them to the report."""

    if not validation:
        return
    lines.extend(
        [
            "## Schema Validation",
            "",
            f"- Valid: {validation['valid']}",
            f"- Errors: {validation['errors']}",
            f"- Warnings: {validation['warnings']}",
            "",
        ]
    )
    if validation.get("issues"):
        lines.append("| Severity | Code | Path | Message |")
        lines.append("| --- | --- | --- | --- |")
        for issue in validation["issues"]:
            lines.append(f"| {issue['severity']} | `{issue['code']}` | `{issue['path']}` | {issue['message']} |")
        lines.append("")


def append_root_causes(lines: list[str], root_causes: list[Mapping]) -> None:
    """Append the deduplicated root-cause table."""

    lines.extend(["## Root Causes", ""])
    if not root_causes:
        lines.append("No root causes reported.")
        lines.append("")
        return
    lines.append("| Primary | Class | State | Missing | Duplicates |")
    lines.append("| --- | --- | --- | --- | ---: |")
    for root in root_causes:
        missing = ", ".join(root.get("missing_assets", [])) or "none"
        lines.append(
            f"| {root['primary_id']} | `{root['class']}` | `{root['state']}` | "
            f"{missing} | {root['duplicate_count']} |"
        )
    lines.append("")


def sc_report_root_causes(report: Mapping) -> list[Mapping]:
    """Return SC root causes from an aggregate report."""

    return report.get("runs", {}).get("SC", {}).get("root_causes", [])


def filtered_violations(violations: list[Mapping], primary_only: bool) -> list[Mapping]:
    """Apply the reviewer-facing primary-only filter."""

    if not primary_only:
        return list(violations)
    return [violation for violation in violations if not violation.get("duplicate_of")]
