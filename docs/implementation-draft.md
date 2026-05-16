# Implementation Draft: Unity Story Continuity Demo

This draft turns the paper architecture into a reviewable end-to-end prototype:

1. Unity-authored story metadata is represented as ScriptableObjects.
2. `StoryGraphExtractor` editor tooling exports the metadata as an engine-independent JSON story graph.
3. A standalone checker loads the JSON graph and DSL rules, explores abstract configurations, and reports continuity defects.
4. Counterexample traces are exported as JSON files.
5. `ReplayHarness` consumes a trace and replays it against the Unity runtime adapter.

The implementation keeps the checker core dependency-free. NuSMV integration is optional and runs through the local executable under `tools/`.

## Repository Layout

```text
checker/
  check_story.py                  CLI entry point
  story_checker/
    models.py                     JSON schema model
    dsl.py                        DSL parser and predicate evaluator
    analysis.py                   SC checker and graph algorithms
    reporting.py                  JSON, Markdown, and trace outputs
    schema.py                     export contract validation
    smv.py                        NuSMV model generation and runner
    metrics.py                    seeded-defect metrics
  tests/
    test_demo.py                  regression checks for the demo slice

examples/unity_chapter/
  story_graph.json                exported demo graph
  rules.dsl                       continuity rules
  story_report.json               generated checker report
  story_report.md                 generated human-readable report
  story_model.smv                 generated NuSMV transition model
  nusmv_output.txt                NuSMV run output
  ground_truth.json               seeded-defect ground truth
  metrics.json                    detection, false-positive, and duplicate metrics
  schema_report.json              export-contract validation diagnostics
  triage.csv                      QA-friendly violation export
  traces/                         Unity-ready per-violation traces

unity-demo/
  Assets/StoryFeasibility/
    Runtime/                      content definitions, runtime, replay harness
    Editor/                       demo asset factory and graph exporter
    Tests/PlayMode/               Unity PlayMode tests
  Exported/                       batch-exported Unity graph and checker outputs
  Logs/                           Unity batchmode logs
  TestResults/                    Unity test results

tools/                            NuSMV installation notes; local NuSMV binaries are git-ignored
verify.ps1                        one-command local verification script
```

## Paper-to-Code Mapping

| Paper concept | Prototype artifact |
| --- | --- |
| Resource-annotated story graph | `examples/unity_chapter/story_graph.json`, `StoryGraph` in `models.py` |
| `StoryGraphExtractor` adapter | `unity-demo/Assets/StoryFeasibility/Editor/StoryGraphExporter.cs` |
| Continuity DSL | `examples/unity_chapter/rules.dsl`, parser in `dsl.py` |
| Abstract configurations `(state, assets)` | `Config` in `analysis.py` |
| SC checker | `StoryChecker.run()` in `analysis.py` |
| SR/AQ/RA baselines | `--mode sr`, `--mode aq`, `--mode ra`, or `--mode all` |
| CTL/NuSMV model construction | `checker/story_checker/smv.py`, generated `story_model.smv` |
| Counterexample trace | `trace` field in `story_report.json`; flat files in `traces/` |
| `ReplayHarness` adapter | `StoryReplayHarness.cs` |
| Export schema validation | `checker/story_checker/schema.py`, generated `schema_report.json` |
| Duplicate triage | `root_causes`, `root_cause_key`, and `duplicate_of` fields in reports |

## Demo Slice

The Unity prototype chapter contains:

- 16 story states
- 10 assets/flags
- 5 quests
- 20 guarded transitions
- 1 mandatory story state, `M7_Boss`, requiring `SniperRifle`

Seeded issues in the current slice:

- Hard lock: `CityHub -> DeadEndDock` has no route back to completion.
- Soft lock: `CityHub -> LongRecovery_1` forces a recovery path longer than the configured threshold.
- Disposable-critical resource: `CityHub -> M5_BlackMarket` can remove the unique `SniperRifle` after its one-time support quest is exhausted.
- Shortcut: `CityHub -> M7_Boss` bypasses the `SniperRifle` prerequisite.
- DSL invariant violation: `BossPrereqsMet` catches entry into `M7_Boss` without `SniperRifle`.
- DSL invariant violation: `NoFinalWhileHighlyWanted` catches finale completion while `WantedLevelGE4` is active.

## Running the Checker

From the repository root:

