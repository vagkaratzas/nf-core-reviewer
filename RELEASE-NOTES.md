# Release Notes

## v0.3.0 — [2026/10/20]

Rubric v2: scores are not comparable with rubric v1.

- T4 now follows the nf-core template: a bare `assert process.success` (or `workflow.success`) comes before `assertAll(...)`, which holds the snapshot. Rubric v1 required the opposite. T4 is now a nit (0 points) instead of a major
- `review.py check` matches `assertAll (` written with a space; T4 used to fail every test written that way

## v0.2.0 — [2026/10/20]

- PR reviews read G1 (nf-core lint) and G2 (nf-test) from the PR's CI checks instead of running them locally. CI covers the conda, docker and singularity profiles; pending or missing checks, infrastructure failures and components skipped on every profile in `.github/skip_nf_test.json` fall back to a local run or `na`
- G3 (strict `nextflow lint`) still runs locally, since it takes seconds and CI's pre-commit hook may not be as strict
- Local-branch reviews run all three gates locally, as before

## v0.1.0 — [2026/10/20]

First release, for calibration: rubric v1 is not frozen yet.

- `vagkaratzas-review` skill: reviews and scores nf-core/modules PRs (modules and subworkflows), or a local branch, against rubric v1: 3 gates (nf-core lint, nf-test with callers, strict `nextflow lint`) and 36 rules worth 3 (blocker), 2 (major), 1 (minor) or 0 (nit) points
- Two scores out of 10: Diff (what the PR changed) and Overall (the whole component). A failing gate multiplies the score by 0.4
- Review drafted to `~/nf-core-reviews/<name>.md` with inline comments and suggestion blocks; posted with `gh` only on request, never as an approval
- `review.py check` runs the 20 script rules; `review.py score` computes scores, the review event and the footer from the rubric
- Gates run with the Nextflow version nf-core/modules CI pins (`NXF_VER`)
