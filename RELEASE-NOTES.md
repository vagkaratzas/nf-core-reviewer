# Release Notes

## v0.1.0 — [2026/10/20]

First release, for calibration: rubric v1 is not frozen yet.

- `vagkaratzas-review` skill: reviews and scores nf-core/modules PRs (modules and subworkflows), or a local branch, against rubric v1: 3 gates (nf-core lint, nf-test with callers, strict `nextflow lint`) and 36 rules worth 3 (blocker), 2 (major), 1 (minor) or 0 (nit) points
- Two scores out of 10: Diff (what the PR changed) and Overall (the whole component). A failing gate multiplies the score by 0.4
- Review drafted to `~/nf-core-reviews/<name>.md` with inline comments and suggestion blocks; posted with `gh` only on request, never as an approval
- `review.py check` runs the 20 script rules; `review.py score` computes scores, the review event and the footer from the rubric
- Gates run with the Nextflow version nf-core/modules CI pins (`NXF_VER`)
