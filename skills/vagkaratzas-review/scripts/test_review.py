import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review  # noqa: E402

BAD_MAIN = """process FOO_BAR {
    label 'process_low'
    label 'process_high'
    container "${ workflow.containerEngine == 'singularity' ? 'https://depot.galaxyproject.org/singularity/foo:1.0' : 'quay.io/biocontainers/foo:1.0' }"

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path("*.txt"), emit: txt
    tuple val("${task.process}"), val('foo'), eval('foo --version'), emit: versions_foo, topic: versions

    script:
    \"\"\"
    foo $reads > out.txt 2> log.txt
    \"\"\"
}
"""

BAD_TEST = """nextflow_process {
    name "Test Process FOO_BAR"
    script "../main.nf"
    process "FOO_BAR"
    tag "modules"

    test("test1") {
        when { process { \"\"\" input[0] = Channel.of([ [id:'t'], file("${projectDir}/x.txt") ]) \"\"\" } }
        then {
            assertAll(
                { assert process.success },
                { assert snapshot(process.out).match() }
            )
        }
    }
}
"""

GOOD_MAIN = """process FOO_BAR {
    tag "$meta.id"
    label 'process_single'

    conda "${moduleDir}/environment.yml"
    container "${workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container
        ? 'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/aa/data'
        : 'community.wave.seqera.io/library/foo:1.0--abc'}"

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path("${prefix}.txt"), emit: txt
    tuple val("${task.process}"), val('foo'), eval('foo --version'), emit: versions_foo, topic: versions
    tuple val("${task.process}"), val('python'), eval('python --version | cut -d" " -f2'), emit: versions_python, topic: versions

    script:
    def args = task.ext.args ?: ''
    prefix = task.ext.prefix ?: "${meta.id}"
    \"\"\"
    foo $args "$reads" > "${prefix}.txt" 2>| err.log
    \"\"\"
}
"""

GOOD_TEST = """nextflow_process {
    name "Test Process FOO_BAR"
    script "../main.nf"
    process "FOO_BAR"
    config "./nextflow.config"

    tag "modules"
    tag "modules_nfcore"
    tag "foo"
    tag "foo/bar"
    tag "gunzip"

    test("sarscov2 - [ fastq, fai ] - txt") {
        setup {
            run("GUNZIP") {
                script "../../../gunzip/main.nf"
                process { \"\"\" input[0] = [ [:], [] ] \"\"\" }
            }
        }
        when {
            params { module_args = '--fast' }
            process {
                \"\"\"
                input[0] = channel.of([ [ id:'test' ], file(params.modules_testdata_base_path + 'genomics/sarscov2/x.fastq.gz', checkIfExists: true) ])
                \"\"\"
            }
        }
        then {
            assert process.success
            assertAll(
                { assert snapshot(sanitizeOutput(process.out)).match() }
            )
        }
    }

    test("sarscov2 - fastq - txt - stub") {
        options "-stub"
        when {
            params { module_args = '' }
            process { \"\"\" input[0] = [ [ id:'test' ], [] ] \"\"\" }
        }
        then {
            assert process.success
            assertAll(
                { assert snapshot(sanitizeOutput(process.out)).match() }
            )
        }
    }
}
"""

GOOD_META = """name: foo_bar
tools:
  - foo:
      description: Foo
      identifier: ""
      args_id: "$args"
input:
  - - reads:
        type: file
        ontologies:
          - edam: http://edamontology.org/format_1930 # FASTQ
containers:
  docker: {}
"""

ENV = """channels:
  - conda-forge
  - bioconda
dependencies:
  - bioconda::foo=1.0
  - conda-forge::python=3.12
  - conda-forge::pigz=2.8
"""


def make_module(root, main, test, env, meta="", config=None, lock=False):
    comp = root / "modules" / "nf-core" / "foo" / "bar"
    (comp / "tests").mkdir(parents=True)
    (comp / "main.nf").write_text(main)
    (comp / "environment.yml").write_text(env)
    (comp / "meta.yml").write_text(meta)
    (comp / "tests" / "main.nf.test").write_text(test)
    if config:
        (comp / "tests" / "nextflow.config").write_text(config)
    if lock:
        (comp / ".conda-lock").mkdir()
        (comp / ".conda-lock" / "linux_amd64-bd-abc_1.txt").write_text("lock")
    return comp


def failing(results):
    return {rule for rule, res in results.items() if isinstance(res, list) and res}


