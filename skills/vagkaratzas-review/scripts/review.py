#!/usr/bin/env python3
"""Deterministic checks and scoring for the vagkaratzas-review rubric.

  review.py check <component_dir> [--diff FILE] [--repo-root DIR]
      One TSV row per script rule: rule, PASS|FAIL|NA, path:line, diff|overall, message.
  review.py score <verdicts.tsv>
      verdicts.tsv rows: rule<TAB>diff<TAB>overall, each pass|fail|na, one row per rubric rule.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

RUBRIC = Path(__file__).resolve().parent.parent / "rubric.md"
PLUGIN_ROOT = Path(__file__).resolve().parents[3]
WEIGHTS = {"blocker": 3, "major": 2, "minor": 1, "nit": 0}
GATE_FACTOR = Decimal("0.4")
EMPTY_MD5 = "d41d8cd98f00b204e9800998ecf8427e"
# generic utilities that need no versions emit
VERSION_OPTIONAL = {"pip", "gzip", "pigz", "coreutils", "procps-ng", "gawk", "sed", "grep", "tar", "bzip2", "findutils", "unzip"}
LABELS = {"process_single", "process_low", "process_medium", "process_high", "process_long", "process_high_memory", "process_low_memory"}
STATUSES = {"pass", "fail", "na"}
STUB = re.compile(r"options\s+['\"]-stub")


def read(path):
    return path.read_text() if path.is_file() else ""


def numbered(text):
    return enumerate(text.splitlines(), 1)


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def rule_key(rule):
    return rule[0], int(rule[1:])


def parse_diff(text):
    """Changed files and the (file, line) pairs added on the new side of a unified diff."""
    files, added = set(), set()
    path, line, prev = None, 0, ""
    for row in text.splitlines():
        if row.startswith("+++ ") and prev.startswith("--- "):
            target = row[4:].split("\t")[0]
            path = None if target == "/dev/null" else target.removeprefix("b/")
            if path:
                files.add(path)
        elif row.startswith("@@"):
            line = int(re.search(r"\+(\d+)", row).group(1))
        elif path is None or row.startswith(("--- ", "diff ", "index ", "\\")):
            pass
        elif row.startswith("+"):
            added.add((path, line))
            line += 1
        elif not row.startswith("-"):
            line += 1
        prev = row
    return files, added


def norm(name):
    name = name.lower().replace("_", "-")
    for prefix in ("r-", "bioconductor-", "python-", "perl-"):
        name = name.removeprefix(prefix)
    return name.replace("-", "")


def env_packages(text):
    in_deps = False
    for n, t in numbered(text):
        if re.match(r"\S", t):
            in_deps = t.startswith("dependencies:")
            continue
        m = re.match(r"\s*-\s*['\"]?(?:[\w.-]+::)?([A-Za-z0-9_.+-]+)", t)
        if in_deps and m and not t.rstrip().endswith(":"):
            yield n, m.group(1).lower()


def top_level_block(text, key):
    m = re.search(rf"^{key}:.*$", text, re.M)
    if not m:
        return "", 0
    rest = text[m.end() + 1:]
    end = re.search(r"^\S", rest, re.M)
    return (rest[: end.start()] if end else rest), line_of(text, m.start())


def test_blocks(text):
    starts = list(re.finditer(r"\btest\(\s*(['\"])(.*?)\1", text))
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        yield m.group(2), m.start(), text[m.start():end]


class Checker:
    def __init__(self, comp_dir, root, diff_text=None):
        self.root, self.dir = root, comp_dir
        rel = comp_dir.relative_to(root).parts
        kinds = {("modules", "nf-core"): "module", ("subworkflows", "nf-core"): "subworkflow"}
        if rel[:2] not in kinds or len(rel) < 3:
            raise SystemExit(f"{comp_dir} is not under modules/nf-core/ or subworkflows/nf-core/")
        self.kind, self.name = kinds[rel[:2]], "/".join(rel[2:])
        self.files, self.added = parse_diff(diff_text) if diff_text is not None else (None, None)
        self.results = {}
        self.main = comp_dir / "main.nf"
        self.test = comp_dir / "tests" / "main.nf.test"
        self.meta = comp_dir / "meta.yml"
        self.main_text, self.test_text, self.meta_text = read(self.main), read(self.test), read(self.meta)

    def ok(self, *rules):
        for rule in rules:
            self.results.setdefault(rule, [])

    def na(self, rule, reason):
        self.results[rule] = reason

    def fail(self, rule, path, line, msg):
        self.results.setdefault(rule, []).append((path, line, msg))

    def rel(self, path):
        return Path(os.path.relpath(path, self.root)).as_posix()

    def scope(self, path, line):
        if self.files is None:
            return "-"
        rel = self.rel(path)
        if line:
            return "diff" if (rel, line) in self.added else "overall"
        return "diff" if any(f == rel or f.startswith(rel + "/") for f in self.files) else "overall"

    def component_tags(self, target):
        rel = Path(os.path.relpath(target, self.root)).parts
        if rel[:2] == ("modules", "nf-core") and len(rel) > 2:
            return {"/".join(rel[2:]), rel[2]}
        if rel[:2] == ("subworkflows", "nf-core") and len(rel) > 2:
            return {"subworkflows/" + "/".join(rel[2:])}
        return set()

    def includes(self):
        for m in re.finditer(r"include\s*\{[^}]*\}\s*from\s*['\"]([^'\"]+)['\"]", self.main_text):
            if m.group(1).startswith("plugin/"):
                continue
            p = Path(os.path.normpath(self.dir / m.group(1)))
            yield p.parent if p.name in ("main", "main.nf") else p

    def run(self):
        if self.kind == "module":
            self.check_containers()
            self.check_versions()
            self.check_redirect()
            self.check_label()
            self.check_meta()
            self.na("S1", "module")
        else:
            for rule in ("E1", "M1", "M2", "M7", "M11", "Y1", "Y3", "Y4"):
                self.na(rule, "subworkflow")
            self.check_components()
        self.check_strict_syntax()
        if self.test_text:
            self.check_tests()
        else:
            for rule in ("T1", "T3"):
                self.fail(rule, self.test, 0, "no tests/main.nf.test")
            for rule in ("T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11"):
                self.na(rule, "no tests/main.nf.test")
        return self.results

    # E1
    def check_containers(self):
        self.ok("E1")
        legacy = [n for n, t in numbered(self.main_text)
                  if re.search(r"quay\.io/biocontainers|depot\.galaxyproject\.org", t)]
        for n in legacy:
            self.fail("E1", self.main, n, "legacy biocontainers container; rebuild with `nf-core modules containers create`")
        if legacy:
            return
        if not re.search(r"community\.wave\.seqera\.io|community-cr-prod\.seqera\.io", self.main_text):
            self.fail("E1", self.main, 0, "container directive does not point at Seqera Wave")
        lock = self.dir / ".conda-lock"
        if not (lock.is_dir() and any(lock.iterdir())):
            self.fail("E1", lock, 0, "no .conda-lock/ lock files")
        if not re.search(r"^containers:", self.meta_text, re.M):
            self.fail("E1", self.meta, 0, "meta.yml has no containers: block")

    # M1, M2
    def check_versions(self):
        self.ok("M1", "M2")
        text = self.main_text
        if re.search(r"^\s*template\s+['\"]", text, re.M):
            self.na("M2", "template module: compare versions.yml keys with environment.yml by hand")
            return
        heredoc = next((n for n, t in numbered(text) if "END_VERSIONS" in t), 0)
        if heredoc:
            self.fail("M1", self.main, heredoc, "versions.yml heredoc; use a `topic: versions` eval tuple")
        elif not re.search(r"topic:\s*versions", text):
            self.fail("M1", self.main, 0, "no `topic: versions` output")
        tools = {norm(t) for t in re.findall(r"val\(\s*['\"]([^'\"$]+)['\"]\s*\)\s*,\s*e?val\(", text)}
        env = self.dir / "environment.yml"
        for n, pkg in env_packages(read(env)):
            p = norm(pkg)
            if pkg in VERSION_OPTIONAL or any(p == t or (min(len(p), len(t)) >= 3 and (p in t or t in p)) for t in tools):
                continue
            self.fail("M2", env, n, f"no versions emit for `{pkg}` (confirm the tool name)")

    # M7
    def check_redirect(self):
        self.ok("M7")
        for n, t in numbered(self.main_text):
            if not t.lstrip().startswith("//") and re.search(r"2>(?![|&>])", t):
                self.fail("M7", self.main, n, "use `2>|` (nf-core sets noclobber)")

    # M11
    def check_label(self):
        self.ok("M11")
        labels = [n for n, t in numbered(self.main_text)
                  if (m := re.match(r"\s*label\s+['\"](\w+)['\"]", t)) and m.group(1) in LABELS]
        if len(labels) != 1:
            self.fail("M11", self.main, labels[1] if len(labels) > 1 else 0, f"{len(labels)} resource labels; use exactly one")

    # Y1, Y3, Y4
    def check_meta(self):
        self.ok("Y1", "Y3", "Y4")
        text = self.meta_text
        for n, t in numbered(text):
            if "edam:" in t and "#" not in t.split("edam:", 1)[1]:
                self.fail("Y1", self.meta, n, "EDAM term without its format name comment, e.g. `# FASTQ`")
            if re.search(r"ontologies:\s*\[\s*\]", t):
                self.fail("Y1", self.meta, n, "empty ontologies; confirm no EDAM term exists")
            if re.match(r"\s*doi:\s*(\"\"|''|null|~)?\s*$", t):
                self.fail("Y3", self.meta, n, "empty doi; omit the key")
        missing = len(re.findall(r"^\s*type:\s*file\s*$", text, re.M)) - len(re.findall(r"^\s*ontologies:", text, re.M))
        if missing > 0:
            self.fail("Y1", self.meta, 0, f"{missing} file entries without ontologies")
        block, ln = top_level_block(text, "tools")
        tools = len(re.findall(r"^\s*-\s+[\w.+-]+:\s*$", block, re.M))
        if block.count("identifier:") < tools:
            self.fail("Y3", self.meta, ln, "a tool has no `identifier` (use \"\" when not on bio.tools)")
        if block.count("args_id:") < tools:
            self.fail("Y4", self.meta, ln, "a tool has no `args_id`")

    # S1
    def check_components(self):
        self.ok("S1")
        block, ln = top_level_block(self.meta_text, "components")
        listed = set(re.findall(r"^\s*-\s*['\"]?([\w./-]+)", block, re.M))
        for dep in self.includes():
            rel = Path(os.path.relpath(dep, self.root)).parts
            name = "/".join(rel[2:])
            if rel[:2] in (("modules", "nf-core"), ("subworkflows", "nf-core")) and name not in listed:
                self.fail("S1", self.meta, ln, f"`{name}` is included but missing from components")

    # C2
    def check_strict_syntax(self):
        self.ok("C2")
        for path, text in ((self.main, self.main_text), (self.test, self.test_text)):
            for n, t in numbered(text):
                if t.lstrip().startswith("//"):
                    continue
                if re.search(r"\bChannel\s*\.", t):
                    self.fail("C2", path, n, "`Channel` is the class; use `channel`")
                if re.search(r"\{\s*it\b|(?<![\w.$])it(?:\.\w|\[)", t):
                    self.fail("C2", path, n, "implicit `it`; name the closure parameter")

    # T1, T3-T6, then T7-T11
    def check_tests(self):
        self.ok("T1", "T3", "T4", "T5", "T6")
        text, blocks = self.test_text, list(test_blocks(self.test_text))
        for name, start, body in blocks:
            ln = line_of(text, start)
            stub = STUB.search(body)
            snaps = list(re.finditer(r"snapshot\(\s*", body))
            if not snaps and not re.search(r"(process|workflow)\.failed", body):
                self.fail("T1", self.test, ln, f'"{name}" has no snapshot')
            for m in snaps:
                if not body.startswith("sanitizeOutput(", m.end()):
                    self.fail("T1", self.test, line_of(text, start + m.start()), f'snapshot without sanitizeOutput in "{name}"')
            outer = re.search(r"assertAll\s*\(", body)
            status = re.search(r"assert\s+(process|workflow)\.(success|failed)", body)
            if not status or (outer and outer.start() < status.start()):
                self.fail("T4", self.test, ln, f'"{name}": put a bare `assert process.success` before assertAll(...), as the nf-core template does')
            if " - " in name:
                if stub and not name.endswith(" - stub"):
                    self.fail("T5", self.test, ln, f'stub test name should end with " - stub": "{name}"')
                if re.search(r"\[(?! )|(?<! )\]", name):
                    self.fail("T6", self.test, ln, f'write grouped inputs as "[ bam, bai ]": "{name}"')
            elif len(name.split()) >= 5:
                self.fail("T6", self.test, ln, f'sentence-style name; prefer "<organism> - <inputs> - <outputs>": "{name}"')
            else:
                self.fail("T5", self.test, ln, f'"{name}" should read "<organism> - <inputs> - <outputs/config>"')
        if not any(STUB.search(body) for _, _, body in blocks):
            self.fail("T3", self.test, 0, "no stub test")
        for n, t in numbered(text):
            if re.search(r"(process|workflow)\.out\.versions", t):
                self.fail("T1", self.test, n, "separate versions assertion; sanitizeOutput already snapshots versions")
        self.check_module_args()
        self.check_test_data()
        self.check_snapshot()
        self.check_tags()

    # T7
    def check_module_args(self):
        cfg = self.dir / "tests" / "nextflow.config"
        ctext = read(cfg)
        if self.kind == "subworkflow":
            self.na("T7", "subworkflow tests configure several processes")
            return
        if not ctext:
            if "module_args" in self.test_text:
                self.fail("T7", self.test, 0, "tests set module_args but there is no tests/nextflow.config")
            else:
                self.na("T7", "no tests/nextflow.config")
            return
        self.ok("T7")
        hits = list(re.finditer(r"ext\.args\d*\s*=", ctext))
        for i, m in enumerate(hits):
            end = hits[i + 1].start() if i + 1 < len(hits) else len(ctext)
            if "module_args" not in ctext[m.start():end].split("withName")[0]:
                self.fail("T7", cfg, line_of(ctext, m.start()), "ext.args should come from params.module_args, set per test")
        if "module_args" in ctext and not re.search(r"module_args\d*\s*\?:", ctext):
            self.fail("T7", cfg, 0, "default it: `params.module_args ?: ''`")

    # T8
    def check_test_data(self):
        self.ok("T8")
        for f in sorted((self.dir / "tests").rglob("*")):
            if f.is_file() and f.name not in ("main.nf.test", "main.nf.test.snap", "tags.yml") and f.suffix != ".config":
                self.fail("T8", f, 0, "local fixture file; host it on the test-datasets modules branch or generate it in the test")
        for n, t in numbered(self.test_text):
            if re.search(r"\bprojectDir\b", t):
                self.fail("T8", self.test, n, "`projectDir` path; use params.modules_testdata_base_path")
            if "pipelines_testdata_base_path" in t:
                self.fail("T8", self.test, n, "pipeline test data; use the test-datasets modules branch")
            if re.search(r"https?://", t):
                self.fail("T8", self.test, n, "hardcoded URL; use params.modules_testdata_base_path")
        for m in re.finditer(r"file\(\s*params\.modules_testdata_base_path[^)]*\)", self.test_text):
            if "checkIfExists" not in m.group(0):
                self.fail("T8", self.test, line_of(self.test_text, m.start()), "add `checkIfExists: true`")

    # T9, T10
    def check_snapshot(self):
        snap = self.dir / "tests" / "main.nf.test.snap"
        stext = read(snap)
        if not stext:
            self.na("T9", "no snapshot file")
            self.na("T10", "no snapshot file")
            return
        self.ok("T9", "T10")
        try:
            data = json.loads(stext)
        except ValueError:
            self.fail("T9", snap, 0, "snapshot is not valid JSON")
            return
        names = {name: bool(STUB.search(body)) for name, _, body in test_blocks(self.test_text)}
        seen = {}
        for key, entry in data.items():
            if names.get(key) or "stub" in key.lower():
                continue
            content = json.dumps(entry.get("content", entry) if isinstance(entry, dict) else entry, sort_keys=True)
            ln = line_of(stext, stext.find(json.dumps(key)))
            if EMPTY_MD5 in content:
                self.fail("T9", snap, ln, f'"{key}" snapshots an empty file')
            if key not in names:
                continue  # named partial snapshots (.match("x")) may legitimately repeat
            if content in seen:
                self.fail("T10", snap, ln, f'"{key}" has the same snapshot as "{seen[content]}"')
            else:
                seen[content] = key

    # T11
    def check_tags(self):
        self.ok("T11")
        text = self.test_text
        tags = set(re.findall(r"^\s*tag\s+['\"]([^'\"]+)['\"]", text, re.M))
        if self.kind == "module":
            need = {"modules", "modules_nfcore", self.name, self.name.split("/")[0]}
        else:
            need = {"subworkflows", "subworkflows_nfcore", f"subworkflows/{self.name}"}
            for dep in self.includes():
                need |= self.component_tags(dep)
        for s in re.findall(r"^\s*script\s+['\"]([^'\"]+)['\"]", text, re.M):
            target = Path(os.path.normpath(self.dir / "tests" / s)).parent
            if target != self.dir:
                need |= self.component_tags(target)
        missing = sorted(need - tags)
        if missing:
            self.fail("T11", self.test, 0, "missing tags: " + ", ".join(missing))


def load_rubric(path=RUBRIC):
    pattern = r"^\|\s*([A-Z]\d+)\s*\|\s*(gate|blocker|major|minor|nit)\s*\|"
    return dict(re.findall(pattern, Path(path).read_text(), re.M))


def footer(rubric=RUBRIC, root=PLUGIN_ROOT):
    """Reviewer identity line: plugin version from its manifest, rubric version from the rubric title."""
    version = "unknown"
    for manifest in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        if (root / manifest).is_file():
            version = json.loads((root / manifest).read_text()).get("version", version)
            break
    m = re.search(r"rubric (v\d+)", Path(rubric).read_text())
    return f"nf-core-reviewer {version} / vagkaratzas-review (rubric {m.group(1) if m else 'unknown'})"


def read_verdicts(path, rules):
    rows = {}
    for n, line in numbered(Path(path).read_text()):
        if not line.strip() or line.startswith("#"):
            continue
        cols = [c.strip().lower() for c in line.split("\t")]
        rule = cols[0].upper()
        if len(cols) < 3 or cols[1] not in STATUSES or cols[2] not in STATUSES:
            raise SystemExit(f"{path}:{n}: expected rule<TAB>pass|fail|na<TAB>pass|fail|na")
        if rule not in rules:
            raise SystemExit(f"{path}:{n}: unknown rule {rule}")
        if rule in rows:
            raise SystemExit(f"{path}:{n}: duplicate rule {rule}")
        rows[rule] = (cols[1], cols[2])
    missing = sorted(set(rules) - set(rows), key=rule_key)
    if missing:
        raise SystemExit("missing verdicts for: " + ", ".join(missing))
    return rows


def score(rows, rules):
    out = {}
    for i, column in enumerate(("diff", "overall")):
        earned = total = 0
        gates, failed = {}, []
        for rule in sorted(rules, key=rule_key):
            severity, status = rules[rule], rows[rule][i]
            if severity == "gate":
                gates[rule] = status
                continue
            if status == "fail":
                failed.append(f"{rule} ({severity})")
            if status == "na" or not WEIGHTS[severity]:
                continue
            total += WEIGHTS[severity]
            earned += WEIGHTS[severity] if status == "pass" else 0
        value = Decimal(10) if not total else Decimal(10 * earned) / Decimal(total)
        if "fail" in gates.values():
            value *= GATE_FACTOR
        out[column] = {"score": value.quantize(Decimal("0.01"), ROUND_HALF_UP), "gates": gates, "failed": failed}
    blocking = any(rules[r] in ("blocker", "major") and rows[r][0] == "fail" for r in rules)
    diff = out["diff"]
    out["event"] = "REQUEST_CHANGES" if blocking or "fail" in diff["gates"].values() else "COMMENT"
    out["approval_line"] = all(s == "pass" for s in diff["gates"].values()) and diff["score"] == Decimal("10.00")
    return out


def cmd_check(args):
    comp = Path(args.component).resolve()
    if args.repo_root:
        root = Path(args.repo_root).resolve()
    else:
        top = subprocess.run(["git", "-C", str(comp), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True)
        root = Path(top.stdout.strip()).resolve()
    checker = Checker(comp, root, Path(args.diff).read_text() if args.diff else None)
    for rule, result in sorted(checker.run().items(), key=lambda item: rule_key(item[0])):
        if isinstance(result, str):
            print(f"{rule}\tNA\t\t\t{result}")
        elif not result:
            print(f"{rule}\tPASS")
        for path, line, msg in [] if isinstance(result, str) else result:
            print(f"{rule}\tFAIL\t{checker.rel(path)}:{line}\t{checker.scope(path, line)}\t{msg}")


def cmd_score(args):
    rules = load_rubric(args.rubric)
    result = score(read_verdicts(args.verdicts, rules), rules)
    d, o = result["diff"], result["overall"]
    print(f"Diff {d['score']}/10 · Overall {o['score']}/10")
    print(f"event: {result['event']}")
    print(f"approval line: {'yes' if result['approval_line'] else 'no'}")
    print("gates: " + ", ".join(f"{g} {s}" for g, s in d["gates"].items()))
    print("diff failed: " + (", ".join(d["failed"]) or "none"))
    print("overall failed: " + (", ".join(o["failed"]) or "none"))
    print("footer: " + footer(args.rubric))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check", help="run the script rules on one component")
    check.add_argument("component")
    check.add_argument("--diff", help="unified diff of the PR or branch")
    check.add_argument("--repo-root", help="modules repo root (default: git toplevel of the component)")
    check.set_defaults(func=cmd_check)
    scorer = sub.add_parser("score", help="compute Diff/Overall scores from a verdicts TSV")
    scorer.add_argument("verdicts")
    scorer.add_argument("--rubric", default=RUBRIC)
    scorer.set_defaults(func=cmd_score)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
