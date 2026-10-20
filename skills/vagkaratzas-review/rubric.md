# vagkaratzas-review rubric v1

Bump the version in this title whenever a rule, severity or weight changes: scores are only comparable within one rubric version.

## Scoring

| Severity | Points | Review effect |
|----------|--------|---------------|
| gate | — | A failing gate multiplies the score by 0.4 |
| blocker | 3 | Fails → REQUEST_CHANGES |
| major | 2 | Fails → REQUEST_CHANGES |
| minor | 1 | Comment only |
| nit | 0 | Comment only, no score impact |

`score = 10 × points of passed rules ÷ points of applicable rules`, two decimals, ×0.4 when any gate fails. A column with no applicable rules scores 10.00.

Every rule gets two verdicts (`pass`, `fail` or `na`):

- **Diff**: judge only what the PR adds or changes. The rule is `na` when the PR touches nothing it governs (a test-only PR gets `na` for E1).
- **Overall**: judge the whole component as it stands after the PR.

Gates get the same verdict in both columns. A gate that could not be run is `na`, never `pass`.

**Check** says who decides: `script` = `scripts/review.py check` (its verdict stands; overturn a hit only as a false positive, with the reason written in the review), `judgment` = read the code, `command` = run it.

## Gates

| ID | Severity | Check | Rule |
|----|----------|-------|------|
| G1 | gate | command | `nf-core modules lint <tool/sub>` (or `nf-core subworkflows lint <name>`) reports no failures. Warnings are fine. |
| G2 | gate | command | `nf-test test <component>/main.nf --related-tests --follow-dependencies --profile=+singularity` passes with the committed snapshots: the component's own tests and every caller's. |
| G3 | gate | command | `nextflow lint` (strict syntax) reports no errors on the component's `main.nf` and `*.config` files. |

## Containers and environment

| ID | Severity | Check | Rule |
|----|----------|-------|------|
| E1 | blocker | script | Containers are Seqera Wave builds from `nf-core modules containers create`: the directive points at `community-cr-prod.seqera.io` / `community.wave.seqera.io`, `meta.yml` has a `containers:` block, `.conda-lock/` holds the lock files. No `quay.io/biocontainers` or `depot.galaxyproject.org`. A version bump on a legacy module must port it. |

## main.nf

| ID | Severity | Check | Rule |
|----|----------|-------|------|
| M1 | blocker | script | Versions are `topic: versions` tuples with `eval(...)` (or `val('x.y.z')` under the standard `// WARN: Version information not provided by tool on CLI` comment). No `versions.yml` heredoc, except template modules. |
| M2 | major | script | Every package in `environment.yml` has its own `versions_<tool>` emit. `python` always counts. Generic utilities (`pip`, `gzip`, `pigz`, `coreutils`, `procps-ng`, `gawk`, `sed`, `grep`, `tar`, `bzip2`, `findutils`, `unzip`) are optional. |
| M3 | minor | judgment | Emitted versions are bare (`1.2.3`): no `v` prefix, tool name or hash. Check the snapshot. |
| M4 | major | judgment | One tuple per sample's files (`tuple val(meta), path(reads), path(index)`). Shared reference data (databases, indexes, genomes) gets its own `tuple val(meta2), path(db)`. Separate channels only where a tuple is impossible. |
| M5 | major | judgment | No `val` input that could be a meta field or an `ext.args` flag. A mode `val` is allowed only when the tool has no default for it and fails without it (flye: one of `--nano-raw`, `--pacbio-hifi`, ... is required). When the tool falls back to a default mode (myloasm), the mode goes through `ext.args`. Modes that need different inputs or outputs belong in separate modules. |
| M6 | major | judgment | No hardcoded tool arguments or thread counts: `task.cpus`, `task.ext.args`, `args2`... Every file input comes through an input channel, never through `ext.args`. |
| M7 | minor | script | Forced redirection `2>\|`, never plain `2>` (nf-core sets noclobber). |
| M8 | major | judgment | Output paths are `"${prefix}.ext"` whenever the name is predictable. Globs only when the tool's naming cannot be predicted. |
| M9 | blocker | judgment | No output or intermediate file can take the name of a staged input under the default prefix (it truncates the upstream file through the symlink). |
| M10 | minor | judgment | Interpolated paths and values that may contain spaces are quoted. |
| M11 | minor | script | Exactly one resource label, from the seven standard ones. |
| M12 | major | judgment | The stub creates exactly what a real run creates for the same inputs: names, input-dependent branches, cardinality, optional outputs. Gzipped outputs via `echo "" \| gzip > x.gz`, never `touch x.gz`. |
| M13 | minor | judgment | Inline scripts over ~20 lines move to `templates/`. |
| M14 | major | judgment | A module-root `nextflow.config` exists only when the module cannot run correctly without it, and the PR says why. Present without need and needed but missing both fail. |

