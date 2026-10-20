# nf-core-reviewer

Reviews nf-core/modules pull requests the way [@vagkaratzas](https://github.com/vagkaratzas) does, and scores them out of 10.

- **Two scores**: Diff (only what the PR changed) and Overall (the whole component, so the author sees what else could be fixed while the PR is open).
- **Rubric**: [`rubric.md`](skills/vagkaratzas-review/rubric.md), versioned. Lint, nf-test and strict `nextflow lint` are gates; the other rules are worth 3 (blocker), 2 (major), 1 (minor) or 0 (nit) points. A failing gate multiplies the score by 0.4.
- **Output**: a review draft at `~/nf-core-reviews/<name>.md`, with inline comments and suggestion blocks on the changed lines and a short TLDR body. It is posted with `gh` only on request, and never as an approval.

## Install

The `vagkaratzas` marketplace catalog lives in the [nf-core-module-dev](https://github.com/vagkaratzas/nf-core-module-dev) repo and lists both plugins, so you add that repo as the marketplace.

Claude Code:

```bash
claude plugin marketplace add vagkaratzas/nf-core-module-dev
claude plugin install nf-core-reviewer@vagkaratzas
```

Codex: `codex plugin marketplace add vagkaratzas/nf-core-module-dev`, then install `nf-core-reviewer` from `/plugins`.

## Use

- "Review nf-core/modules PR 1234"
- "Score the module on my current branch"
