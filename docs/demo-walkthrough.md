# Reproducibility Walkthrough

This walkthrough exercises the Unity story-continuity artefact end to end.

## 1. Generate Unity Content and Export the Graph

Unity 6000.3.9f1 was used for validation on the preparation machine. Unity 2022.3.20f1 is installed there as well, but its local Package Manager binary fails in that environment before compilation.

```powershell
$projectPath = (Resolve-Path .\unity-demo).Path
$logPath = Join-Path $projectPath 'Logs\batch-export-unity6000.log'
& 'C:\Program Files\Unity\Hub\Editor\6000.3.9f1\Editor\Unity.exe' `
  -batchmode `
  -quit `
  -projectPath $projectPath `
  -executeMethod StoryFeasibilityEditor.DemoChapterFactory.ExportDemoChapterForBatch `
  -logFile $logPath
```

Expected output:

- `unity-demo/Exported/story_graph.json`
- log contains `Batch-exported demo story graph`

The exported graph should produce the same checker behavior as `examples/unity_chapter/story_graph.json`:

- 52 SC configurations
- 20 SC reports
- 11 SC root causes

## 2. Run Checker, NuSMV, Metrics, and Triage Export

NuSMV 2.7.1 can be installed locally at:

```text
tools/NuSMV/NuSMV-2.7.1-win64/bin/NuSMV.exe
```

Run the full checker pipeline:

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

Expected result:

- `SC: 6/6` ground-truth entries detected
- schema validation has 0 errors and 0 warnings
- `story_report.md` lists root causes and primary SC reports
- `traces/` contains one trace per primary root cause
- `nusmv_output.txt` contains false CTL properties for the seeded P1/P3 defects and true P4 ordering

## 3. Run Python Tests

```powershell
python -m unittest discover -s .\checker\tests
```

Expected result:

```text
Ran 5 tests
OK
```

## 4. Run Unity PlayMode Tests

```powershell
$projectPath = (Resolve-Path .\unity-demo).Path
$logPath = Join-Path $projectPath 'Logs\playmode-tests-unity6000.log'
$resultsPath = Join-Path $projectPath 'TestResults\playmode-results.xml'
& 'C:\Program Files\Unity\Hub\Editor\6000.3.9f1\Editor\Unity.exe' `
  -batchmode `
  -projectPath $projectPath `
  -runTests `
  -testPlatform PlayMode `
  -testResults $resultsPath `
  -logFile $logPath
```

Expected result:

- `unity-demo/TestResults/playmode-results.xml`
- 4 passed, 0 failed

The tests cover:

- initial-state reset
- valid transition effects
- failed precondition handling
- replay harness execution from trace JSON

## Seeded Defects

| Defect | Demo source | Expected checker signal |
| --- | --- | --- |
| Hard lock | `CityHub -> DeadEndDock` | `hard_lock` |
| Soft lock | `CityHub -> LongRecovery_1` | `soft_lock` |
| Disposable critical resource | `CityHub -> M5_BlackMarket` removes `SniperRifle` | `disposable_critical_resource` |
| Shortcut | `CityHub -> M7_Boss` bypasses `SniperRifle` | `shortcut`, `BossPrereqsMet` |
| High wanted finale | `WantedLevelGE4` remains active at ending | `NoFinalWhileHighlyWanted` |
| Missing recommended asset | boss reached without `GateOpened` | `recommended_asset_missing` advisory |
