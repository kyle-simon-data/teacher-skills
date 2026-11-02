"""Tests for build_linkit.py. Run from this skill's folder:

    python -m unittest discover tests
"""

import csv
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "build_linkit.py"
SAMPLE = SKILL / "examples" / "sample_questions.json"

sys.path.insert(0, str(SCRIPT.parent))
import build_linkit as bl  # noqa: E402


def run(questions_path, out_dir):
    return subprocess.run([sys.executable, str(SCRIPT), str(questions_path), "--out-dir", str(out_dir)],
                          capture_output=True, text=True)


class SampleBuild(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        self.result = run(SAMPLE, self.out)

    def tearDown(self):
        self.tmp.cleanup()

    def test_succeeds_and_reports_counts(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout + self.result.stderr)
        self.assertIn("Items in zip: 7", self.result.stdout)
        self.assertIn("Items converted from matching: 3", self.result.stdout)
        self.assertIn("Source questions left for manual entry: 2", self.result.stdout)
        self.assertNotIn("MISMATCH", self.result.stdout)

    def test_zip_contents(self):
        z = self.out / "network_security_sample_quiz_linkit.zip"
        with zipfile.ZipFile(z) as zf:
            self.assertEqual(sorted(zf.namelist()), ["imsmanifest.xml", "res00001.dat"])
            pool = zf.read("res00001.dat").decode()
        self.assertIn("browser &amp; a server", pool)
        self.assertIn("<code>ipconfig</code>", pool)
        self.assertNotIn("QUESTION_TRUEFALSE", pool)

    def test_matrix(self):
        m = self.out / "network_security_sample_quiz_companion_matrix.csv"
        with m.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 9)
        self.assertEqual(rows[0]["Correct Answer"], "B")
        self.assertTrue(rows[-1]["LinkIt Status"].startswith("Not imported"))

    def test_no_overwrite(self):
        run(SAMPLE, self.out)
        self.assertTrue((self.out / "network_security_sample_quiz_linkit_r2.zip").exists())


class Matching(unittest.TestCase):
    def test_rotation_small(self):
        items = bl.convert_matching(1, "Match:", [["a", "1"], ["b", "2"], ["c", "3"]], False)
        self.assertEqual(items[0]["choices"], ["2", "3", "1"])
        for it in items:
            self.assertEqual(it["choices"][it["correct"]], it["matching_right"])

    def test_large_set_uses_five_choices(self):
        pairs = [[f"L{i}", f"R{i}"] for i in range(1, 8)]
        items = bl.convert_matching(1, "Match:", pairs, False)
        self.assertEqual(len(items), 7)
        for it in items:
            self.assertEqual(len(it["choices"]), 5)
            self.assertEqual(it["choices"][it["correct"]], it["matching_right"])


class EdgeCases(unittest.TestCase):
    def build(self, data):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "q.json"
            p.write_text(json.dumps(data))
            r = run(p, Path(d) / "out")
            files = sorted(x.name for x in (Path(d) / "out").glob("*")) if (Path(d) / "out").exists() else []
            return r, files

    def test_all_manual_gives_matrix_only(self):
        r, files = self.build({"title": "T", "questions": [{"type": "essay", "text": "Why?"}]})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(files, ["t_companion_matrix.csv"])

    def test_single_choice_needs_clarification(self):
        r, _ = self.build({"title": "T", "questions": [
            {"type": "multiple_choice", "text": "Q", "choices": ["only"], "correct": [0]}]})
        self.assertEqual(r.returncode, 1)
        self.assertIn("NEEDS CLARIFICATION", r.stdout)

    def test_cdata_terminator_is_split(self):
        self.assertEqual(bl.cdata("a]]>b", is_html=True), "<![CDATA[a]]]]><![CDATA[>b]]>")


if __name__ == "__main__":
    unittest.main()
