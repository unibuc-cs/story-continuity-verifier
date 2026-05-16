# Paper-to-Code Traceability Matrix

This document maps the claims and artefacts in `docs/paper/main.tex` to the current implementation. Its purpose is to make the correspondence between the paper, the public artefact, and known limitations explicit.

## Status Legend

| Status | Meaning |
| --- | --- |
| Implemented | Present in code and exercised by generated reports or tests. |
| Partial | Implemented for the demo path, but not at the full scope described in the paper. |
| Demo-only | Present as a small seeded prototype, not as the full paper evaluation dataset. |
| Out of scope | Deliberately not implemented in this public artefact. |
| Missing | Described in the paper but not yet represented in the implementation. |

## Research Questions

| Paper item | Current status | Implementation evidence | Review note |
| --- | --- | --- | --- |
| RQ1: resource-annotated story graphs and continuity requirements | Implemented | `checker/story_checker/models.py`, `examples/unity_chapter/story_graph.json`, `examples/unity_chapter/rules.dsl`, `unity-demo/Assets/StoryFeasibility/Editor/StoryGraphExporter.cs` | Covers states, assets, quests, guarded transitions, mandatory states, and P1-P4 style rules. |
| RQ2: trace-to-replay validity | Partial | `checker/story_checker/analysis.py` trace generation, `unity-demo/Assets/StoryFeasibility/Runtime/StoryReplayHarness.cs`, `unity-demo/Assets/StoryFeasibility/Tests/PlayMode/StoryRuntimePlayModeTests.cs` | Replay harness and trace shape exist; PlayMode tests validate replay mechanics. Automated batch replay of every generated checker trace is not yet implemented. |
| RQ3: pipeline utility against SR/AQ/RA baselines | Demo-only | `StoryChecker.run_all`, `checker/story_checker/metrics.py`, generated `examples/unity_chapter/metrics.json` | The implementation compares SR/AQ/RA/SC on the compact seeded chapter. It does not reproduce industrial case studies or paper-scale timing tables. |

## Contributions

| Paper contribution | Current status | Implementation evidence | Gap or limitation |
| --- | --- | --- | --- |
| Engine-independent analysis core with project adapters | Implemented | Python checker under `checker/story_checker`; Unity adapter under `unity-demo/Assets/StoryFeasibility` | Only Unity ScriptableObject adapter is implemented. Database-backed extraction is not included. |
| Requirements language over missions, assets, and progression constraints | Implemented | `checker/story_checker/dsl.py`, `examples/unity_chapter/rules.dsl`, schema checks in `checker/story_checker/schema.py` | DSL is intentionally small and function-call based. |
| Translation to symbolic verification models | Partial | `checker/story_checker/smv.py`, generated `examples/unity_chapter/story_model.smv`, `tools/NuSMV/.../NuSMV.exe` | Unbounded CTL-style rules are emitted for NuSMV. Step-bounded rules are checked in Python and emitted as SMV comments, not as full bounded-unrolling models. |
| Trace mapping to replayable playthroughs | Partial | `trace` fields in `story_report.json`, files under `examples/unity_chapter/traces`, `StoryReplayHarness.cs` | Runtime hook path exists. UI-driven replay and batch replay of all generated traces are not included. |
| Repair suggestions for missing prerequisites | Implemented | `_repair_suggestions` in `checker/story_checker/analysis.py`, report fields in `story_report.json` and Markdown | Suggestions are currently asset/support-quest based. They do not synthesize full content patches. |
| Empirical evaluation on two commercial games and open-source Unity prototype | Demo-only | `examples/unity_chapter/ground_truth.json`, generated metrics | Commercial case studies and full paper-scale Unity dataset are not present in this repo. |

## Method Artefacts

