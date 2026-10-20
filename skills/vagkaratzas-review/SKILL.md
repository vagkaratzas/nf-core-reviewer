---
name: vagkaratzas-review
description: Use when reviewing, scoring or evaluating an nf-core/modules pull request, or a module or subworkflow branch in a local nf-core/modules clone (including one an agent just built), the way vagkaratzas reviews them. Examples - "review nf-core/modules#1234", "score this module PR", "evaluate the new samtools/sort module".
---

# vagkaratzas-review

You review as a bot standing in for vagkaratzas. Every rule, severity and the scoring formula live in `rubric.md` next to this file. Read it in full before judging anything.

- **Never approve.** The event is `REQUEST_CHANGES` or `COMMENT`. Approving is always the human's call.
- **Script verdicts stand.** Overturn a `scripts/review.py check` hit only as a false positive, and say why in the review.
- **Never fake a gate.** A command you could not run is `na`, and the review says it was not run.
- **Draft first.** Write the review to a file. Post it only when the user asks.

## Inputs

- **PR mode**: an nf-core/modules PR number.
- **Local mode**: a branch or component path inside a local nf-core/modules clone.

Placeholders: `<modules_repo>` is the user's nf-core/modules clone (ask if unknown). `<skill_dir>` is this file's folder. `<work>` is a scratch folder outside the clone: the session scratchpad when the platform has one, else `${TMPDIR:-/tmp}/vagkaratzas-review`.

## Workflow

1. **Get the code without touching the user's checkout.**
   - PR mode:
     ```bash
     gh pr view <N> -R nf-core/modules --json title,author,body,files
     gh pr diff <N> -R nf-core/modules > <work>/pr-<N>.diff
     git -C <modules_repo> fetch https://github.com/nf-core/modules.git pull/<N>/head
     git -C <modules_repo> worktree add --detach <work>/pr-<N> FETCH_HEAD
     ```
     Review inside `<work>/pr-<N>`. Never `gh pr checkout` in `<modules_repo>`.
   - Local mode:
     ```bash
     git -C <modules_repo> fetch https://github.com/nf-core/modules.git master
     git -C <modules_repo> diff FETCH_HEAD...HEAD > <work>/<branch>.diff
     ```
   - The components are the changed `modules/nf-core/<tool>[/<sub>]` and `subworkflows/nf-core/<name>` folders in the diff.
2. **Run the gates** (G1–G3 in the rubric) from the review checkout, once per component. Use the tools on the user's PATH. If they are missing, look in the conda base env before giving up. Run G2 and G3 with the Nextflow version CI pins, because results differ between versions. Set it in the same command, since shell state may not persist between commands:
   ```bash
   NXF_VER=$(grep -oP 'NXF_VER:\s*"\K[^"]+' .github/workflows/nf-test.yml) nf-test test ...
   ```
   Run nf-test with `--profile=+singularity`, and never with `--update-snapshot`: a snapshot mismatch is a failure.
3. **Run the script rules** once per component:
   ```bash
   python3 <skill_dir>/scripts/review.py check <component_dir> --diff <work>/<diff file>
   ```
   Each row is `rule  PASS|FAIL|NA  path:line  diff|overall  message`. `diff` means the hit is on a line the PR added; `overall` means it was already there or on an untouched line.
4. **Judge every rule twice.** The Diff column covers what the PR changed; the Overall column covers the whole component. Read `main.nf`, `environment.yml`, the tests, the snapshot, `meta.yml` and the PR body for the judgment rules. When there are several components, a rule fails if it fails in any of them.
5. **Score.** Write `~/nf-core-reviews/<name>.verdicts.tsv` with one `rule<TAB>diff<TAB>overall` row per rubric rule. Use `modules-pr-<N>` as `<name>` in PR mode and the branch name in local mode. Then run:
   ```bash
   python3 <skill_dir>/scripts/review.py score ~/nf-core-reviews/<name>.verdicts.tsv
   ```
   Use its scores, event, approval line and footer exactly as printed.
6. **Write the review** to `~/nf-core-reviews/<name>.md` in the format below, show it to the user, and stop.
7. **Clean up** the worktree with `git -C <modules_repo> worktree remove <work>/pr-<N>`.

## Review file

```markdown
# nf-core/modules#<N>: <PR title>

event: <REQUEST_CHANGES|COMMENT>
diff_score: <x.yz>
overall_score: <x.yz>

## Inline comments

### <path>:<line>
<comment>

### <path>:<start>-<end>
<comment with a suggestion block>

## Review body

<TLDR: 1-3 bullets, the blocking points first>

<if the score printed "approval line: yes": Approval should be on its way soon.>

<if there are Overall-only findings: "While you are here (not blocking):" then one line per finding, `path:line` and the issue>

<if a gate was not run: "Not run: G2 (<reason>)">

Diff <x.yz>/10 · Overall <x.yz>/10
<footer printed by `review.py score`> · <your model ID, or "unknown">
```

**Inline comments.** Every failed finding on a line the PR added gets its own comment on that line or range. GitHub only accepts inline comments on lines inside the diff, so findings on untouched lines go in the body's "While you are here" list instead. Each comment:

- One issue, in one or two short sentences: what is wrong and what to do.
- A ```` ```suggestion ```` block holding the exact replacement lines whenever the fix is mechanical.
- The rule ID in parentheses at the end, e.g. `(T1)`. It stays in the `.md` file for traceability, and is removed when posting.

**The body** is a TLDR. It never repeats the inline comments one by one.

## Posting (only when the user asks)

1. Confirm `gh` is available and authenticated.
2. Rebuild the payload from the `.md` file as the user left it, because they may have edited it. Strip the trailing rule IDs (`(T1)`) from every comment, since PR authors don't know the rubric. Write it to `<work>/review-<N>.json`:
   ```json
   {"event": "COMMENT", "body": "<review body>",
    "comments": [{"path": "<path>", "line": 12, "side": "RIGHT", "body": "<comment>"},
                 {"path": "<path>", "start_line": 30, "line": 34, "start_side": "RIGHT", "side": "RIGHT", "body": "<comment>"}]}
   ```
3. If the PR author is the authenticated `gh` user, use `COMMENT`: GitHub refuses `REQUEST_CHANGES` on your own PR.
4. Post it:
   ```bash
   gh api repos/nf-core/modules/pulls/<N>/reviews --method POST --input <work>/review-<N>.json
   ```
   Report the review URL from the response.
