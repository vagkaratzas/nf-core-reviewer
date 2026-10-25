# Release Notes

## v0.6.0dev — [unreleased]

## v0.5.0 — [2026/10/25]

Rubric v4: scores are not comparable with rubric v3.

- New blocker M15: the module exposes every file input and output its tool or subcommand offers, optional ones included. The reviewer now checks the tool's manual or `--help` and names each missing file input or output
- New major E2: GPU-capable modules follow the nf-core GPU modules guide (dual containers chosen by `task.accelerator`, exact lowest `cuda-version` pin, CUDA build glob, CUDA version on the versions topic, a `gpu`-tagged `main.gpu.nf.test` with real and stub tests, and `nextflow.gpu.config` setting `accelerator = 1` and `maxForks = 1`). For GPU components, G2 needs both `confirm-pass-nf-test` and `confirm-pass-gpu`
- `review.py check` runs the test rules on every test file, so `main.gpu.nf.test` is checked too, and T3 asks for a stub test in each file. T7 reads every `tests/nextflow*.config`, including `nextflow.gpu.config` and older per-test configs that hardcode `ext.args`
- `review.py check` false positives: T8 no longer counts `main.gpu.nf.test` and its snapshot as local fixture files, and Y1 accepts `ontologies: []` on `type: directory` entries, which have no EDAM format

## v0.4.0 — [2026/10/24]

Rubric v3: scores are not comparable with rubric v2.

- E1 is `na` for modules without an `environment.yml`: their tool has no Conda package, so a custom container is the only option. These modules used to fail E1 as a blocker
- `review.py check`: T8 no longer counts a URL in a comment, such as a TODO linking a test-datasets issue, as hardcoded test data. T11 reads test `script` paths written from the repo root, instead of asking for nonsense tags like `bcl2fastq/tests/modules/nf-core/bcl2fastq`
- Reviews of several PRs can run at once: each PR is fetched into its own ref and its head commit checked. Parallel reviews used to overwrite each other's fetch and could review the wrong PR
- When a PR's CI never ran, only the `confirm-pass-*` and lint jobs count as CI (a green Graphite check does not), and a non-member author is asked to request an invitation in the nf-core Slack #github-invitations channel
- Local gates: when nf-test cannot download its plugins, they are copied from the main clone; `nf-core modules lint` is time-boxed and marked `na` if it hangs
- Posted reviews no longer leave rule IDs such as `(M12)` in the body

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
