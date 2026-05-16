# Tools

## NuSMV

NuSMV 2.7.1 for Windows x64 can be installed locally under:

```text
tools/NuSMV/NuSMV-2.7.1-win64/bin/NuSMV.exe
```

The local `tools/NuSMV/` directory is ignored by Git because it contains third-party binaries. In the working copy used to prepare this artefact, NuSMV was downloaded from the official NuSMV distribution site and checked against the official `.sha256sum` before extraction.

The checker command can run it with:

```powershell
--nusmv .\tools\NuSMV\NuSMV-2.7.1-win64\bin\NuSMV.exe
```

If NuSMV is not installed locally, run `verify.ps1 -SkipNuSMV` or install NuSMV at the path above before running the full verification script.
