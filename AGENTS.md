# AGENTS.md

Source of truth for coding agents working in this repository.

## What this repo is

The **nf-core-reviewer** plugin: one skill, `vagkaratzas-review`, that reviews and scores nf-core/modules PRs (modules and subworkflows) the way vagkaratzas reviews them. It targets Claude Code and Codex, and is listed in the `vagkaratzas` marketplace (`vagkaratzas/nf-core-module-dev`, `.claude-plugin/marketplace.json`).

```
.claude-plugin/plugin.json           Claude Code manifest
.codex-plugin/plugin.json            Codex manifest
skills/vagkaratzas-review/
├── SKILL.md                         workflow and review format
├── rubric.md                        rules, severities, scoring (source of truth)
└── scripts/
    ├── review.py                    script rules (`check`) and scoring (`score`)
    └── test_review.py               unit tests
```

## Rules

- `rubric.md` is the only place severities live: `review.py score` parses its tables. Any change to a rule, severity, weight or the gate factor bumps the rubric version in its title and in SKILL.md's footer line, so scores stay comparable within a version.
- A new `script` rule needs a check in `review.py` and a case in `test_review.py`. Before merging, run the checker over a whole nf-core/modules clone and read a sample of each rule's hits for false positives.
- `review.py` uses the Python standard library only.
- The reviewer never approves, and never posts without the user asking.
- Keep the plugin version in sync in `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`.

## Tests

```bash
python3 -B skills/vagkaratzas-review/scripts/test_review.py
```
