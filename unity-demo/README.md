# Story Feasibility Unity Demo

This folder is a minimal Unity project shell for the story-continuity prototype.

Validated editor: Unity 6000.3.9f1.

Use these editor menus:

1. `Tools > Story Feasibility > Create Demo Chapter Assets`
2. Select the generated `UnityPrototypeChapter` asset.
3. `Tools > Story Feasibility > Export Selected Story Graph`

The exported JSON follows the checker schema used by `examples/unity_chapter/story_graph.json`.
Attach `StoryRuntime` and `StoryReplayHarness` to a scene object to replay a trace exported from the checker report.

`StoryReplayHarness` writes replay artifacts to `Application.persistentDataPath/StoryReplayArtifacts` when artifact writing is enabled. Screenshot capture can be enabled on the harness component.

Batch export:

```powershell
$projectPath = (Resolve-Path .\unity-demo).Path
& 'C:\Program Files\Unity\Hub\Editor\6000.3.9f1\Editor\Unity.exe' `
  -batchmode `
  -quit `
  -projectPath $projectPath `
  -executeMethod StoryFeasibilityEditor.DemoChapterFactory.ExportDemoChapterForBatch
```

PlayMode tests:

```powershell
$projectPath = (Resolve-Path .\unity-demo).Path
& 'C:\Program Files\Unity\Hub\Editor\6000.3.9f1\Editor\Unity.exe' `
  -batchmode `
  -projectPath $projectPath `
  -runTests `
  -testPlatform PlayMode `
  -testResults (Join-Path $projectPath 'TestResults\playmode-results.xml')
```
