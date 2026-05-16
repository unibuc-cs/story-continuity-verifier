"""Typed in-memory representation of the exported story graph JSON.

The checker keeps this layer intentionally small: schema-level diagnostics live
in schema.py, while this module converts a valid export into immutable data
records that the analysis code can traverse.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple


@dataclass(frozen=True)
class State:
    """A story node exported from Unity or authored directly in JSON."""

    id: str
    kind: str = "state"
    tags: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Asset:
    """A resource, flag, or abstraction used by predicates and effects."""

    id: str
    category: str = "flag"
    support_quests: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Quest:
    """Quest metadata used for diagnostics and repair suggestions."""

    id: str
    role: str = "side"
    rewards: Tuple[str, ...] = ()
    pre: Tuple[str, ...] = ()


@dataclass(frozen=True)
class MandatoryState:
    """Contract for a main story state that must not be bypassed."""

    state: str
    required: Tuple[str, ...] = ()
    recommended: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Transition:
    """Directed story action with predicate preconditions and asset effects."""

    id: str
    source: str
    target: str
    pre: Tuple[str, ...] = ()
    eff: Tuple[str, ...] = ()
    action_type: str = "transition"
    params: Mapping[str, Any] = field(default_factory=dict)
    cost: int = 1


@dataclass
class StoryGraph:
    """Complete story graph plus entry and completion contracts."""

    states: Dict[str, State]
    assets: Dict[str, Asset]
    quests: Dict[str, Quest]
    mandatory_states: Dict[str, MandatoryState]
    transitions: List[Transition]
    initial_state: str
    completion_states: Set[str]
    initial_assets: Set[str] = field(default_factory=set)
    name: str = "chapter"

    @classmethod
    def load(cls, path: str | Path) -> "StoryGraph":
        with Path(path).open("r", encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "StoryGraph":
        # The exporter uses compact JSON objects. Tuple conversion prevents
        # accidental mutation of nested content while exploring configurations.
        states = {
            item["id"]: State(
                id=item["id"],
                kind=item.get("kind", "state"),
                tags=tuple(item.get("tags", ())),
            )
            for item in raw.get("states", ())
        }
        assets = {
            item["id"]: Asset(
                id=item["id"],
                category=item.get("category", "flag"),
                support_quests=tuple(item.get("support_quests", ())),
            )
            for item in raw.get("assets", ())
        }
        quests = {
            item["id"]: Quest(
                id=item["id"],
                role=item.get("role", "side"),
                rewards=tuple(item.get("rewards", ())),
                pre=tuple(item.get("pre", ())),
            )
            for item in raw.get("quests", ())
        }
        mandatory_states = {
            item["state"]: MandatoryState(
                state=item["state"],
                required=tuple(item.get("required", ())),
                recommended=tuple(item.get("recommended", ())),
            )
            for item in raw.get("mandatory_story_states", ())
        }

        transitions: List[Transition] = []
        for index, item in enumerate(raw.get("transitions", ())):
            source = item.get("from")
            target = item.get("to")
            transitions.append(
                Transition(
                    id=item.get("id") or f"{source}->{target}#{index}",
                    source=source,
                    target=target,
                    pre=tuple(item.get("pre", ())),
                    eff=tuple(item.get("eff", ())),
                    action_type=item.get("action_type", "transition"),
                    params=item.get("params", {}),
                    cost=int(item.get("cost", 1)),
                )
            )

        graph = cls(
            states=states,
            assets=assets,
            quests=quests,
            mandatory_states=mandatory_states,
            transitions=transitions,
            initial_state=raw["initial_state"],
            completion_states=set(raw.get("completion_states", ())),
            initial_assets=set(raw.get("initial_assets", ())),
            name=raw.get("name", "chapter"),
        )
        graph.validate()
        return graph

    def validate(self) -> None:
        # This validation is intentionally fatal and minimal. The user-facing
        # schema validator collects detailed path-based errors before this runs.
        if self.initial_state not in self.states:
            raise ValueError(f"initial_state '{self.initial_state}' is not declared")
        for state in self.completion_states:
            if state not in self.states:
                raise ValueError(f"completion state '{state}' is not declared")
        for state in self.mandatory_states:
            if state not in self.states:
                raise ValueError(f"mandatory state '{state}' is not declared")
        for transition in self.transitions:
            if transition.source not in self.states:
                raise ValueError(f"transition '{transition.id}' has unknown source '{transition.source}'")
            if transition.target not in self.states:
                raise ValueError(f"transition '{transition.id}' has unknown target '{transition.target}'")

    def outgoing(self) -> Dict[str, List[Transition]]:
        result: Dict[str, List[Transition]] = {state: [] for state in self.states}
        for transition in self.transitions:
            result.setdefault(transition.source, []).append(transition)
        return result

    def critical_assets(self) -> Set[str]:
        # "unique" is treated as critical for the prototype because a one-off
        # resource can become a continuity blocker even without that exact label.
        return {
            asset.id
            for asset in self.assets.values()
            if asset.category.lower() in {"unique", "critical"}
        }

    def support_quests_for(self, asset_id: str) -> List[str]:
        # Prefer explicit asset metadata, then infer side-quest support from
        # quest rewards so repair suggestions work with either authoring style.
        direct = list(self.assets.get(asset_id, Asset(asset_id)).support_quests)
        rewarding = [
            quest.id
            for quest in self.quests.values()
            if quest.role == "side" and asset_id in quest.rewards and quest.id not in direct
        ]
        return direct + rewarding

    def declared_assets(self) -> Set[str]:
        return set(self.assets)


def flatten(values: Iterable[Iterable[str]]) -> Set[str]:
    """Collapse a sequence of string collections into one set."""

    result: Set[str] = set()
    for group in values:
        result.update(group)
    return result
