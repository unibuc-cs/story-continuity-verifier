param(
    [string]$UnityPath = "",
    [switch]$SkipUnity,
    [switch]$SkipNuSMV,
    [switch]$CleanUnityCache
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = (Get-Location).Path
}

$UnityProject = Join-Path $Root "unity-demo"
$UnityLogs = Join-Path $UnityProject "Logs"
$UnityResults = Join-Path $UnityProject "TestResults"
$NuSMV = Join-Path $Root "tools\NuSMV\NuSMV-2.7.1-win64\bin\NuSMV.exe"

function Write-Step {
    param([string]$Name)
    Write-Host ""
    Write-Host "== $Name =="
}

function Invoke-Checked {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory = $Root
    )

    Write-Step $Name
    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        $exitCode = if ($global:LASTEXITCODE -ne $null) { $global:LASTEXITCODE } else { 0 }
        if ($exitCode -ne 0) {
            throw "$Name failed with exit code $exitCode."
        }
    }
    finally {
        Pop-Location
    }
}

function ConvertTo-ArgumentLine {
    param([string[]]$Arguments)

    $quoted = foreach ($argument in $Arguments) {
        if ($argument -match '[\s"]') {
            '"' + ($argument -replace '"', '\"') + '"'
        }
        else {
            $argument
        }
    }

    return ($quoted -join " ")
}

