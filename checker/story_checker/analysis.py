from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, List, Optional, Set, Tuple

from .dsl import (
    apply_effect,
    evaluate_predicate,
    next_state_requirement,
    referenced_assets,
    trigger_matches,
)
from .models import StoryGraph, Transition, flatten


@dataclass(frozen=True)
class Config:
    """A reachable abstract runtime snapshot."""

    state: str
    assets: frozenset[str]


# Edges retain both endpoint configurations because asset effects can make the
# same story-state transition produce different abstract successors.
Edge = Tuple[Config, Transition, Config]


class StoryChecker:
    """Runs the paper-inspired continuity analyses over an exported story graph."""

    VALID_MODES = {"SR", "AQ", "RA", "SC"}

    def __init__(self, graph: StoryGraph, rules: Iterable, theta: int = 5, mode: str = "SC") -> None:
        self.graph = graph
        self.rules = list(rules)
        self.theta = theta
        self.mode = mode.upper()
        if self.mode not in self.VALID_MODES:
            raise ValueError(f"unsupported analysis mode '{mode}'")
        self.outgoing = graph.outgoing()
        # Resource-aware modes track only assets that can affect reachability,
        # mandatory-state contracts, rules, or repair suggestions. This keeps
        # the explored configuration space small enough for review demos.
        self.relevant_assets = self._compute_relevant_assets() if self._uses_asset_semantics() else set()
        self.initial = Config(graph.initial_state, self._project(graph.initial_assets))
        self.adjacency: Dict[Config, List[Tuple[Transition, Config]]] = defaultdict(list)
        self.reverse: Dict[Config, List[Config]] = defaultdict(list)
        self.predecessor: Dict[Config, Tuple[Config, Transition]] = {}
        self.reachable: Set[Config] = set()
        self._explored = False
        self._violations: List[dict] = []

    def run(self) -> dict:
        # The lower modes intentionally omit later checks. Their reports make it
        # easy to show why resource and semantic contracts reduce false comfort.
        self.explore()
        self._violations = []
        self._detect_hard_locks()
        self._detect_soft_locks()
        if self.mode == "AQ":
            self._detect_quest_diagnostics()
        elif self.mode == "RA":
            self._detect_irrecoverable_critical_losses()
        elif self.mode == "SC":
            self._detect_disposable_critical()
            self._detect_shortcuts()
            self._detect_recommended_assets()
            self._check_rules()
        violations = self._finalize_violations(self._violations)
        return {
            "graph": {
                "name": self.graph.name,
                "states": len(self.graph.states),
                "assets": len(self.graph.assets),
                "quests": len(self.graph.quests),
                "transitions": len(self.graph.transitions),
                "mandatory_story_states": len(self.graph.mandatory_states),
                "completion_states": sorted(self.graph.completion_states),
            },
            "analysis": {
                "mode": self.mode,
                "description": self._mode_description(),
                "soft_lock_threshold": self.theta,
                "relevant_assets": sorted(self.relevant_assets),
                "reachable_abstract_configurations": len(self.reachable),
                "induced_abstract_transitions": sum(len(edges) for edges in self.adjacency.values()),
                "root_causes": len(self._root_cause_summary(violations)),
            },
            "root_causes": self._root_cause_summary(violations),
            "violations": violations,
        }

    @classmethod
    def run_all(cls, graph: StoryGraph, rules: Iterable, theta: int = 5) -> dict:
        rule_list = list(rules)
        runs = {
            mode: cls(graph, rule_list, theta=theta, mode=mode).run()
            for mode in ("SR", "AQ", "RA", "SC")
        }
        return {
            "graph": runs["SC"]["graph"],
            "analysis": {
                "mode": "ALL",
                "soft_lock_threshold": theta,
                "runs": {
                    mode: {
                        "description": report["analysis"]["description"],
                        "reachable_abstract_configurations": report["analysis"]["reachable_abstract_configurations"],
                        "induced_abstract_transitions": report["analysis"]["induced_abstract_transitions"],
                        "violations": len(report["violations"]),
                        "root_causes": len(report["root_causes"]),
                    }
                    for mode, report in runs.items()
                },
            },
            "runs": runs,
            "violations": runs["SC"]["violations"],
        }

    def explore(self) -> None:
        if self._explored:
            return
        # Breadth-first exploration gives deterministic predecessor traces while
        # still covering every reachable abstract configuration.
        queue: Deque[Config] = deque([self.initial])
        self.reachable.add(self.initial)
        while queue:
            config = queue.popleft()
            for transition in self.outgoing.get(config.state, ()):
                if not self._enabled(transition, config):
                    continue
                next_config = self._apply_transition(transition, config)
                self.adjacency[config].append((transition, next_config))
                self.reverse[next_config].append(config)
                if next_config not in self.reachable:
                    self.reachable.add(next_config)
                    self.predecessor[next_config] = (config, transition)
                    queue.append(next_config)
        self._explored = True

    def _compute_relevant_assets(self) -> Set[str]:
        # Include assets that are never in the initial state but can appear as
        # quest rewards; otherwise acquisition routes would be projected away.
        mandatory_assets = flatten(
            tuple(ms.required) + tuple(ms.recommended)
            for ms in self.graph.mandatory_states.values()
        )
        rule_assets = referenced_assets(
            [rule.requirement for rule in self.rules]
            + [rule.trigger for rule in self.rules]
        )
        transition_assets = referenced_assets(
            expression
            for transition in self.graph.transitions
            for expression in tuple(transition.pre) + tuple(transition.eff)
        )
        quest_assets = flatten(quest.rewards for quest in self.graph.quests.values())
        return set(self.graph.initial_assets) | mandatory_assets | rule_assets | transition_assets | quest_assets | self.graph.critical_assets()

    def _project(self, assets: Iterable[str]) -> frozenset[str]:
        # Projection is the abstraction boundary used by the checker. Assets not
        # referenced by the story contract are ignored for state-space purposes.
        return frozenset(asset for asset in assets if asset in self.relevant_assets)

    def _enabled(self, transition: Transition, config: Config) -> bool:
        if not self._uses_asset_semantics():
            return True
        return all(evaluate_predicate(expr, config.state, config.assets) for expr in transition.pre)

    def _apply_transition(self, transition: Transition, config: Config) -> Config:
        if not self._uses_asset_semantics():
            return Config(transition.target, frozenset())
        assets = set(config.assets)
        for effect in transition.eff:
            apply_effect(effect, assets)
        return Config(transition.target, self._project(assets))

    def _uses_asset_semantics(self) -> bool:
        return self.mode in {"RA", "SC"}

    def _mode_description(self) -> str:
        return {
            "SR": "Structural reachability over story states; ignores quests, assets, and DSL rules.",
            "AQ": "Asset-agnostic reachability with quest diagnostics; ignores asset effects and DSL rules.",
            "RA": "Resource-aware reachability over abstract configurations; ignores DSL rules and mandatory-state contracts.",
            "SC": "Symbolic continuity: resource-aware graph checks plus mandatory-state requirements and DSL rules.",
        }[self.mode]

    def _completion_reachable(self) -> Set[Config]:
        completion_configs = [config for config in self.reachable if config.state in self.graph.completion_states]
        return self._reverse_reachable(completion_configs)

    def _distance_to_completion(self) -> Dict[Config, int]:
        distances: Dict[Config, int] = {}
        queue: Deque[Config] = deque()
        for config in self.reachable:
            if config.state in self.graph.completion_states:
                distances[config] = 0
                queue.append(config)
        while queue:
            current = queue.popleft()
            for previous in self.reverse.get(current, ()):
                if previous not in distances:
                    distances[previous] = distances[current] + 1
                    queue.append(previous)
        return distances

    def _reverse_reachable(self, starts: Iterable[Config]) -> Set[Config]:
        seen: Set[Config] = set(starts)
        queue: Deque[Config] = deque(seen)
        while queue:
            current = queue.popleft()
            for previous in self.reverse.get(current, ()):
                if previous not in seen:
                    seen.add(previous)
                    queue.append(previous)
        return seen

    def _detect_hard_locks(self) -> None:
        # A hard lock is any reachable configuration outside the reverse
        # completion basin.
        can_complete = self._completion_reachable()
        for config in sorted(self.reachable - can_complete, key=self._config_key):
            if config.state in self.graph.completion_states:
                continue
            self._add_violation(
                defect_class="hard_lock",
                config=config,
                message="Completion is no longer reachable from this configuration.",
                severity="error",
            )

    def _detect_soft_locks(self) -> None:
        # Soft locks keep completion possible but place it beyond the configured
        # recovery threshold.
        distances = self._distance_to_completion()
        for config, distance in sorted(distances.items(), key=lambda item: (item[1], self._config_key(item[0]))):
            if config.state in self.graph.completion_states:
                continue
            if distance > self.theta:
                self._add_violation(
                    defect_class="soft_lock",
                    config=config,
                    message=f"Shortest recovery path to completion is {distance} transitions, above theta={self.theta}.",
                    severity="warning",
                    metadata={"distance_to_completion": distance},
                )

    def _detect_shortcuts(self) -> None:
        # Mandatory states are allowed to be reachable multiple ways, but every
        # reaching configuration must satisfy the required resource contract.
        for config in sorted(self.reachable, key=self._config_key):
            mandatory = self.graph.mandatory_states.get(config.state)
            if mandatory is None:
                continue
            missing = sorted(set(mandatory.required) - set(config.assets))
            if missing:
                self._add_violation(
                    defect_class="shortcut",
                    config=config,
                    message=f"Mandatory state '{config.state}' is reachable without required assets: {', '.join(missing)}.",
                    severity="error",
                    missing_assets=missing,
                    repair_suggestions=self._repair_suggestions(missing),
                )

    def _detect_recommended_assets(self) -> None:
        # Recommended assets are review advisories, not correctness failures.
        for config in sorted(self.reachable, key=self._config_key):
            mandatory = self.graph.mandatory_states.get(config.state)
            if mandatory is None:
                continue
            missing = sorted(set(mandatory.recommended) - set(config.assets))
            if missing:
                self._add_violation(
                    defect_class="recommended_asset_missing",
                    config=config,
                    message=f"Mandatory state '{config.state}' is reachable without recommended assets: {', '.join(missing)}.",
                    severity="info",
                    missing_assets=missing,
                    repair_suggestions=self._repair_suggestions(missing),
                    metadata={"advisory": True},
                )

    def _detect_disposable_critical(self) -> None:
        # This is stricter than generic resource loss: the removed asset must be
        # critical and still needed by a reachable mandatory state.
        all_edges = self._all_edges()
        for asset_id in sorted(self.graph.critical_assets()):
            configs_with_asset = [config for config in self.reachable if asset_id in config.assets]
            if not configs_with_asset:
                continue
            can_recover_asset = self._reverse_reachable(configs_with_asset)
            mandatory_targets = [
                config
                for config in self.reachable
                if self.graph.mandatory_states.get(config.state) is not None
                and asset_id in self.graph.mandatory_states[config.state].required
            ]
            if not mandatory_targets:
                continue
            can_reach_required_state = self._reverse_reachable(mandatory_targets)
            for source, transition, target in all_edges:
                if asset_id not in source.assets or asset_id in target.assets:
                    continue
                if source in can_recover_asset and target not in can_recover_asset and target in can_reach_required_state:
                    self._add_violation(
                        defect_class="disposable_critical_resource",
                        config=target,
                        message=f"Transition '{transition.id}' irreversibly removes critical asset '{asset_id}' while a mandatory state still requires it.",
                        severity="error",
                        missing_assets=[asset_id],
                        extra_edge=(source, transition, target),
                        repair_suggestions=self._repair_suggestions([asset_id]),
                    )

    def _detect_irrecoverable_critical_losses(self) -> None:
        # RA mode reports critical losses without looking at mandatory-state
        # contracts. This intentionally produces broader warnings than SC mode.
        all_edges = self._all_edges()
        for asset_id in sorted(self.graph.critical_assets()):
            configs_with_asset = [config for config in self.reachable if asset_id in config.assets]
            if not configs_with_asset:
                continue
            can_recover_asset = self._reverse_reachable(configs_with_asset)
            for source, transition, target in all_edges:
                if asset_id not in source.assets or asset_id in target.assets:
                    continue
                if source in can_recover_asset and target not in can_recover_asset:
                    self._add_violation(
                        defect_class="resource_loss",
                        config=target,
                        message=f"Transition '{transition.id}' removes critical asset '{asset_id}' and no recovery route is visible in the exported graph.",
                        severity="warning",
                        missing_assets=[asset_id],
                        extra_edge=(source, transition, target),
                        repair_suggestions=self._repair_suggestions([asset_id]),
                    )

    def _detect_quest_diagnostics(self) -> None:
        # AQ mode does not evaluate assets, so quest diagnostics are limited to
        # structural omissions visible in the exported graph.
        reachable_states = {config.state for config in self.reachable}
        for quest in sorted(self.graph.quests.values(), key=lambda item: item.id):
            if quest.id in self.graph.states and quest.id not in reachable_states:
                self._add_violation(
                    defect_class="quest_unreachable",
                    config=Config(quest.id, frozenset()),
                    message=f"Quest '{quest.id}' is declared but unreachable in the asset-agnostic story graph.",
                    severity="warning",
                )
            if quest.role == "side" and not quest.rewards:
                self._add_violation(
                    defect_class="quest_reward_missing",
                    config=self.initial,
                    message=f"Side quest '{quest.id}' has no exported reward relation.",
                    severity="warning",
                )

    def _check_rules(self) -> None:
        # DSL rules are evaluated only in SC mode after resource-aware
        # reachability has fixed the set of possible configurations.
        for rule in self.rules:
            expected_next = next_state_requirement(rule.requirement)
            for config in sorted(self.reachable, key=self._config_key):
                state = self.graph.states[config.state]
                if not trigger_matches(rule.trigger, config.state, state.kind, state.tags):
                    continue
                if rule.within_steps is not None:
                    if not self._has_bounded_path(config, rule.requirement, rule.within_steps):
                        self._add_violation(
                            defect_class="dsl_bounded_reachability",
                            config=config,
                            rule=rule.name,
                            message=f"Rule '{rule.name}' was not satisfied within {rule.within_steps} transitions.",
                            severity="error",
                        )
                    continue
                if expected_next is not None:
                    edges = self.adjacency.get(config, ())
                    bad_edges = [(transition, target) for transition, target in edges if target.state != expected_next]
                    if not edges:
                        self._add_violation(
                            defect_class="dsl_ordering",
                            config=config,
                            rule=rule.name,
                            message=f"Rule '{rule.name}' expected next state '{expected_next}', but no transition is enabled.",
                            severity="error",
                        )
                    for transition, target in bad_edges:
                        self._add_violation(
                            defect_class="dsl_ordering",
                            config=target,
                            rule=rule.name,
                            message=f"Rule '{rule.name}' expected next state '{expected_next}', but transition '{transition.id}' reaches '{target.state}'.",
                            severity="error",
                            extra_edge=(config, transition, target),
                        )
                    continue
                if not evaluate_predicate(rule.requirement, config.state, config.assets):
                    self._add_violation(
                        defect_class="dsl_invariant",
                        config=config,
                        rule=rule.name,
                        message=f"Rule '{rule.name}' is violated at state '{config.state}'.",
                        severity="error",
                        missing_assets=self._missing_assets_for_requirement(rule.requirement, config),
                    )

    def _has_bounded_path(self, start: Config, requirement: str, max_depth: int) -> bool:
        # Bounded rules use a local BFS instead of the global completion
        # distance because the target predicate can be any supported DSL call.
        if evaluate_predicate(requirement, start.state, start.assets):
            return True
        queue: Deque[Tuple[Config, int]] = deque([(start, 0)])
        seen: Set[Config] = {start}
        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for _, target in self.adjacency.get(current, ()):
                if target in seen:
                    continue
                if evaluate_predicate(requirement, target.state, target.assets):
                    return True
                seen.add(target)
                queue.append((target, depth + 1))
        return False

    def _all_edges(self) -> List[Edge]:
        return [
            (source, transition, target)
            for source, edges in self.adjacency.items()
            for transition, target in edges
        ]

    def _trace_to(self, config: Config, extra_edge: Optional[Edge] = None) -> dict:
        # Traces are serialized in the Unity replay harness shape so the checker
        # output can be replayed directly in the demo project.
        edges: List[Edge] = []
        current = config
        if extra_edge is not None:
            edges.append(extra_edge)
            current = extra_edge[0]
        while current in self.predecessor:
            previous, transition = self.predecessor[current]
            edges.append((previous, transition, current))
            current = previous
        edges.reverse()
        actions = []
        for index, (source, transition, target) in enumerate(edges):
            actions.append(
                {
                    "index": index,
                    "transition_id": transition.id,
                    "action_type": transition.action_type,
                    "from": source.state,
                    "to": target.state,
                    "params": dict(transition.params),
                    "parameters": [
                        {"key": str(key), "value": str(value)}
                        for key, value in transition.params.items()
                    ],
                    "expected_state": target.state,
                    "expected_assets": sorted(target.assets),
                }
            )
        return {
            "initial_state": self.initial.state,
            "initial_assets": sorted(self.initial.assets),
            "actions": actions,
        }

    def _repair_suggestions(self, missing_assets: Iterable[str]) -> List[dict]:
        suggestions = []
        for asset_id in missing_assets:
            quests = self.graph.support_quests_for(asset_id)
            if quests:
                suggestions.append(
                    {
                        "asset": asset_id,
                        "support_quests": quests,
                        "suggestion": "Keep at least one support quest available or add an alternative acquisition route before the mandatory state.",
                    }
                )
            else:
                suggestions.append(
                    {
                        "asset": asset_id,
                        "support_quests": [],
                        "suggestion": "Add an acquisition route or relax the mandatory-state requirement if this sequence is intended.",
                    }
                )
        return suggestions

    def _missing_assets_for_requirement(self, requirement: str, config: Config) -> List[str]:
        refs = referenced_assets([requirement])
        return sorted(asset for asset in refs if asset in self.graph.assets and asset not in config.assets)

    def _add_violation(
        self,
        defect_class: str,
        config: Config,
        message: str,
        severity: str,
        rule: Optional[str] = None,
        missing_assets: Optional[List[str]] = None,
        extra_edge: Optional[Edge] = None,
        repair_suggestions: Optional[List[dict]] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        merged_metadata = dict(metadata or {})
        if extra_edge is not None:
            merged_metadata.setdefault("offending_transition", extra_edge[1].id)
        self._violations.append(
            {
                "id": f"V{len(self._violations) + 1:04d}",
                "class": defect_class,
                "severity": severity,
                "rule": rule,
                "state": config.state,
                "assets": sorted(config.assets),
                "missing_assets": missing_assets or [],
                "message": message,
                "trace": self._trace_to(config, extra_edge),
                "repair_suggestions": repair_suggestions or [],
                "metadata": merged_metadata,
            }
        )

    def _finalize_violations(self, violations: List[dict]) -> List[dict]:
        # First remove byte-for-byte equivalent reports, then preserve
        # near-duplicates by annotating the shared root cause for triage.
        seen = set()
        exact_deduped = []
        for violation in violations:
            key = (
                violation["class"],
                violation.get("rule"),
                violation["state"],
                tuple(violation["missing_assets"]),
                tuple(action["transition_id"] for action in violation["trace"]["actions"][-2:]),
            )
            if key in seen:
                continue
            seen.add(key)
            exact_deduped.append(violation)

        first_by_root: Dict[str, str] = {}
        for index, violation in enumerate(exact_deduped, start=1):
            violation["id"] = f"V{index:04d}"
            root_key = self._root_cause_key(violation)
            violation["root_cause_key"] = root_key
            if root_key in first_by_root:
                violation["duplicate_of"] = first_by_root[root_key]
            else:
                first_by_root[root_key] = violation["id"]
                violation["duplicate_of"] = None
        return exact_deduped

    def _root_cause_summary(self, violations: List[dict]) -> List[dict]:
        grouped: Dict[str, List[dict]] = defaultdict(list)
        for violation in violations:
            grouped[violation["root_cause_key"]].append(violation)
        result = []
        for root_key, items in sorted(grouped.items()):
            first = items[0]
            result.append(
                {
                    "key": root_key,
                    "primary_id": first["id"],
                    "class": first["class"],
                    "rule": first.get("rule"),
                    "state": first["state"],
                    "missing_assets": first["missing_assets"],
                    "reports": [item["id"] for item in items],
                    "duplicate_count": max(0, len(items) - 1),
                }
            )
        return result

    def _root_cause_key(self, violation: dict) -> str:
        # The key trades precision for reviewability: it groups symptoms that a
        # designer would likely fix in one content edit.
        defect_class = violation["class"]
        missing = ",".join(violation.get("missing_assets") or [])
        if defect_class == "hard_lock":
            return f"hard_lock|{violation['state']}"
        if defect_class == "soft_lock":
            return f"soft_lock|{violation['state']}"
        if defect_class in {"disposable_critical_resource", "resource_loss"}:
            transition_id = violation.get("metadata", {}).get("offending_transition") or self._last_transition_id(violation)
            return f"critical_loss|{missing}|{transition_id}"
        if defect_class in {"shortcut", "recommended_asset_missing"}:
            return f"{defect_class}|{violation['state']}|{missing}"
        if defect_class.startswith("dsl_"):
            return f"{defect_class}|{violation.get('rule')}|{violation['state']}|{missing}"
        return f"{defect_class}|{violation.get('rule')}|{violation['state']}|{missing}|{self._last_transition_id(violation)}"

    @staticmethod
    def _last_transition_id(violation: dict) -> str:
        actions = violation.get("trace", {}).get("actions", [])
        if not actions:
            return ""
        return actions[-1].get("transition_id", "")

    @staticmethod
    def _config_key(config: Config) -> Tuple[str, Tuple[str, ...]]:
        return config.state, tuple(sorted(config.assets))
