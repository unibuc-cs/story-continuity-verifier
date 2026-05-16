# Paper Artefacts

This folder contains the paper source and workflow figure assets.

## Files

| File | Purpose |
| --- | --- |
| `main.tex` | IEEE paper source. |
| `Flow.pdf` | Workflow figure used by the paper and root README. |
| `Flow.png` | PNG rendering of `Flow.pdf` for Markdown preview. |
| `Flow.drawio` | Editable workflow diagram source. |
| `Flow.drawio.pdf` | Draw.io PDF export. |

## Notes

The paper source references `Flow.pdf` with:

```tex
\includegraphics[width=\linewidth]{Flow.pdf}
```

Because `main.tex` and `Flow.pdf` now live in the same folder, this figure path remains valid when compiling from `docs/paper`.

The current repository does not include every external LaTeX support file referenced by `main.tex`, such as custom style inputs or bibliography files. The implementation review materials do not depend on compiling the paper locally.
