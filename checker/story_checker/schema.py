from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .dsl import parse_call, referenced_assets


KNOWN_ASSET_CATEGORIES = {"flag", "unique", "critical", "replenishable", "transformable"}
KNOWN_QUEST_ROLES = {"main", "side"}
KNOWN_TRIGGERS = {"EnterMission", "EnterHub", "CompleteMission", "ReachState", "AtState", "ReachTaggedState", "EnterKind"}
KNOWN_REQUIREMENTS = {
    "HasAsset",
    "HasFlag",
    "NotHasAsset",
    "NotHasFlag",
    "MissingAsset",
    "AtState",
    "NextStateIs",
    "WantedLevelBelow",
    "AlwaysTrue",
    "True",
    "AlwaysFalse",
    "False",
}
KNOWN_EFFECTS = {"AddAsset", "AddFlag", "RemoveAsset", "RemoveFlag", "NoOp", "None"}


def load_raw_story_graph(path: str | Path) -> Mapping[str, Any]:
    """Load JSON without converting it, so validation can report raw paths."""

    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_story_graph(raw: Mapping[str, Any], rules: Sequence = ()) -> dict:
    """Validate the exported story graph and DSL references."""

    issues: list[dict] = []

    states = raw.get("states", [])
    assets = raw.get("assets", [])
    quests = raw.get("quests", [])
    mandatory_states = raw.get("mandatory_story_states", [])
    transitions = raw.get("transitions", [])

    require_array(raw, "states", issues)
    require_array(raw, "assets", issues)
    require_array(raw, "quests", issues)
    require_array(raw, "mandatory_story_states", issues)
    require_array(raw, "transitions", issues)

    # Collect IDs before cross-reference checks so every later diagnostic can be
    # expressed as a JSON path plus an unknown or duplicated identifier.
    state_ids = collect_ids(states, "states", issues)
    asset_ids = collect_ids(assets, "assets", issues)
    quest_ids = collect_ids(quests, "quests", issues)
    transition_ids = collect_ids(transitions, "transitions", issues)

    initial_state = raw.get("initial_state")
    if not initial_state:
        add_issue(issues, "error", "missing_initial_state", "$.initial_state", "initial_state is required.")
    elif initial_state not in state_ids:
        add_issue(issues, "error", "unknown_initial_state", "$.initial_state", f"Unknown initial state '{initial_state}'.")

    for state in raw.get("completion_states", []):
        if state not in state_ids:
            add_issue(issues, "error", "unknown_completion_state", "$.completion_states", f"Unknown completion state '{state}'.")

    for asset in raw.get("initial_assets", []):
        if asset not in asset_ids:
            add_issue(issues, "error", "unknown_initial_asset", "$.initial_assets", f"Unknown initial asset '{asset}'.")

    for index, state in enumerate(states):
        if state.get("kind", "state") == "":
            add_issue(issues, "warning", "empty_state_kind", f"$.states[{index}].kind", "State kind is empty.")

    for index, asset in enumerate(assets):
        category = str(asset.get("category", "flag")).lower()
        if category not in KNOWN_ASSET_CATEGORIES:
            add_issue(issues, "warning", "unknown_asset_category", f"$.assets[{index}].category", f"Unknown asset category '{category}'.")
        for quest_id in asset.get("support_quests", []):
            if quest_id not in quest_ids:
                add_issue(issues, "warning", "unknown_support_quest", f"$.assets[{index}].support_quests", f"Unknown support quest '{quest_id}'.")

    for index, quest in enumerate(quests):
        role = quest.get("role", "side")
        if role not in KNOWN_QUEST_ROLES:
            add_issue(issues, "warning", "unknown_quest_role", f"$.quests[{index}].role", f"Unknown quest role '{role}'.")
        for asset_id in quest.get("rewards", []):
            if asset_id not in asset_ids:
                add_issue(issues, "error", "unknown_quest_reward", f"$.quests[{index}].rewards", f"Quest reward references unknown asset '{asset_id}'.")
        validate_expressions(quest.get("pre", []), asset_ids, state_ids, issues, f"$.quests[{index}].pre", KNOWN_REQUIREMENTS)

    for index, mandatory in enumerate(mandatory_states):
        state = mandatory.get("state")
        if state not in state_ids:
            add_issue(issues, "error", "unknown_mandatory_state", f"$.mandatory_story_states[{index}].state", f"Unknown mandatory state '{state}'.")
        for field in ("required", "recommended"):
            for asset_id in mandatory.get(field, []):
                if asset_id not in asset_ids:
                    add_issue(issues, "error", "unknown_mandatory_asset", f"$.mandatory_story_states[{index}].{field}", f"Unknown {field} asset '{asset_id}'.")

    for index, transition in enumerate(transitions):
        source = transition.get("from")
        target = transition.get("to")
        if source not in state_ids:
            add_issue(issues, "error", "unknown_transition_source", f"$.transitions[{index}].from", f"Unknown transition source '{source}'.")
        if target not in state_ids:
            add_issue(issues, "error", "unknown_transition_target", f"$.transitions[{index}].to", f"Unknown transition target '{target}'.")
        validate_expressions(transition.get("pre", []), asset_ids, state_ids, issues, f"$.transitions[{index}].pre", KNOWN_REQUIREMENTS)
        validate_expressions(transition.get("eff", []), asset_ids, state_ids, issues, f"$.transitions[{index}].eff", KNOWN_EFFECTS)
        if int(transition.get("cost", 1)) < 0:
            add_issue(issues, "error", "negative_transition_cost", f"$.transitions[{index}].cost", "Transition cost cannot be negative.")

    validate_rules(rules, asset_ids, state_ids, {state.get("kind", "state") for state in states}, issues)

    counts = Counter(issue["severity"] for issue in issues)
    return {
        "valid": counts.get("error", 0) == 0,
        "errors": counts.get("error", 0),
        "warnings": counts.get("warning", 0),
        "issues": issues,
        "summary": {
            "states": len(state_ids),
            "assets": len(asset_ids),
            "quests": len(quest_ids),
            "transitions": len(transition_ids),
        },
    }