class CheckTest(unittest.TestCase):
    def test_bad_module_hits_script_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            comp = make_module(root, BAD_MAIN, BAD_TEST, ENV + "  - bioconda::samtools=1.21\n")
            fails = failing(review.Checker(comp, root).run())
        self.assertTrue({"E1", "M2", "M7", "M11", "C2", "T1", "T3", "T4", "T5", "T8", "T11"} <= fails, fails)

    def test_clean_module_has_no_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = "process {\n    withName: 'FOO_BAR' {\n        ext.args = { params.module_args ?: '' }\n    }\n}\n"
            comp = make_module(root, GOOD_MAIN, GOOD_TEST, ENV, GOOD_META, config, lock=True)
            results = review.Checker(comp, root).run()
        self.assertEqual(failing(results), set(), {r: v for r, v in results.items() if isinstance(v, list) and v})

    def test_empty_and_duplicate_snapshots(self):
        test = 'test("sarscov2 - fastq - txt") {}\ntest("sarscov2 - fasta - txt") {}\n'
        content = {"content": [{"txt": ["test.txt:md5,d41d8cd98f00b204e9800998ecf8427e"]}]}
        snap = {"sarscov2 - fastq - txt": content, "sarscov2 - fasta - txt": content}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            comp = make_module(root, GOOD_MAIN, test, ENV)
            (comp / "tests" / "main.nf.test.snap").write_text(review.json.dumps(snap))
            fails = failing(review.Checker(comp, root).run())
        self.assertTrue({"T9", "T10"} <= fails, fails)

    def test_t4_wants_template_order(self):
        inside = 'test("a - b - c") { then { assertAll ( { assert process.success }, { assert snapshot(sanitizeOutput(process.out)).match() } ) } }\n'
        template = 'test("a - b - c") { then { assert process.success\n assertAll( { assert snapshot(sanitizeOutput(process.out)).match() } ) } }\n'
        for test, expected in ((inside, True), (template, False)):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                comp = make_module(root, GOOD_MAIN, test, ENV)
                self.assertEqual("T4" in failing(review.Checker(comp, root).run()), expected, test)

    def test_t8_ignores_urls_in_comments(self):
        for line, expected in (("// TODO see https://github.com/x", False), ('file("https://x/y.fa")', True)):
            test = GOOD_TEST.replace("        when {\n            params { module_args = '--fast' }",
                                     "        when {\n            " + line + "\n            params { module_args = '--fast' }", 1)
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                comp = make_module(root, GOOD_MAIN, test, ENV)
                self.assertEqual("T8" in failing(review.Checker(comp, root).run()), expected, line)

    def test_t11_reads_root_relative_script_paths(self):
        test = GOOD_TEST.replace('script "../main.nf"', 'script "modules/nf-core/foo/bar/main.nf"', 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            comp = make_module(root, GOOD_MAIN, test, ENV)
            self.assertNotIn("T11", failing(review.Checker(comp, root).run()))

    def test_e1_na_without_environment_yml(self):
        main = BAD_MAIN.replace("quay.io/biocontainers/foo:1.0", "quay.io/nf-core/foo:1.0")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            comp = make_module(root, main, GOOD_TEST, ENV)
            (comp / "environment.yml").unlink()
            self.assertIsInstance(review.Checker(comp, root).run()["E1"], str)

    def test_diff_scope(self):
        diff = ("diff --git a/x.nf b/x.nf\n--- a/x.nf\n+++ b/x.nf\n@@ -1,2 +1,3 @@\n a\n+b\n c\n"
                "diff --git a/y.nf b/y.nf\nnew file mode 100644\n--- /dev/null\n+++ b/y.nf\n@@ -0,0 +1 @@\n++ added\n")
        files, added = review.parse_diff(diff)
        self.assertEqual(files, {"x.nf", "y.nf"})
        self.assertEqual(added, {("x.nf", 2), ("y.nf", 1)})


class ScoreTest(unittest.TestCase):
    RUBRIC = "| G1 | gate |\n" + "".join(f"| B{i} | blocker |\n" for i in range(3)) + \
        "".join(f"| J{i} | major |\n" for i in range(4)) + "".join(f"| N{i} | minor |\n" for i in range(3)) + "| X1 | nit |\n"

    def scored(self, gate):
        with tempfile.TemporaryDirectory() as tmp:
            rubric, verdicts = Path(tmp) / "rubric.md", Path(tmp) / "v.tsv"
            rubric.write_text(self.RUBRIC)
            fails = {"J0", "N0", "X1"}
            rows = [f"{r}\t{'fail' if r in fails else 'pass'}\tpass" for r in review.load_rubric(rubric) if r != "G1"]
            verdicts.write_text("\n".join(rows + [f"G1\t{gate}\t{gate}"]))
            rules = review.load_rubric(rubric)
            return review.score(review.read_verdicts(verdicts, rules), rules)

    def test_worked_example(self):
        result = self.scored("pass")
        self.assertEqual(result["diff"]["score"], Decimal("8.50"))
        self.assertEqual(result["overall"]["score"], Decimal("10.00"))
        self.assertEqual(result["event"], "REQUEST_CHANGES")
        self.assertFalse(result["approval_line"])

    def test_gate_failure_multiplies(self):
        result = self.scored("fail")
        self.assertEqual(result["diff"]["score"], Decimal("3.40"))
        self.assertEqual(result["overall"]["score"], Decimal("4.00"))

    def test_footer_reads_plugin_and_rubric_versions(self):
        self.assertRegex(review.footer(), r"^nf-core-reviewer \d+\.\d+\.\d+ / vagkaratzas-review \(rubric v\d+\)$")

    def test_missing_rule_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            verdicts = Path(tmp) / "v.tsv"
            verdicts.write_text("G1\tpass\tpass\n")
            with self.assertRaises(SystemExit):
                review.read_verdicts(verdicts, {"G1": "gate", "B0": "blocker"})


if __name__ == "__main__":
    unittest.main()