```powershell
python .\checker\check_story.py `
  .\examples\unity_chapter\story_graph.json `
  .\examples\unity_chapter\rules.dsl `
  --mode all `
  --theta 5 `
  --out .\examples\unity_chapter\story_report.json `
  --markdown .\examples\unity_chapter\story_report.md `
  --trace-dir .\examples\unity_chapter\traces `
  --primary-only `
  --emit-smv .\examples\unity_chapter\story_model.smv `
  --nusmv .\tools\NuSMV\NuSMV-2.7.1-win64\bin\NuSMV.exe `
  --nusmv-out .\examples\unity_chapter\nusmv_output.txt `
  --ground-truth .\examples\unity_chapter\ground_truth.json `
  --metrics-out .\examples\unity_chapter\metrics.json `
  --schema-report .\examples\unity_chapter\schema_report.json `
  --triage-csv .\examples\unity_chapter\triage.csv
```

Run the regression tests:

```powershell
python -m unittest discover -s .\checker\tests
```

Current verified result:

- 52 reachable abstract configurations
- 20 SC reported violations, including 2 recommended-asset advisories
- 11 SC root causes after grouping duplicate reports
- all four core defect classes present
- SC detects 6/6 seeded ground-truth entries
- SR, AQ, RA, and SC mode summaries are written into the aggregate report
- NuSMV 2.7.1 runs on the generated SMV model
- Unity 6000.3.9f1 compiles the demo and passes 4/4 PlayMode tests

## JSON Contract

The checker consumes the paper's engine-independent export shape:

```json
{
  "states": [{ "id": "M7_Boss", "kind": "mission", "tags": ["mandatory"] }],
  "assets": [{ "id": "SniperRifle", "category": "unique", "support_quests": ["Q_SideSniper"] }],
  "quests": [{ "id": "Q_SideSniper", "role": "side", "rewards": ["SniperRifle"] }],
  "mandatory_story_states": [{ "state": "M7_Boss", "required": ["SniperRifle"] }],
  "transitions": [
    {
      "id": "t_rooftop_boss",
      "from": "M6_Rooftop",
      "to": "M7_Boss",
      "pre": ["HasAsset(\"SniperRifle\")"],
      "eff": ["AddFlag(\"FinaleUnlocked\")"],
      "action_type": "enter_mission",
      "params": { "mission": "M7_Boss" }
    }
  ],
  "initial_state": "M1_Intro",
  "initial_assets": [],
  "completion_states": ["M8_Ending"]
}
```

`initial_assets` is an implementation extension. It keeps the exported model self-contained while preserving the paper's asset-summary abstraction.

## DSL MVP

Supported rule structure:

```text
RULE Name:
  WHEN EnterMission("StateId")
  REQUIRE HasAsset("AssetId")
  [WITHIN K STEPS]