## Tests

| ID | Severity | Check | Rule |
|----|----------|-------|------|
| T1 | blocker | script | Every test, stub included, asserts `snapshot(sanitizeOutput(process.out ...))` (`workflow.out` for subworkflows): `sanitizeOutput` inside `snapshot(...)`, never raw `.out`, no separate versions assertion. |
| T2 | major | judgment | `unstableKeys` lists only channels whose content truly changes between runs, and each exempted channel gets the strongest stable check back in the same `snapshot(...)`: line count, else `.contains()` on a line the tool always writes. Hand-picking channels instead of `unstableKeys` fails. |
| T3 | blocker | script | At least one `options "-stub"` test. |
| T4 | major | script | `assert process.success` sits inside `assertAll(...)` with the snapshot. |
| T5 | major | script | Test names follow `<organism> - <inputs> - <outputs/config>`, e.g. `sarscov2 - [ cram, crai ] - fasta - fai`. Stub tests end with ` - stub`. |
| T6 | nit | script | Sentence-style names (`Should search ... and return ...`) are nf-core-valid but not preferred; grouped inputs are written `[ bam, bai ]`, with spaces. |
| T7 | major | script | Modules: `tests/nextflow.config` takes arguments as `ext.args = { params.module_args ?: '' }` (fixed flags may precede it), and tests that need arguments set `params { module_args = '...' }` in their `when` block. |
| T8 | blocker | script | Test data only from the `modules` branch of nf-core/test-datasets, through `params.modules_testdata_base_path` with `checkIfExists: true`, or tiny files generated in Groovy inside the test. No local fixture files, `projectDir` paths, hardcoded URLs or pipeline-branch data. |
| T9 | major | script | No empty-file md5 (`d41d8cd98f00b204e9800998ecf8427e`) in non-stub snapshots. |
| T10 | major | script | Every non-stub snapshot differs from every other one, so each test can fail when its feature is removed. Every input branch (compressed and plain, each format, optional inputs given and empty) is covered: judge that part. |
| T11 | major | script | Tags: `modules`, `modules_nfcore`, `<tool>`, `<tool>/<sub>` (subworkflows: `subworkflows`, `subworkflows_nfcore`, `subworkflows/<name>`), plus `<tool>` and `<tool>/<sub>` for every component run in a `setup` block or included by the subworkflow. |
| T12 | minor | judgment | A file-level `setup` block only when every test needs it; otherwise it goes inside each test that does. |
| T13 | minor | judgment | The smallest test data that still gives a meaningful result (sarscov2 first). |

## meta.yml

| ID | Severity | Check | Rule |
|----|----------|-------|------|
| Y1 | minor | script | Every file entry has EDAM `ontologies`, one per format its `pattern` accepts, each URL followed by its format name comment (`# FASTQ`). `ontologies: []` only when no term exists. |
| Y2 | minor | judgment | `keywords` cover research domain, data type and function, not only the tool name. Multi-tool modules add `multi-tool`. |
| Y3 | minor | script | `doi` is omitted when there is none (never `""` or `null`). Every tool has `identifier` (`""` when not on bio.tools). |
| Y4 | minor | script | Every tool has an `args_id` matching its `$args` variable. |
| Y5 | minor | judgment | Descriptions are one short line. Optional inputs and outputs say "Optional". |

## Subworkflows

| ID | Severity | Check | Rule |
|----|----------|-------|------|
| S1 | major | script | `meta.yml` `components:` lists every included module and subworkflow. |

## General

| ID | Severity | Check | Rule |
|----|----------|-------|------|
| C1 | minor | judgment | Comments only explain why, in as few words as possible. A comment that restates the code fails. |
| C2 | minor | script | Lowercase `channel` (`Channel` is the class) and named closure parameters, never the implicit `it`. |
