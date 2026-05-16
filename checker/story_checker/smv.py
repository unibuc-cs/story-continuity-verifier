from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .analysis import StoryChecker
from .dsl import parse_call
from .models import StoryGraph, Transition


def write_smv(graph: StoryGraph, rules: Iterable, path: str | Path) -> None:
    """Write a finite NuSMV model for the story graph and supported DSL rules."""

    rule_list = list(rules)
    checker = StoryChecker(graph, rule_list, mode="SC")
    model = build_smv(graph, rule_list, sorted(checker.relevant_assets))
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(model, encoding="utf-8")


def run_nusmv(nusmv_path: str, smv_path: str | Path, output_path: str | Path | None = None) -> subprocess.CompletedProcess:
    """Run NuSMV and optionally persist combined stdout/stderr."""

    completed = subprocess.run(
        [nusmv_path, str(smv_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if output_path is not None:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    return completed


def build_smv(graph: StoryGraph, rules: Sequence, relevant_assets: Sequence[str]) -> str:
    """Build the textual SMV module used for external model-checker review."""

    state_names = {state_id: smv_id(state_id) for state_id in graph.states}
    asset_names = {asset_id: "has_" + smv_id(asset_id) for asset_id in relevant_assets}
    action_names = {transition.id: "act_" + smv_id(transition.id) for transition in graph.transitions}
    lines: list[str] = []
    lines.append("MODULE main")
    lines.append("")
    lines.append("VAR")
    lines.append("  state : {" + ", ".join(state_names[state_id] for state_id in graph.states) + "};")
    lines.append("  action : {idle, " + ", ".join(action_names[transition.id] for transition in graph.transitions) + "};")
    for asset_id in relevant_assets:
        lines.append(f"  {asset_names[asset_id]} : boolean;")
    lines.append("")
    lines.append("ASSIGN")
    lines.append(f"  init(state) := {state_names[graph.initial_state]};")
    for asset_id in relevant_assets:
        initial = "TRUE" if asset_id in graph.initial_assets else "FALSE"
        lines.append(f"  init({asset_names[asset_id]}) := {initial};")
    lines.append("")
    lines.append("TRANS")
    # The transition relation is disjunctive. The idle branch is enabled only
    # when no story transition can fire, so AX properties are not weakened by
    # arbitrary self-loops.
    transition_terms = [idle_relation(graph.transitions, state_names, asset_names)]
    transition_terms.extend(
        transition_relation(transition, state_names, asset_names, action_names[transition.id])
        for transition in graph.transitions
    )
    for index, term in enumerate(transition_terms):
        prefix = "  " if index == 0 else "  | "
        suffix = ";" if index + 1 == len(transition_terms) else ""
        lines.append(prefix + term + suffix)

    lines.append("")
    lines.append("DEFINE")
    for state_id, state_name in state_names.items():
        lines.append(f"  atState_{state_name} := state = {state_name};")
    for completion_state in sorted(graph.completion_states):
        lines.append(f"  completed_{state_names[completion_state]} := state = {state_names[completion_state]};")

    lines.append("")
    lines.append("-- CTL properties generated from the DSL.")
    for rule in rules:
        ctl = ctl_for_rule(rule, state_names, asset_names)
        if ctl.startswith("--"):
            lines.append(ctl)
        else:
            lines.append(f"CTLSPEC {ctl};")
    lines.append("")
    return "\n".join(lines)


def transition_condition(
    transition: Transition,
    state_names: Mapping[str, str],
    asset_names: Mapping[str, str],
) -> str:
    """Translate a transition guard into an SMV boolean condition."""

    parts = [f"state = {state_names[transition.source]}"]
    for expression in transition.pre:
        parts.append(predicate_to_smv(expression, state_names, asset_names))
    return " & ".join(parts)


def transition_relation(
    transition: Transition,
    state_names: Mapping[str, str],
    asset_names: Mapping[str, str],
    action_name: str,
) -> str:
    """Translate one story transition into an SMV next-state relation."""

    parts = [
        f"action = {action_name}",
        transition_condition(transition, state_names, asset_names),
        f"next(state) = {state_names[transition.target]}",
    ]
    add_effects = effects_for(transition, {"AddAsset", "AddFlag"})
    remove_effects = effects_for(transition, {"RemoveAsset", "RemoveFlag"})
    for asset_id, asset_var in asset_names.items():
        if asset_id in add_effects:
            parts.append(f"next({asset_var}) = TRUE")
        elif asset_id in remove_effects:
            parts.append(f"next({asset_var}) = FALSE")
        else:
            parts.append(f"next({asset_var}) = {asset_var}")
    return "(" + " & ".join(parts) + ")"


def idle_relation(
    transitions: Sequence[Transition],
    state_names: Mapping[str, str],
    asset_names: Mapping[str, str],
) -> str:
    """Allow stuttering only in dead-end configurations."""

    enabled_conditions = [
        transition_condition(transition, state_names, asset_names)
        for transition in transitions
    ]
    no_enabled = "!(" + " | ".join(f"({condition})" for condition in enabled_conditions) + ")" if enabled_conditions else "TRUE"
    parts = ["action = idle", no_enabled, "next(state) = state"]
    for asset_var in asset_names.values():
        parts.append(f"next({asset_var}) = {asset_var}")
    return "(" + " & ".join(parts) + ")"


def predicate_to_smv(expression: str, state_names: Mapping[str, str], asset_names: Mapping[str, str]) -> str:
    """Translate a supported predicate into an SMV expression."""

    call = parse_call(expression)
    if not call.args:
        return "FALSE"
    arg = call.args[0]
    if call.name in {"HasAsset", "HasFlag"}:
        return asset_names.get(arg, "FALSE")
    if call.name in {"NotHasAsset", "NotHasFlag", "MissingAsset"}:
        return "!" + asset_names.get(arg, "FALSE")
    if call.name in {"AtState", "NextStateIs", "EnterMission", "EnterHub", "CompleteMission", "ReachState"}:
        return f"state = {state_names[arg]}"
    if call.name == "WantedLevelBelow":
        # The numeric predicate shares the same boolean abstraction used by the
        # Python checker and Unity demo.
        positive = asset_names.get(f"WantedLevelBelow{arg}")
        negative = asset_names.get(f"WantedLevelGE{arg}")
        if positive and negative:
            return f"({positive} | !{negative})"
        if positive:
            return positive
        if negative:
            return f"!{negative}"
        return "TRUE"
    if call.name in {"AlwaysTrue", "True"}:
        return "TRUE"
    if call.name in {"AlwaysFalse", "False"}:
        return "FALSE"
    return "TRUE"


def trigger_to_smv(expression: str, state_names: Mapping[str, str], asset_names: Mapping[str, str]) -> str:
    """Translate a DSL trigger when it has a direct SMV predicate form."""

    call = parse_call(expression)
    if call.name in {"EnterMission", "EnterHub", "CompleteMission", "ReachState", "AtState"} and call.args:
        return f"state = {state_names[call.args[0]]}"
    return predicate_to_smv(expression, state_names, asset_names)


def ctl_for_rule(rule, state_names: Mapping[str, str], asset_names: Mapping[str, str]) -> str:
    """Generate a CTL property for rules NuSMV can represent directly."""

    trigger = trigger_to_smv(rule.trigger, state_names, asset_names)
    requirement_call = parse_call(rule.requirement)
    if rule.within_steps is not None:
        requirement = predicate_to_smv(rule.requirement, state_names, asset_names)
        # NuSMV CTL has no native AF<=k operator; bounded rules stay as comments
        # while the Python checker enforces them.
        return f"-- Bounded rule {rule.name}: AG({trigger} -> AF<= {rule.within_steps} {requirement})"
    if requirement_call.name == "NextStateIs" and requirement_call.args:
        target = requirement_call.args[0]
        return f"AG(({trigger}) -> AX state = {state_names[target]})"
    requirement = predicate_to_smv(rule.requirement, state_names, asset_names)
    return f"AG(({trigger}) -> {requirement})"


def effects_for(transition: Transition, effect_names: set[str]) -> set[str]:
    """Return asset IDs affected by a transition for the selected effect names."""

    result: set[str] = set()
    for expression in transition.eff:
        call = parse_call(expression)
        if call.name in effect_names and call.args:
            result.add(call.args[0])
    return result


def smv_id(value: str) -> str:
    """Sanitize arbitrary story IDs into NuSMV identifiers."""

    cleaned = []
    for char in value:
        if char.isalnum() or char == "_":
            cleaned.append(char)
        else:
            cleaned.append("_")
    result = "".join(cleaned).strip("_")
    if not result:
        result = "id"
    if result[0].isdigit():
        result = "S_" + result
    return result
