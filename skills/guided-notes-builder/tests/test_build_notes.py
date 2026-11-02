"""Tests for build_notes.py. Run from this skill's folder:

    python -m unittest discover tests

Requires python-docx. PDF tests run only when LibreOffice is installed.
"""

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "build_notes.py"
SAMPLE = SKILL / "examples" / "sample_packet.json"

sys.path.insert(0, str(SCRIPT.parent))
import build_notes as bn  # noqa: E402
from docx import Document  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402


def sample():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def run(packet_path, out_dir, *extra):
    return subprocess.run([sys.executable, str(SCRIPT), str(packet_path), "--out-dir", str(out_dir), *extra],
                          capture_output=True, text=True)


class BlankSizing(unittest.TestCase):
    def test_standard_rule(self):
        self.assertEqual(bn.blank_length("a"), 13)            # clamp to 10
        self.assertEqual(bn.blank_length("concatenation"), 22)  # (13 + 4) * 1.3
        self.assertEqual(bn.blank_length("x" * 60), 39)       # clamp to 30


class Validation(unittest.TestCase):
    def errors(self, data):
        try:
            bn.validate(data)
        except bn.ContentError as e:
            return str(e)
        return ""

    def test_sample_is_valid(self):
        self.assertEqual(self.errors(sample()), "")

    def test_slide_reference_rejected(self):
        d = sample()
        d["lessons"][0]["guiding_question"] = "What does slide 4 show?"
        self.assertIn("slides", self.errors(d))

    def test_blank_answer_mismatch(self):
        d = sample()
        d["lessons"][0]["sections"][0]["notes"][0] = {"text": "A {{blank}} and a {{blank}}.", "answers": ["x"]}
        self.assertIn("2 blank(s) but 1 answer(s)", self.errors(d))

    def test_blank_inside_code_rejected(self):
        d = sample()
        d["lessons"][0]["sections"][0]["notes"][0] = ["Run `print({{blank}})` now.", "x"]
        self.assertIn("inside a `code` span", self.errors(d))

    def test_target_count(self):
        d = sample()
        d["lessons"][0]["targets"] = ["I can do one thing."]
        self.assertIn("2-4 learning targets", self.errors(d))


class Build(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_builds_and_checks(self):
        r = run(SAMPLE, self.out)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        student = self.out / "Intro_to_Python_Unit_2_Guided_Notes_Student.docx"
        teacher = self.out / "Intro_to_Python_Unit_2_Guided_Notes_Teacher_Key.docx"
        self.assertTrue(student.exists() and teacher.exists())
        s_text = "\n".join(p.text for p in Document(student).paragraphs)
        t_text = "\n".join(p.text for p in Document(teacher).paragraphs)
        self.assertIn("_" * bn.blank_length("concatenation"), s_text)
        self.assertNotIn("concatenation.", s_text)
        self.assertIn("concatenation", t_text)
        self.assertIn("TEACHER ANSWER KEY", t_text)

    def test_real_word_lists(self):
        run(SAMPLE, self.out)
        doc = Document(self.out / "Intro_to_Python_Unit_2_Guided_Notes_Student.docx")
        numbering = doc.part.numbering_part.element
        texts = {el.find(qn("w:lvl")).find(qn("w:lvlText")).get(qn("w:val"))
                 for el in numbering.findall(qn("w:abstractNum"))}
        self.assertTrue({"•", "☐", "%1."} <= texts)
        typed = [p.text for p in doc.paragraphs if p.text.startswith(("•", "☐"))]
        self.assertEqual(typed, [], "bullet characters must not be typed into text")

    def test_no_overwrite(self):
        run(SAMPLE, self.out)
        run(SAMPLE, self.out)
        self.assertTrue((self.out / "Intro_to_Python_Unit_2_Guided_Notes_r2_Student.docx").exists())

    def test_bad_content_exit_code(self):
        d = sample()
        d["lessons"][0]["review"] = []
        p = self.out / "bad.json"
        p.write_text(json.dumps(d))
        r = run(p, self.out / "o")
        self.assertEqual(r.returncode, 1)
        self.assertIn("CONTENT NEEDS FIXING", r.stdout)

    @unittest.skipUnless(shutil.which("soffice") or shutil.which("libreoffice"), "LibreOffice not installed")
    def test_pdf_export(self):
        r = run(SAMPLE, self.out, "--pdf")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue((self.out / "Intro_to_Python_Unit_2_Guided_Notes_Student.pdf").exists())


if __name__ == "__main__":
    unittest.main()
