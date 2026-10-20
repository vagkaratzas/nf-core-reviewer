# AGENTS.md

Source of truth for coding agents working in this repository.

## What this repo is

The **nf-core-reviewer** plugin: one skill, `vagkaratzas-review`, that reviews and scores nf-core/modules PRs (modules and subworkflows) the way vagkaratzas reviews them. It targets Claude Code and Codex, and is listed in the `vagkaratzas` marketplace (`vagkaratzas/nf-core-module-dev`, `.claude-plugin/marketplace.json`).

```
.claude-plugin/plugin.json           Claude Code manifest
.codex-plugin/plugin.json            Codex manifest
.version-bump.json                   files bump-version.sh keeps in sync
RELEASE-NOTES.md                     one section per release
scripts/bump-version.sh              version bump, drift check, audit
skills/vagkaratzas-review/
├── SKILL.md                         workflow and review format
├── rubric.md                        rules, severities, scoring (source of truth)
└── scripts/
    ├── review.py                    script rules (`check`) and scoring (`score`)
    └── test_review.py               unit tests
```

## Rules

- `rubric.md` is the only place severities live: `review.py score` parses its tables. Any change to a rule, severity, weight or the gate factor bumps the rubric version in its title (`# vagkaratzas-review rubric vN`), so scores stay comparable within a version. Weights and the gate factor also live in `review.py` (`WEIGHTS`, `GATE_FACTOR`): change both places together.
- A new `script` rule needs a check in `review.py` and a case in `test_review.py`. Before merging, run the checker over a whole nf-core/modules clone and read a sample of each rule's hits for false positives.
- `review.py` uses the Python standard library only.
- The reviewer never approves, and never posts without the user asking.
- The review footer (`review.py score`) reads the plugin version from `plugin.json` and the rubric version from `rubric.md`; never hardcode either elsewhere.

## Versioning

The plugin version and the rubric version are separate: a release can fix the script without changing any rule.

```bash
scripts/bump-version.sh --check    # report versions, detect drift
scripts/bump-version.sh 0.2.0      # bump both manifests, then audit
```

Add a `RELEASE-NOTES.md` section for every release. The marketplace entry (in nf-core-module-dev) has no version field on purpose, so nothing there needs bumping.

## Tests

```bash
python3 -B skills/vagkaratzas-review/scripts/test_review.py
```
