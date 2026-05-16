from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set


# Supported expressions deliberately look like function calls so the same text
# can move between Unity assets, JSON exports, Python analysis, and NuSMV export.
CALL_RE = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\((?P<args>.*)\)$")
ASSET_ARG_FUNCS = {
    "HasAsset",
    "HasFlag",
    "NotHasAsset",
    "NotHasFlag",
    "MissingAsset",
    "AddAsset",
    "AddFlag",
    "RemoveAsset",
    "RemoveFlag",
}


@dataclass(frozen=True)
class Call:
    """Parsed function-style expression."""

    name: str
    args: Sequence[str]


@dataclass(frozen=True)
class Rule:
    """One DSL continuity rule: trigger plus immediate or bounded requirement."""

    name: str
    trigger: str
    requirement: str
    within_steps: Optional[int] = None


def parse_call(expression: str) -> Call:
    # csv.reader handles quoted commas, which keeps the DSL usable for richer
    # parameter strings without adding a full parser.
    text = expression.strip()
    match = CALL_RE.match(text)
    if not match:
        raise ValueError(f"expected function-style expression, got '{expression}'")
    args_text = match.group("args").strip()
    if not args_text:
        return Call(match.group("name"), ())
    reader = csv.reader([args_text], skipinitialspace=True)
    args = next(reader)
    cleaned = [arg.strip().strip("\"'") for arg in args]
    return Call(match.group("name"), tuple(cleaned))


def referenced_assets(expressions: Iterable[str]) -> Set[str]:
    # WantedLevelBelow(N) is represented by boolean abstractions because the
    # checker tracks finite asset sets, not unbounded numeric variables.
    assets: Set[str] = set()
    for expression in expressions:
        try:
            call = parse_call(expression)
        except ValueError:
            continue
        if call.name in ASSET_ARG_FUNCS and call.args:
            assets.add(call.args[0])
        elif call.name == "WantedLevelBelow" and call.args:
            assets.add(f"WantedLevelBelow{call.args[0]}")
            assets.add(f"WantedLevelGE{call.args[0]}")
    return assets


def evaluate_predicate(expression: str, state: str, assets: Set[str] | frozenset[str]) -> bool:
    """Evaluate a supported predicate against one abstract configuration."""

    call = parse_call(expression)
    name = call.name
    args = call.args
    if name in {"HasAsset", "HasFlag"}:
        return bool(args) and args[0] in assets
    if name in {"NotHasAsset", "NotHasFlag", "MissingAsset"}:
        return bool(args) and args[0] not in assets
    if name in {"AtState", "NextStateIs"}:
        return bool(args) and state == args[0]
    if name == "WantedLevelBelow":
        if not args:
            return False
        bound = args[0]
        positive = f"WantedLevelBelow{bound}"
        negative = f"WantedLevelGE{bound}"
        # Either an explicit positive flag proves the bound, or the absence of
        # the negative abstraction leaves the story below the threshold.
        return positive in assets or negative not in assets
    if name in {"AlwaysTrue", "True"}:
        return True
    if name in {"AlwaysFalse", "False"}:
        return False
    raise ValueError(f"unsupported predicate '{expression}'")


def apply_effect(expression: str, assets: Set[str]) -> None:
    """Apply a supported transition effect in place."""

    call = parse_call(expression)
    if not call.args:
        return
    asset_id = call.args[0]
    if call.name in {"AddAsset", "AddFlag"}:
        assets.add(asset_id)
    elif call.name in {"RemoveAsset", "RemoveFlag"}:
        assets.discard(asset_id)
    elif call.name in {"NoOp", "None"}:
        return
    else:
        raise ValueError(f"unsupported effect '{expression}'")


def parse_rules(text: str) -> List[Rule]:
    """Parse the review DSL used by rules.dsl files."""

    rules: List[Rule] = []
    current_name: Optional[str] = None
    trigger: Optional[str] = None
    requirement: Optional[str] = None
    within: Optional[int] = None

    def flush() -> None:
        # A rule starts at RULE and is emitted once the next RULE or EOF appears.
        nonlocal current_name, trigger, requirement, within
        if current_name is None:
            return
        if trigger is None or requirement is None:
            raise ValueError(f"rule '{current_name}' is missing WHEN or REQUIRE")
        rules.append(Rule(current_name, trigger, requirement, within))
        current_name = None
        trigger = None
        requirement = None
        within = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("--") or line.startswith("#"):
            continue
        if line.startswith("RULE "):
            flush()
            current_name = line[len("RULE ") :].rstrip(":").strip()
            continue
        if current_name is None:
            raise ValueError(f"unexpected DSL line outside a rule: '{raw_line}'")
        if line.startswith("WHEN "):
            trigger = line[len("WHEN ") :].strip()
        elif line.startswith("REQUIRE "):
            requirement = line[len("REQUIRE ") :].strip()
        elif line.startswith("WITHIN "):
            parts = line.split()
            if len(parts) < 2 or not parts[1].isdigit():
                raise ValueError(f"WITHIN expects an integer step bound: '{raw_line}'")
            within = int(parts[1])
        else:
            raise ValueError(f"unsupported DSL line: '{raw_line}'")
    flush()
    return rules


def trigger_matches(trigger: str, state: str, state_kind: str = "state", tags: Sequence[str] = ()) -> bool:
    """Return true when a DSL trigger applies to the current story state."""

    call = parse_call(trigger)
    if call.name in {"EnterMission", "CompleteMission", "EnterHub", "ReachState", "AtState"}:
        return bool(call.args) and state == call.args[0]
    if call.name == "ReachTaggedState":
        return bool(call.args) and call.args[0] in tags
    if call.name == "EnterKind":
        return bool(call.args) and state_kind == call.args[0]
    raise ValueError(f"unsupported trigger '{trigger}'")


def next_state_requirement(requirement: str) -> Optional[str]:
    """Extract the target of REQUIRE NextStateIs(...) rules."""

    call = parse_call(requirement)
    if call.name == "NextStateIs" and call.args:
        return call.args[0]
    return None