| Paper section | Paper concept | Current status | Implementation evidence | Notes |
| --- | --- | --- | --- | --- |
| Framework Overview | Chapter slice as bounded content unit | Implemented | `examples/unity_chapter/story_graph.json`, `unity-demo/Assets/StoryFeasibility/DemoData` | Current chapter is a compact seeded slice: 16 states, 10 assets/flags, 5 quests, 20 transitions. |
| Framework Overview | Project-specific extraction adapter | Implemented | `StoryGraphExporter.cs`, `DemoChapterFactory.cs` | Exports Unity ScriptableObjects to the checker JSON contract. |
| Framework Overview | Optional replay adapter | Partial | `StoryRuntime.cs`, `StoryReplayHarness.cs` | Replays through direct runtime hooks, not UI automation. |
| Story-Graph Model | `G = (S, A, Q, T, s0, F)` | Implemented | `StoryGraph` in `models.py` | Uses `states`, `assets`, `quests`, `transitions`, `initial_state`, `completion_states`. |
| Story-Graph Model | Configurations `(state, assets)` | Implemented | `Config` in `analysis.py` | Explored by BFS over projected asset sets. |
| Story-Graph Model | Asset categories | Implemented | `StoryAssetCategory` in Unity, `Asset.category` in Python, `critical_assets()` | Categories accepted by schema: flag, unique, critical, replenishable, transformable. |
| Story-Graph Model | Mandatory story states with required assets | Implemented | `MandatoryState`, `mandatory_story_states`, `_detect_shortcuts` | Required assets produce blocking shortcut defects. |
| Story-Graph Model | Recommended assets | Implemented | `recommended` field, `_detect_recommended_assets` | Implemented as severity `info` advisories. |
| Quests and Repair | Quest rewards and support relations | Implemented | `Quest.rewards`, `Asset.support_quests`, `support_quests_for` | Used for repair suggestions. |
| Quests and Repair | Repair suggestion as candidate content changes | Partial | `_repair_suggestions` | Suggests support quests or alternative acquisition routes; does not edit content automatically. |
| Defect Taxonomy | Hard lock | Implemented | `_detect_hard_locks` | Reverse reachability from completion configurations. |
| Defect Taxonomy | Soft lock | Implemented | `_detect_soft_locks`, `--theta` | Uses transition-count distance to completion. |
| Defect Taxonomy | Disposable-critical resource | Implemented | `_detect_disposable_critical` | Requires critical/unique asset loss plus reachable mandatory requirement. |
| Defect Taxonomy | Requirement-violating shortcut | Implemented | `_detect_shortcuts`, P1 DSL check | Reports mandatory states reached without required assets. |
| Pipeline Interfaces | `StoryGraphExtractor` | Implemented | `StoryGraphExporter.cs` | Named `StoryGraphExporter` in code; serves the extractor role. |
| Pipeline Interfaces | `ReplayHarness` | Implemented | `StoryReplayHarness.cs` | Maps abstract transition IDs to `StoryRuntime.TryExecuteTransition`. |
| Export Schema | Engine-independent JSON | Implemented | `schema.py`, `story_graph.json`, Unity exporter | Schema validation reports path-based errors and warnings. |
| Verification Model | Finite transition system from JSON | Implemented | `StoryGraph.from_dict`, `StoryChecker.explore`, `smv.py` | Python checker is the executable reference for the demo. |
| Verification Model | CTL model construction | Partial | `smv.py`, generated `.smv` and `nusmv_output.txt` | NuSMV runs supported unbounded properties. |

## DSL and Properties

| Paper rule/property | Current status | Implementation evidence | Expected demo signal |
| --- | --- | --- | --- |
| P1 `BossPrereqsMet`: entering boss requires `SniperRifle` | Implemented | `rules.dsl`, `_check_rules`, NuSMV CTL output | Fails on seeded shortcut into `M7_Boss`. |
| P2 `HubObjectiveReachable`: objective reachable within K steps | Implemented in Python, partial in NuSMV | `_has_bounded_path`; SMV emits bounded rule as comment | Python checker enforces bounded reachability. |
| P3 `NoFinalWhileHighlyWanted` | Implemented | `WantedLevelBelow` predicate, NuSMV CTL output | Fails when `WantedLevelGE4` remains active at ending. |
| P4 `EscapeImmediatelyAfterHeist` | Implemented | `NextStateIs`, NuSMV AX property | Passes in the current demo. |
| Numeric abstractions such as `WantedLevelBelow(4)` | Implemented | `dsl.py`, `schema.py`, `smv.py`, Unity evaluator | Encoded through boolean assets such as `WantedLevelGE4`. |

