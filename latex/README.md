# RVT-Swarm LaTeX Paper

## Files

- `main.tex` — Full paper (IEEEtran journal format, ~8 pages)
- `references.bib` — BibTeX bibliography (20 entries)
- `fig_architecture.tex` — TikZ architecture diagram

## Compilation

```bash
cd latex/
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Or with `latexmk`:
```bash
latexmk -pdf main.tex
```

## Notes

- Results tables have placeholder `---` values.
  Populate after full training run on CUDA hardware.
- The architecture diagram is in TikZ (no external image files needed).
- Target format: IEEE Transactions on Robotics / RA-L / ICRA.