function Invoke-UnityChecked {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$LogPath,
        [string]$SuccessPattern = ""
    )

    Write-Step $Name
    if (Test-Path -LiteralPath $LogPath) {
        Remove-Item -LiteralPath $LogPath -Force -ErrorAction Stop
    }

    $argumentLine = ConvertTo-ArgumentLine $Arguments
    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $argumentLine `
        -WorkingDirectory $Root `
        -Wait `
        -PassThru

    if ($process.ExitCode -ne 0) {
        throw "$Name failed with process exit code $($process.ExitCode). See $LogPath"
    }

    Assert-UnityLogHealthy $LogPath $SuccessPattern
}

function Assert-UnityLogHealthy {
    param(
        [string]$LogPath,
        [string]$SuccessPattern = ""
    )

    if (-not (Test-Path -LiteralPath $LogPath)) {
        throw "Unity log was not written: $LogPath"
    }

    $logText = Get-Content -LiteralPath $LogPath -Raw
    $failurePatterns = @(
        "fatal error",
        "Aborting batchmode",
        "Application will terminate with return code 1",
        "Scripts have compiler errors",
        "Compilation failed"
    )

    foreach ($pattern in $failurePatterns) {
        if ($logText.IndexOf($pattern, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            throw "Unity reported '$pattern' in $LogPath"
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($SuccessPattern) -and
        $logText.IndexOf($SuccessPattern, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "Unity log did not contain expected marker '$SuccessPattern': $LogPath"
    }
}

function Assert-UnityPlayModePassed {
    param([string]$ResultsPath)

    if (-not (Test-Path -LiteralPath $ResultsPath)) {
        throw "Unity PlayMode result file was not written: $ResultsPath"
    }

    [xml]$results = Get-Content -LiteralPath $ResultsPath -Raw
    $run = $results.'test-run'
    if ($run.result -ne "Passed" -or [int]$run.failed -ne 0) {
        throw "Unity PlayMode tests failed: result=$($run.result), passed=$($run.passed), failed=$($run.failed)"
    }
}

function Get-UnityExecutable {
    if (-not [string]::IsNullOrWhiteSpace($UnityPath)) {
        if (-not (Test-Path -LiteralPath $UnityPath)) {
            throw "UnityPath does not exist: $UnityPath"
        }
        return (Resolve-Path -LiteralPath $UnityPath).Path
    }

    $candidates = New-Object System.Collections.Generic.List[string]
    $projectVersionPath = Join-Path $UnityProject "ProjectSettings\ProjectVersion.txt"
    if (Test-Path -LiteralPath $projectVersionPath) {
        $versionLine = Get-Content -LiteralPath $projectVersionPath |
            Where-Object { $_ -match '^m_EditorVersion:\s*(.+)$' } |
            Select-Object -First 1
        if ($versionLine -match '^m_EditorVersion:\s*(.+)$') {
            $version = $Matches[1].Trim()
            $candidates.Add((Join-Path $env:ProgramFiles "Unity\Hub\Editor\$version\Editor\Unity.exe"))
        }
    }

    $candidates.Add((Join-Path $env:ProgramFiles "Unity\Hub\Editor\6000.3.9f1\Editor\Unity.exe"))

    $hubRoot = Join-Path $env:ProgramFiles "Unity\Hub\Editor"
    if (Test-Path -LiteralPath $hubRoot) {
        Get-ChildItem -LiteralPath $hubRoot -Directory |
            Sort-Object Name -Descending |
            ForEach-Object { $candidates.Add((Join-Path $_.FullName "Editor\Unity.exe")) }
    }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "Unity executable not found. Pass -UnityPath or use -SkipUnity."
}

function Remove-UnityGeneratedCaches {
    $workspace = (Resolve-Path -LiteralPath $Root).Path
    $targets = @(
        (Join-Path $UnityProject "Library"),
        (Join-Path $UnityProject "Temp"),
        (Join-Path $UnityProject "UserSettings")
    )

    foreach ($target in $targets) {
        if (-not (Test-Path -LiteralPath $target)) {
            continue
        }
        $resolved = (Resolve-Path -LiteralPath $target).Path
        if (-not $resolved.StartsWith($workspace, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove outside workspace: $resolved"
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction Stop
    }
}

New-Item -ItemType Directory -Force -Path $UnityLogs | Out-Null
New-Item -ItemType Directory -Force -Path $UnityResults | Out-Null

try {
    Invoke-Checked "Python compile" "python" @("-m", "compileall", ".\checker")

    Invoke-Checked "Python unit tests" "python" @("-m", "unittest", "discover", "-s", ".\checker\tests")

    $checkerArgs = @(
        ".\checker\check_story.py",
        ".\examples\unity_chapter\story_graph.json",
        ".\examples\unity_chapter\rules.dsl",
        "--mode", "all",
        "--theta", "5",
        "--out", ".\examples\unity_chapter\story_report.json",
        "--markdown", ".\examples\unity_chapter\story_report.md",
        "--trace-dir", ".\examples\unity_chapter\traces",
        "--primary-only",
        "--emit-smv", ".\examples\unity_chapter\story_model.smv",
        "--ground-truth", ".\examples\unity_chapter\ground_truth.json",
        "--metrics-out", ".\examples\unity_chapter\metrics.json",
        "--schema-report", ".\examples\unity_chapter\schema_report.json",
        "--triage-csv", ".\examples\unity_chapter\triage.csv"
    )

    if (-not $SkipNuSMV) {
        if (-not (Test-Path -LiteralPath $NuSMV)) {
            throw "NuSMV executable not found at $NuSMV. Reinstall it or rerun with -SkipNuSMV."
        }
        $checkerArgs += @("--nusmv", ".\tools\NuSMV\NuSMV-2.7.1-win64\bin\NuSMV.exe")
        $checkerArgs += @("--nusmv-out", ".\examples\unity_chapter\nusmv_output.txt")
    }

    Invoke-Checked "Checker pipeline on sample graph" "python" $checkerArgs

    if (-not $SkipUnity) {
        $unityExe = Get-UnityExecutable
        Write-Host ""
        Write-Host "Using Unity: $unityExe"

        $compileLog = Join-Path $UnityLogs "compile-unity6000.log"
        $playmodeLog = Join-Path $UnityLogs "playmode-tests-unity6000.log"
        $playmodeResults = Join-Path $UnityResults "playmode-results.xml"
        $exportLog = Join-Path $UnityLogs "batch-export-unity6000.log"
        $exportedGraph = Join-Path $UnityProject "Exported\story_graph.json"

        Invoke-UnityChecked "Unity batch compile" $unityExe @(
            "-batchmode",
            "-quit",
            "-projectPath", $UnityProject,
            "-logFile", $compileLog
        ) $compileLog "Exiting batchmode successfully now"

        Invoke-UnityChecked "Unity PlayMode tests" $unityExe @(
            "-batchmode",
            "-projectPath", $UnityProject,
            "-runTests",
            "-testPlatform", "PlayMode",
            "-testResults", $playmodeResults,
            "-logFile", $playmodeLog
        ) $playmodeLog "Test run completed. Exiting with code 0"
        Assert-UnityPlayModePassed $playmodeResults

        Invoke-UnityChecked "Unity batch export" $unityExe @(
            "-batchmode",
            "-quit",
            "-projectPath", $UnityProject,
            "-executeMethod", "StoryFeasibilityEditor.DemoChapterFactory.ExportDemoChapterForBatch",
            "-logFile", $exportLog
        ) $exportLog "Batch-exported demo story graph"
        if (-not (Test-Path -LiteralPath $exportedGraph)) {
            throw "Unity batch export did not write $exportedGraph"
        }

        Invoke-Checked "Checker pipeline on Unity export" "python" @(
            ".\checker\check_story.py",
            ".\unity-demo\Exported\story_graph.json",
            ".\examples\unity_chapter\rules.dsl",
            "--mode", "all",
            "--theta", "5",
            "--out", ".\unity-demo\Exported\story_report.json",
            "--markdown", ".\unity-demo\Exported\story_report.md",
            "--primary-only",
            "--ground-truth", ".\examples\unity_chapter\ground_truth.json",
            "--metrics-out", ".\unity-demo\Exported\metrics.json",
            "--schema-report", ".\unity-demo\Exported\schema_report.json"
        )
    }
}
finally {
    if ($CleanUnityCache) {
        Write-Step "Clean Unity generated caches"
        Remove-UnityGeneratedCaches
    }
}

Write-Host ""
Write-Host "Verification completed successfully."