## Algorithms and Reporting

| Paper item | Current status | Implementation evidence | Notes |
| --- | --- | --- | --- |
| Abstract configuration projection | Implemented | `_compute_relevant_assets`, `_project` | Keeps only assets referenced by rules, transitions, mandatory states, quests, and critical categories. |
| Worklist exploration | Implemented | `StoryChecker.explore` | BFS preserves deterministic predecessor traces. |
| FindShortcutBugs algorithm | Implemented | `_detect_shortcuts` | Same concept as the paper pseudocode. |
| Graph procedures with `O(|Sigma_a| + |T_a|)` behavior | Implemented conceptually | `explore`, reverse reachability, distances | The repo does not include a formal complexity proof. |
| Counterexample traces | Implemented | `_trace_to`, `write_trace_files` | JSON trace format is compatible with Unity `JsonUtility`. |
| Root-cause grouping and duplicate triage | Implemented | `_root_cause_key`, `duplicate_of`, `root_causes`, `write_triage_csv` | Aligns with paper labelling procedure. |
| Markdown/JSON reports | Implemented | `reporting.py`, generated report files | JSON remains source of truth; Markdown and CSV support review. |

## Evaluation Claims

| Paper evaluation item | Current status | Implementation evidence | Important distinction |
| --- | --- | --- | --- |
| SR, AQ, RA, SC baselines | Implemented | `--mode all`, `StoryChecker.run_all`, `metrics.json` | Runs on compact demo. |
| Detection rate and false positives | Implemented for demo | `ground_truth.json`, `metrics.py` | Current ground truth has 6 seeded entries, not the 28-defect Unity dataset in the paper table. |
| Replay success rate | Partial | PlayMode test `ReplayHarnessReplaysTrace` | No automated replay-success metric over every generated trace yet. |
| Trace length | Partial | Reports contain trace action counts | No aggregate median/min/max report yet. |
| Analysis time | Missing | None | Verification script runs checks but does not currently write timing metrics. |
| Peak memory | Missing | None | Not measured in this implementation. |
| Adoption effort table | Documentation only | `docs/implementation-notes.md` | Effort estimates are not produced by code. |
| Industrial case studies | Out of scope | None | Requires private commercial data and adapters. |
| Full open-source Unity prototype from paper table | Missing | Current Unity demo is smaller | The current implementation is a compact replication artefact, not the full paper-scale dataset. |

## Verification Evidence

Run the full local verification with:

```powershell
.\verify.ps1
```

The script exercises:

- Python syntax compilation
- Python unit tests
- checker + NuSMV pipeline on `examples/unity_chapter`
- Unity batch compile
- Unity PlayMode tests
- Unity batch export
- checker metrics on the Unity-exported graph

Expected core results:

- Python unit tests: 5 passed
- Unity PlayMode tests: 4 passed, 0 failed
- checker SC mode: 52 configurations, 20 SC violations, 11 root causes
- SC metrics: 6/6 seeded ground-truth entries detected

## Remaining Work

These items would move the public artefact closer to the full method described in the paper:

1. Add automated Unity batch replay for every generated `V*_trace.json` and write replay success metrics.
2. Implement bounded-rule translation into an extended NuSMV model instead of emitting a comment.
3. Add timing and trace-length aggregation to `metrics.json`.
4. Expand the Unity prototype data toward the paper-scale dataset or adjust paper text to describe this smaller replication artefact.
5. Add a formal JSON Schema file beside the Python schema validator for external tooling.
6. Add UI-driven replay only if reviewers need parity with production UI automation; otherwise keep direct runtime hooks as the lower-maintenance path.