def require_array(raw: Mapping[str, Any], field: str, issues: list[dict]) -> None:
    """Require a top-level list field in the story graph export."""

    if field not in raw:
        add_issue(issues, "error", "missing_field", f"$.{field}", f"Required field '{field}' is missing.")
    elif not isinstance(raw[field], list):
        add_issue(issues, "error", "wrong_type", f"$.{field}", f"Field '{field}' must be an array.")


def collect_ids(items: Iterable[Mapping[str, Any]], path: str, issues: list[dict]) -> set[str]:
    """Collect IDs and report missing or duplicated identifiers."""

    ids: list[str] = []
    for index, item in enumerate(items):
        item_id = item.get("id")
        if not item_id and path == "mandatory_story_states":
            item_id = item.get("state")
        if not item_id:
            add_issue(issues, "error", "missing_id", f"$.{path}[{index}]", "Item is missing an id.")
            continue
        ids.append(item_id)
    duplicates = {item_id for item_id, count in Counter(ids).items() if count > 1}
    for duplicate in sorted(duplicates):
        add_issue(issues, "error", "duplicate_id", f"$.{path}", f"Duplicate id '{duplicate}'.")
    return set(ids)


def validate_expressions(
    expressions: Iterable[str],
    asset_ids: set[str],
    state_ids: set[str],
    issues: list[dict],
    path: str,
    known_calls: set[str],
) -> None:
    """Validate predicate/effect syntax and its state or asset references."""

    for index, expression in enumerate(expressions):
        try:
            call = parse_call(expression)
        except ValueError as exc:
            add_issue(issues, "error", "invalid_expression", f"{path}[{index}]", str(exc))
            continue
        if call.name not in known_calls:
            add_issue(issues, "warning", "unknown_expression_call", f"{path}[{index}]", f"Unknown expression function '{call.name}'.")
        if call.name == "WantedLevelBelow" and call.args:
            # Numeric quantities are reduced to named boolean abstractions in
            # the checker. The export must declare at least one side explicitly.
            positive = f"WantedLevelBelow{call.args[0]}"
            negative = f"WantedLevelGE{call.args[0]}"
            if positive not in asset_ids and negative not in asset_ids:
                add_issue(
                    issues,
                    "error",
                    "unknown_numeric_abstraction",
                    f"{path}[{index}]",
                    f"Expected either '{positive}' or '{negative}' to be declared for {expression}.",
                )
        else:
            for asset_id in referenced_assets([expression]):
                if asset_id not in asset_ids:
                    add_issue(issues, "error", "unknown_asset_reference", f"{path}[{index}]", f"Expression references unknown asset '{asset_id}'.")
        if call.name in {"AtState", "NextStateIs", "EnterMission", "EnterHub", "CompleteMission", "ReachState"} and call.args:
            if call.args[0] not in state_ids:
                add_issue(issues, "error", "unknown_state_reference", f"{path}[{index}]", f"Expression references unknown state '{call.args[0]}'.")


def validate_rules(rules: Sequence, asset_ids: set[str], state_ids: set[str], state_kinds: set[str], issues: list[dict]) -> None:
    """Validate parsed DSL rules against the graph vocabulary."""

    for rule in rules:
        try:
            trigger = parse_call(rule.trigger)
        except ValueError as exc:
            add_issue(issues, "error", "invalid_rule_trigger", f"rules.{rule.name}.WHEN", str(exc))
            continue
        if trigger.name not in KNOWN_TRIGGERS:
            add_issue(issues, "warning", "unknown_rule_trigger", f"rules.{rule.name}.WHEN", f"Unknown trigger '{trigger.name}'.")
        if trigger.name in {"EnterMission", "EnterHub", "CompleteMission", "ReachState", "AtState"} and trigger.args and trigger.args[0] not in state_ids:
            add_issue(issues, "error", "unknown_rule_state", f"rules.{rule.name}.WHEN", f"Rule trigger references unknown state '{trigger.args[0]}'.")
        if trigger.name == "EnterKind" and trigger.args and trigger.args[0] not in state_kinds:
            add_issue(issues, "warning", "unknown_rule_kind", f"rules.{rule.name}.WHEN", f"Rule trigger references unknown state kind '{trigger.args[0]}'.")

        try:
            requirement = parse_call(rule.requirement)
        except ValueError as exc:
            add_issue(issues, "error", "invalid_rule_requirement", f"rules.{rule.name}.REQUIRE", str(exc))
            continue
        if requirement.name not in KNOWN_REQUIREMENTS:
            add_issue(issues, "warning", "unknown_rule_requirement", f"rules.{rule.name}.REQUIRE", f"Unknown requirement '{requirement.name}'.")
        validate_expressions([rule.requirement], asset_ids, state_ids, issues, f"rules.{rule.name}.REQUIRE", KNOWN_REQUIREMENTS)


def add_issue(issues: list[dict], severity: str, code: str, path: str, message: str) -> None:
    """Append one normalized validation issue."""

    issues.append(
        {
            "severity": severity,
            "code": code,
            "path": path,
            "message": message,
        }
    )