```

Supported triggers:

- `EnterMission("state")`
- `EnterHub("state")`
- `CompleteMission("state")`
- `ReachState("state")`
- `ReachTaggedState("tag")`
- `EnterKind("kind")`

Supported predicates/effects:

- `HasAsset`, `HasFlag`
- `NotHasAsset`, `NotHasFlag`, `MissingAsset`
- `NextStateIs`
- `WantedLevelBelow`
- `AddAsset`, `AddFlag`
- `RemoveAsset`, `RemoveFlag`

The current bounded rule implementation checks whether the requirement is reachable within `K` exported transitions from each trigger configuration. A stricter CTL `AF <= K` interpretation can be added in the symbolic backend.

The demo now includes all four rules from the paper examples:

- P1 `BossPrereqsMet`
- P2 `HubObjectiveReachable`
- P3 `NoFinalWhileHighlyWanted`
- P4 `EscapeImmediatelyAfterHeist`

## Checker Algorithms

The checker projects configurations to assets referenced by:

- mandatory-state requirements
- DSL rules
- transition preconditions/effects
- quest rewards
- critical asset categories

Then it builds a reachable abstract configuration graph.

Implemented detectors:

- Hard locks: reachable configurations from which no completion state is reachable.
- Soft locks: reachable configurations whose shortest path to completion is greater than `theta`.
- Disposable-critical resources: transitions that remove a unique/critical asset irreversibly while a mandatory state requiring it remains reachable.
- Shortcuts: reachable mandatory states whose required asset set is not satisfied.
- Recommended-asset advisories: reachable mandatory states whose recommended assets are missing.
- DSL invariants, bounded reachability, and immediate successor ordering.

Implemented analysis modes:

- `SR`: structural reachability over story states, ignoring guards, assets, quests, and DSL rules.
- `AQ`: asset-agnostic reachability with quest diagnostics.
- `RA`: resource-aware reachability over abstract configurations, without DSL or mandatory-state contracts.
- `SC`: full symbolic continuity, combining resource-aware graph checks with mandatory requirements and DSL rules.

## SMV / NuSMV Export

`checker/story_checker/smv.py` emits a NuSMV model with:

- finite-domain `state`
- nondeterministic `action`
- boolean asset/flag predicates
- a `TRANS` relation derived from guarded transitions and effects
- CTL properties for unbounded DSL rules
- comments for bounded obligations that need the bounded-unrolling backend

`--nusmv path-to-nusmv` can be supplied together with `--emit-smv` to run an installed NuSMV binary and capture its output.

NuSMV 2.7.1 is installed locally under:

```text
tools/NuSMV/NuSMV-2.7.1-win64/bin/NuSMV.exe
```

The current generated NuSMV output shows:

- P1 `BossPrereqsMet`: false, counterexample generated
- P3 `NoFinalWhileHighlyWanted`: false, counterexample generated
- P4 `EscapeImmediatelyAfterHeist`: true

## Ground-Truth Metrics

`examples/unity_chapter/ground_truth.json` records the seeded issues. When passed through `--ground-truth`, the checker writes:

- detection totals
- per-class detection rates
- false positives
- duplicate reports
- unmatched ground-truth entries

When `--mode all` is used, metrics are computed separately for `SR`, `AQ`, `RA`, and `SC`.

## Schema Validation

`checker/story_checker/schema.py` validates the export contract before analysis. It checks:

- missing required top-level fields
- duplicate IDs
- unknown transition endpoints
- unknown mandatory-state assets
- unknown quest rewards and support quests
- malformed predicate/effect expressions
- rule triggers and requirements that reference unknown states or assets
- numeric abstractions such as `WantedLevelBelow(4)` represented by either `WantedLevelBelow4` or `WantedLevelGE4`

The checker aborts with exit code `2` when schema errors are present. Warnings remain non-blocking and are emitted into the report.

## Duplicate and Root-Cause Triage

Each violation now includes:

- `root_cause_key`
- `duplicate_of`

Reports also include a `root_causes` section. This keeps replay traces for individual configurations while making QA triage closer to the paper's duplicate-merge procedure.

## Recommended Assets

Mandatory states can declare both `required` and `recommended` assets. Missing required assets remain blocking defects. Missing recommended assets are emitted as `recommended_asset_missing` advisories with severity `info`; metrics count them separately from false positives.

## Unity Adapter Flow

In Unity:

1. Open `unity-demo` as a Unity project.
2. Run `Tools > Story Feasibility > Create Demo Chapter Assets`.
3. Select the generated `UnityPrototypeChapter` asset.
4. Run `Tools > Story Feasibility > Export Selected Story Graph`.
5. Run the checker on the exported JSON.
6. Attach `StoryRuntime` and `StoryReplayHarness` to a scene object.
7. Assign the generated chapter asset and a trace JSON from `examples/unity_chapter/traces`.
8. Run replay to confirm that the abstract trace maps to runtime transitions.

The current replay adapter executes transitions through stable test hooks rather than UI automation. This matches the lower-maintenance replay path described in the paper.

Unity validation was performed with Unity 6000.3.9f1:

- batch compile: exit code 0
- batch export: `unity-demo/Exported/story_graph.json`
- PlayMode tests: 4 passed, 0 failed

Unity 2022.3.20f1 is installed on this machine, but its local Package Manager binary fails before compilation because it cannot find its internal `server/app.js`; Unity 6000.3.9f1 was therefore used for validation.

Replay now writes runtime artifacts under `Application.persistentDataPath/StoryReplayArtifacts`:

- `<violation>_result.json`
- optional `<violation>_screenshot.png`

## Adoption and Maintenance Notes

The current prototype maps the paper's adoption-effort categories as follows:

| Activity | Current implementation | Review status |
| --- | --- | --- |
| StoryGraph extractor | Unity ScriptableObject exporter in `StoryGraphExporter.cs` | Implemented for demo metadata |
| DSL rules | `rules.dsl` with P1-P4 examples | Implemented |
| ReplayHarness hooks | `StoryRuntime.TryExecuteTransition` and `StoryReplayHarness` | Implemented with stable test hooks |
| ReplayHarness UI | Not implemented | Deliberately out of scope for this demo |
| Triage review | Markdown report, metrics JSON, root-cause grouping, CSV export | Implemented |

Maintenance-sensitive areas:

- content schema drift: update `StoryGraphExporter.cs` and schema validation rules
- new predicate functions: update `dsl.py`, `schema.py`, `smv.py`, and Unity `StoryPredicateEvaluator.cs`
- new replay action types: update trace generation and `StoryReplayHarness`
- new progression abstractions: add assets/flags to the export so analysis remains faithful

## Review Alignment

For section-by-section mapping from the paper to this implementation draft, see:

```text
docs/paper-traceability.md
```

The traceability matrix also lists the current review backlog, including bounded NuSMV unrolling, automated replay of every generated trace, timing aggregation, and the distinction between this compact demo and the larger paper evaluation dataset.
