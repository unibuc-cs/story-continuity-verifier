from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Mapping


def load_ground_truth(path: str | Path) -> dict:
    """Load the seeded defect list used by demo metrics."""

    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if "defects" not in data:
        raise ValueError("ground truth file must contain a 'defects' array")
    return data


def evaluate_against_ground_truth(report: Mapping, ground_truth: Mapping) -> dict:
    """Evaluate one report or all mode reports against the same ground truth."""

    if "runs" in report:
        return {
            "graph": report["graph"]["name"],
            "runs": {
                mode: evaluate_single_report(run_report, ground_truth)
                for mode, run_report in report["runs"].items()
            },
        }
    return evaluate_single_report(report, ground_truth)


def evaluate_single_report(report: Mapping, ground_truth: Mapping) -> dict:
    """Compute detection, duplicate, advisory, and false-positive counts."""

    defects = ground_truth.get("defects", [])
    violations = report.get("violations", [])
    matched_gt: dict[str, str] = {}
    matched_violations: set[str] = set()
    duplicate_count = 0
    false_positives = 0
    advisories = 0

    for violation in violations:
        match = first_matching_defect(violation, defects)
        if match is None:
            # Recommended-asset messages are intentional advisories; counting
            # them as false positives would penalize review hints.
            if violation.get("metadata", {}).get("advisory") or violation.get("severity") == "info":
                advisories += 1
                continue
            false_positives += 1
            continue
        matched_violations.add(violation["id"])
        gt_id = match["id"]
        if gt_id in matched_gt:
            duplicate_count += 1
        else:
            matched_gt[gt_id] = violation["id"]

    gt_by_class = Counter(defect["class"] for defect in defects)
    detected_by_class = Counter(
        defect["class"]
        for defect in defects
        if defect["id"] in matched_gt
    )
    detection_by_class = {}
    for defect_class in sorted(gt_by_class):
        total = gt_by_class[defect_class]
        detected = detected_by_class[defect_class]
        detection_by_class[defect_class] = {
            "detected": detected,
            "total": total,
            "rate": detected / total if total else 0.0,
        }

    violation_classes = Counter(violation["class"] for violation in violations)
    return {
        "mode": report["analysis"]["mode"],
        "ground_truth_total": len(defects),
        "detected_total": len(matched_gt),
        "detection_rate": len(matched_gt) / len(defects) if defects else 0.0,
        "false_positives": false_positives,
        "duplicates": duplicate_count,
        "root_cause_duplicates": sum(1 for violation in violations if violation.get("duplicate_of")),
        "advisories": advisories,
        "root_cause_count": len(report.get("root_causes", [])),
        "violation_count": len(violations),
        "detection_by_class": detection_by_class,
        "violations_by_class": dict(sorted(violation_classes.items())),
        "matched_ground_truth": dict(sorted(matched_gt.items())),
        "unmatched_ground_truth": [
            defect["id"]
            for defect in defects
            if defect["id"] not in matched_gt
        ],
        "matched_violations": sorted(matched_violations),
    }


def first_matching_defect(violation: Mapping, defects: list[Mapping]) -> Mapping | None:
    """Return the first ground-truth defect accepted by this violation."""

    for defect in defects:
        if violation_matches_defect(violation, defect):
            return defect
    return None


def violation_matches_defect(violation: Mapping, defect: Mapping) -> bool:
    """Match by accepted class, state, rule, and required missing assets."""

    accepted_classes = set(defect.get("accepted_classes", [defect["class"]]))
    if violation["class"] not in accepted_classes:
        return False
    states = set(defect.get("states", []))
    if "state" in defect:
        states.add(defect["state"])
    if states and violation.get("state") not in states:
        return False
    if defect.get("rule") and violation.get("rule") != defect["rule"]:
        return False
    required_missing = set(defect.get("missing_assets", []))
    if required_missing and not required_missing.issubset(set(violation.get("missing_assets", []))):
        return False
    return True


def write_metrics(metrics: Mapping, path: str | Path) -> None:
    """Write metrics JSON beside the checker report."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)
        handle.write("\n")


def metrics_summary(metrics: Mapping) -> str:
    """Produce the concise CLI status line."""

    if "runs" in metrics:
        parts = []
        for mode, run in metrics["runs"].items():
            parts.append(
                f"{mode}: {run['detected_total']}/{run['ground_truth_total']} detected, "
                f"{run['false_positives']} FP, {run['duplicates']} GT duplicates, "
                f"{run['root_cause_duplicates']} root duplicates, {run['advisories']} advisories"
            )
        return "; ".join(parts)
    return (
        f"{metrics['mode']}: {metrics['detected_total']}/{metrics['ground_truth_total']} detected, "
        f"{metrics['false_positives']} FP, {metrics['duplicates']} GT duplicates, "
        f"{metrics['root_cause_duplicates']} root duplicates, {metrics['advisories']} advisories"
    )
