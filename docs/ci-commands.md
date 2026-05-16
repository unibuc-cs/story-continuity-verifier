# Verification Commands

These commands reproduce the current validation state.

## One-Command Verification

```powershell
.\verify.ps1
```

Useful switches:

- `-SkipUnity`: run only Python, checker, metrics, and NuSMV validation.
- `-SkipNuSMV`: run without the local NuSMV executable.
- `-UnityPath <path>`: override Unity auto-detection.
- `-CleanUnityCache`: remove Unity `Library`, `Temp`, and `UserSettings` after verification.

## Python

```powershell
python -m unittest discover -s .\checker\tests
```

## Checker Pipeline

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

## Unity Compile

```powershell
$projectPath = (Resolve-Path .\unity-demo).Path
$logPath = Join-Path $projectPath 'Logs\compile-unity6000.log'
& 'C:\Program Files\Unity\Hub\Editor\6000.3.9f1\Editor\Unity.exe' `
  -batchmode `
  -quit `
  -projectPath $projectPath `
  -logFile $logPath
```

## Unity PlayMode Tests

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

## Unity Batch Export

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

## Known Environment Note

Unity 2022.3.20f1 is installed, but its local `UnityPackageManager.exe` fails in this environment because it cannot find its internal `server/app.js`. Unity 6000.3.9f1 has a working Package Manager and was used for compile, batch export, and PlayMode tests.
