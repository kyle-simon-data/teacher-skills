#!/usr/bin/env python3
"""Build a student guided-notes packet and matching teacher key (.docx, and
optionally .pdf) from a packet JSON file.

Usage:
  python build_notes.py packet.json --out-dir OUT [--pdf] [--render-dir PNGS]
                        [--validate-only] [--overwrite]

Requires python-docx (pip install python-docx). PDF export and page images
need LibreOffice (soffice) and, for images, pdftoppm (poppler).

Exit codes: 0 success, 1 content needs fixing, 2 output check failed.
"""

import argparse
import json
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from docx import Document
    from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import nsdecls, qn
    from docx.shared import Inches, Pt, RGBColor
except ImportError:  # pragma: no cover
    sys.exit("python-docx is required: pip install python-docx")

# ------------------------------------------------------------ constants

TEXT_WIDTH_IN = 7.0  # US Letter minus 0.75 in side margins

C_VERY_DARK = "202020"   # headings, table headers
C_DARK = "3F3F3F"        # secondary emphasis, teacher answers
C_MEDIUM = "595959"      # supporting text
C_ALT_ROW = "F2F2F2"     # alternating rows, code blocks
C_CALLOUT = "EEEEEE"     # directions callout, teacher answer areas
C_GUIDING_Q = "E7E7E7"   # guiding-question callout
C_TEXT = "111111"        # main text
C_WHITE = "FFFFFF"       # table-header text
C_RULE = "7F7F7F"        # response lines, table borders

MIN_PT = 10.5
BLANK = "{{blank}}"
CODE_SPAN = re.compile(r"`([^`]+)`")
SLIDE_REF = re.compile(r"\bslides?\b|student-facing", re.I)

FONTS = {"body": "Aptos", "display": "Aptos Display", "code": "Courier New"}


class ContentError(Exception):
    pass


def blank_length(answer):
    """Shared standard: clamp(len + 4, 10, 30) x 1.30, rounded (13-39)."""
    return round(max(10, min(30, len(answer) + 4)) * 1.30)


# ------------------------------------------------------------ validation

def normalize_note(item, where):
    if isinstance(item, (list, tuple)):
        if len(item) != 2:
            raise ContentError(f"{where}: shorthand notes are [sentence, answer]")
        text, answers = item
        answers = [answers] if isinstance(answers, str) else list(answers)
        return {"text": text, "answers": answers}
    if isinstance(item, dict) and "code" in item:
        return {"code": item["code"]}
    if isinstance(item, dict) and "text" in item:
        a = item.get("answers", item.get("answer", []))
        return {"text": item["text"], "answers": [a] if isinstance(a, str) else list(a)}
    raise ContentError(f"{where}: a note must be [sentence, answer], "
                       "{text, answers} or {code}")


def validate(data):
    """Return (packet, lessons, warnings). Raise ContentError on problems."""
    errors, warnings = [], []

    def need_text(value, where, code_ok=True):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{where}: expected nonempty text")
            return
        if value.count("`") % 2:
            errors.append(f"{where}: unmatched code backtick")
        if not code_ok and "`" in value:
            errors.append(f"{where}: use plain text without backticks")
        if SLIDE_REF.search(value):
            errors.append(f"{where}: remove the reference to slides ({value[:60]!r})")

    packet = data.get("packet") or {}
    for f in ("course", "packet_title", "subtitle", "unit_label", "overview", "output_stem"):
        need_text(packet.get(f), f"packet.{f}", code_ok=False)
    stem = packet.get("output_stem", "")
    if stem and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", stem):
        errors.append("packet.output_stem: use letters, numbers, underscores, dots or hyphens")

    lessons = data.get("lessons") or []
    if not lessons:
        errors.append("lessons: at least one lesson is required")
    seen = set()
    for li, lesson in enumerate(lessons):
        num = str(lesson.get("number", f"#{li + 1}"))
        w = f"Lesson {num}"
        for f in ("number", "title", "guiding_question"):
            need_text(str(lesson.get(f, "")) if lesson.get(f) is not None else None,
                      f"{w} {f}", code_ok=(f == "guiding_question"))
        if num in seen:
            errors.append(f"{w}: duplicate lesson number")
        seen.add(num)

        targets = lesson.get("targets") or []
        if not 2 <= len(targets) <= 4:
            errors.append(f"{w}: use 2-4 learning targets (found {len(targets)})")
        for t in targets:
            need_text(t, f"{w} target")

        sections = lesson.get("sections") or []
        if not sections:
            errors.append(f"{w}: at least one notes section is required")
        for si, sec in enumerate(sections):
            sw = f"{w} section {si + 1}"
            need_text(sec.get("heading"), f"{sw} heading", code_ok=False)
            notes = []
            for ni, item in enumerate(sec.get("notes") or []):
                nw = f"{sw} note {ni + 1}"
                try:
                    n = normalize_note(item, nw)
                except ContentError as e:
                    errors.append(str(e))
                    continue
                notes.append(n)
                if "code" in n:
                    if not isinstance(n["code"], str) or not n["code"].strip():
                        errors.append(f"{nw}: code block is empty")
                    continue
                need_text(n["text"], nw)
                k = n["text"].count(BLANK)
                if k not in (1, 2):
                    errors.append(f"{nw}: each statement needs one blank (two at most), found {k}")
                if k != len(n["answers"]):
                    errors.append(f"{nw}: {k} blank(s) but {len(n['answers'])} answer(s)")
                for a in n["answers"]:
                    need_text(a, f"{nw} answer", code_ok=False)
                pieces = n["text"].split(BLANK)
                before = ""
                for p in pieces[:-1]:
                    before += p
                    if before.count("`") % 2:
                        errors.append(f"{nw}: a blank must not sit inside a `code` span")
                for p in pieces[1:]:
                    if p[:1].isalnum():
                        errors.append(f"{nw}: put a space or punctuation after each blank")
                if k == 2:
                    warnings.append(f"{nw}: two blanks; confirm the sentence stays easy to follow")
            if not any("text" in n for n in notes):
                errors.append(f"{sw}: needs at least one cloze statement")
            sec["notes"] = notes

        for oi, org in enumerate(lesson.get("organizers") or []):
            ow = f"{w} organizer {oi + 1}"
            need_text(org.get("heading"), f"{ow} heading", code_ok=False)
            cols = org.get("columns") or []
            if len(cols) < 2:
                errors.append(f"{ow}: needs at least 2 columns")
            for c in cols:
                need_text(c, f"{ow} column", code_ok=False)
            rows = org.get("rows") or []
            if not rows:
                errors.append(f"{ow}: needs at least 1 row")
            for r in rows:
                if len(r) != len(cols):
                    errors.append(f"{ow}: every row needs {len(cols)} cells")
                for v in r:
                    need_text(v, f"{ow} cell", code_ok=False)
            given = org.get("given_columns", [0])
            if any(not isinstance(g, int) or not 0 <= g < len(cols) for g in given):
                errors.append(f"{ow}: given_columns must list valid column positions")
            if len(given) >= len(cols):
                errors.append(f"{ow}: at least one column must be left for students to fill in")
            widths = org.get("widths")
            if widths is not None and (len(widths) != len(cols) or min(widths) <= 0):
                errors.append(f"{ow}: widths needs one positive number per column")

        for ei, ex in enumerate(lesson.get("examples") or []):
            ew = f"{w} example {ei + 1}"
            need_text(ex.get("label"), f"{ew} label", code_ok=False)
            need_text(ex.get("summary"), f"{ew} summary")
            for p in ex.get("prompts") or []:
                need_text(p, f"{ew} prompt")

        review = lesson.get("review") or []
        if not review:
            errors.append(f"{w}: at least one review question is required")
        for ri, q in enumerate(review):
            rw = f"{w} review {ri + 1}"
            if isinstance(q, (list, tuple)):
                q = {"question": q[0], "answer": q[1] if len(q) > 1 else ""}
                review[ri] = q
            need_text(q.get("question"), f"{rw} question")
            need_text(q.get("answer"), f"{rw} suggested answer")
            lines = q.get("lines", 3)
            if not isinstance(lines, int) or not 1 <= lines <= 12:
                errors.append(f"{rw}: lines must be a whole number from 1 to 12")

    if errors:
        raise ContentError("\n".join(errors))
    return packet, lessons, warnings


# ------------------------------------------------------------ low-level docx

class Styler:
    def __init__(self, fonts):
        self.f = {**FONTS, **(fonts or {})}

    def run(self, p, text, size=10.5, bold=False, italic=False, color=C_TEXT, font="body"):
        r = p.add_run(text)
        name = self.f.get(font, font)
        r.font.name = name
        rpr = r._element.get_or_add_rPr()
        rf = rpr.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts")
            rpr.insert(0, rf)
        for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rf.set(qn(a), name)
        r.font.size = Pt(max(size, MIN_PT))
        r.font.bold = bold
        r.font.italic = italic
        r.font.color.rgb = RGBColor.from_string(color)
        return r

    def rich(self, p, text, size=10.5, bold=False, color=C_TEXT):
        """Text with `code` spans in the code font."""
        pos = 0
        for m in CODE_SPAN.finditer(text):
            if m.start() > pos:
                self.run(p, text[pos:m.start()], size, bold, color=color)
            self.run(p, m.group(1), size, bold, color=color, font="code")
            pos = m.end()
        if pos < len(text):
            self.run(p, text[pos:], size, bold, color=color)


def spacing(p, before=0, after=5, line=1.15, exact_pt=None):
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = Pt(exact_pt) if exact_pt else line
    pf.widow_control = True


def keep_next(p, on=True):
    p.paragraph_format.keep_with_next = on


def cell_fill(cell, hex_color):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcpr.append(shd)


def cell_margins(cell, top, bottom, side=120):
    tcpr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for tag, v in (("top", top), ("bottom", bottom), ("start", side), ("end", side)):
        el = OxmlElement(f"w:{tag}")
        el.set(qn("w:w"), str(v))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tcpr.append(mar)


def row_flags(row, header=False):
    trpr = row._tr.get_or_add_trPr()
    trpr.append(OxmlElement("w:cantSplit"))
    if header:
        h = OxmlElement("w:tblHeader")
        h.set(qn("w:val"), "true")
        trpr.append(h)


def table_borders(table, color=C_RULE, size=4, none=False):
    tblpr = table._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil" if none else "single")
        if not none:
            el.set(qn("w:sz"), str(size))
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), color)
        b.append(el)
    tblpr.append(b)


def new_table(doc, rows, widths_in, borders=True):
    t = doc.add_table(rows=rows, cols=len(widths_in))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    table_borders(t, none=not borders)
    for j, w in enumerate(widths_in):
        t.columns[j].width = Inches(w)
        for r in t.rows:
            r.cells[j].width = Inches(w)
    return t


def rule_lines(p):
    """Bottom and between borders so every response line is ruled to the margin."""
    ppr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    for edge in ("bottom", "between"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "1")
        el.set(qn("w:color"), C_RULE)
        bdr.append(el)
    ppr.append(bdr)


def page_field(p, styler):
    r = styler.run(p, "", color=C_MEDIUM)
    for kind, text in (("begin", None), (None, "PAGE"), ("separate", None), (None, "1"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        elif text == "PAGE":
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = "PAGE"
        else:
            el = OxmlElement("w:t")
            el.text = text
        r._r.append(el)


class Lists:
    """Explicit single-level Word lists. Abstract definitions are inserted
    before every concrete <w:num>, each with a unique nsid."""

    def __init__(self, doc, fonts):
        self.numbering = doc.part.numbering_part.element
        self.fonts = fonts
        ids = [int(a.get(qn("w:abstractNumId"))) for a in self.numbering.findall(qn("w:abstractNum"))]
        nums = [int(n.get(qn("w:numId"))) for n in self.numbering.findall(qn("w:num"))]
        self.next_abs = max(ids, default=0) + 1
        self.next_num = max(nums, default=0) + 1
        self.bullet = self._num(self._abstract("bullet", "•", fonts["body"]))
        self.checkbox = self._num(self._abstract("bullet", "☐", fonts["body"]))
        self.decimal_abs = self._abstract("decimal", "%1.", fonts["body"], bold=True)

    def _abstract(self, fmt, text, font, bold=False):
        aid = self.next_abs
        self.next_abs += 1
        xml = (
            f'<w:abstractNum {nsdecls("w")} w:abstractNumId="{aid}">'
            f'<w:nsid w:val="{secrets.token_hex(4).upper()}"/>'
            f'<w:multiLevelType w:val="singleLevel"/>'
            f'<w:tmpl w:val="{secrets.token_hex(4).upper()}"/>'
            f'<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="{fmt}"/>'
            f'<w:lvlText w:val="{text}"/><w:lvlJc w:val="left"/>'
            f'<w:pPr><w:ind w:left="360" w:hanging="360"/></w:pPr>'
            f'<w:rPr><w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:cs="{font}" w:hint="default"/>'
            f'{"<w:b/>" if bold else ""}<w:color w:val="{C_TEXT}"/><w:sz w:val="21"/></w:rPr>'
            f'</w:lvl></w:abstractNum>'
        )
        el = parse_xml(xml)
        first_num = self.numbering.find(qn("w:num"))
        if first_num is not None:
            first_num.addprevious(el)
        else:
            self.numbering.append(el)
        return aid

    def _num(self, aid, restart=False):
        nid = self.next_num
        self.next_num += 1
        override = ('<w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride>'
                    if restart else "")
        self.numbering.append(parse_xml(
            f'<w:num {nsdecls("w")} w:numId="{nid}"><w:abstractNumId w:val="{aid}"/>{override}</w:num>'))
        return nid

    def new_review_list(self):
        return self._num(self.decimal_abs, restart=True)

    @staticmethod
    def apply(p, num_id):
        numpr = p._p.get_or_add_pPr().get_or_add_numPr()
        numpr.get_or_add_ilvl().val = 0
        numpr.get_or_add_numId().val = num_id
        p.paragraph_format.left_indent = Inches(0.25)
        p.paragraph_format.first_line_indent = Inches(-0.25)


# ------------------------------------------------------------ document builder

class Builder:
    def __init__(self, packet, lessons, teacher):
        self.packet, self.lessons, self.teacher = packet, lessons, teacher
        self.s = Styler(packet.get("fonts"))
        self.doc = Document()
        self.blanks = 0
        self.answers = 0
        self._setup()
        self.lists = Lists(self.doc, self.s.f)

    # -- setup
    def _setup(self):
        sec = self.doc.sections[0]
        sec.page_width, sec.page_height = Inches(8.5), Inches(11)
        sec.top_margin, sec.bottom_margin = Inches(0.70), Inches(0.65)
        sec.left_margin = sec.right_margin = Inches(0.75)
        sec.header_distance = sec.footer_distance = Inches(0.30)
        for style in self.doc.styles:
            for b in list(style.element.iter(qn("w:pBdr"))):
                b.getparent().remove(b)
        normal = self.doc.styles["Normal"]
        normal.font.name = self.s.f["body"]
        normal.font.size = Pt(MIN_PT)
        normal.font.color.rgb = RGBColor.from_string(C_TEXT)
        normal.paragraph_format.widow_control = True

        course = self.packet["course"]
        hp = sec.header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        self.s.run(hp, f"{course} • {'Teacher Key' if self.teacher else 'Guided Notes'}",
                   color=C_MEDIUM)
        spacing(hp, 0, 0, 1.0)
        fp = sec.footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        self.s.run(fp, f"{course} • {self.packet['unit_label']} | ", color=C_MEDIUM)
        page_field(fp, self.s)
        spacing(fp, 0, 0, 1.0)

    def para(self, before=0, after=5, line=1.15, align=None):
        p = self.doc.add_paragraph()
        spacing(p, before, after, line)
        if align:
            p.alignment = align
        return p

    def heading(self, text, level):
        p = self.doc.add_paragraph(style=f"Heading {level}")
        size, font = {1: (18, "display"), 2: (14, "display"), 3: (11.5, "body")}[level]
        self.s.run(p, text, size, bold=True, color=C_VERY_DARK if level < 3 else C_DARK, font=font)
        spacing(p, {1: 6, 2: 12, 3: 8}[level], {1: 8, 2: 6, 3: 4}[level], 1.1)
        keep_next(p)
        return p

    def id_fields(self, centered=False, after=10):
        if centered:
            for label in ("Name:", "Class:", "Date:"):
                p = self.para(0, 14, 1.3, WD_ALIGN_PARAGRAPH.CENTER)
                self.s.run(p, f"{label} " + "_" * 36, 12)
        else:
            p = self.para(0, after, 1.3)
            keep_next(p)
            self.s.run(p, "Name: " + "_" * 30 + "    Class: " + "_" * 14 + "    Date: " + "_" * 14)

    def callout(self, label, text, fill, keep=False):
        t = new_table(self.doc, 1, [TEXT_WIDTH_IN], borders=False)
        c = t.cell(0, 0)
        cell_fill(c, fill)
        cell_margins(c, 140, 140, 160)
        row_flags(t.rows[0])
        p = c.paragraphs[0]
        spacing(p, 0, 0, 1.25)
        keep_next(p, keep)
        self.s.run(p, label + " ", bold=True, color=C_VERY_DARK)
        self.s.rich(p, text)
        # No spacer paragraph after the callout: an empty paragraph between a
        # table and a keep-with-next heading breaks the chain in LibreOffice.
        # The following heading's space-before provides the gap.

    # -- title page
    def title_page(self):
        pk = self.packet
        for _ in range(5):
            self.para(0, 10, 1.0)
        C = WD_ALIGN_PARAGRAPH.CENTER
        self.s.run(self.para(0, 10, 1.2, C), pk.get("course_label", pk["course"].upper()),
                   14, True, color=C_DARK, font="display")
        p = self.para(0, 10, 1.1, C)
        self.s.run(p, pk["packet_title"], 28, True, color=C_VERY_DARK, font="display")
        self.s.run(self.para(0, 24, 1.2, C), pk["subtitle"], 14, color=C_MEDIUM)
        label = "TEACHER ANSWER KEY" if self.teacher else f"{pk['unit_label']} - Guided Notes Packet"
        self.s.run(self.para(0, 24, 1.2, C), label, 18, True, color=C_VERY_DARK, font="display")
        if self.teacher:
            self.s.run(self.para(0, 24, 1.3, C), "Completed answers appear in bold dark-gray text.",
                       11, italic=True, color=C_MEDIUM)
        else:
            self.id_fields(centered=True)
            self.para(0, 6, 1.0)
        p = self.para(0, 18, 1.35, C)
        p.paragraph_format.left_indent = p.paragraph_format.right_indent = Inches(0.6)
        self.s.rich(p, pk["overview"], 11, color=C_TEXT)
        self.s.run(self.para(4, 8, 1.2, C), "Packet Contents", 12, True, color=C_DARK, font="display")
        for lesson in self.lessons:
            self.s.run(self.para(0, 4, 1.2, C), f"Lesson {lesson['number']} — {lesson['title']}",
                       11, color=C_MEDIUM)
        self.doc.add_page_break()

    # -- lesson parts
    def cloze(self, note):
        p = self.doc.add_paragraph()
        Lists.apply(p, self.lists.bullet)
        spacing(p, 2, 7, 1.5)
        parts = note["text"].split(BLANK)
        for i, part in enumerate(parts):
            if part:
                self.s.rich(p, part)
            if i < len(note["answers"]):
                ans = note["answers"][i]
                if self.teacher:
                    self.s.run(p, ans, bold=True, color=C_DARK)
                    self.answers += 1
                else:
                    self.s.run(p, "_" * blank_length(ans), color=C_TEXT)
                    self.blanks += 1
        return p

    def code_block(self, code):
        t = new_table(self.doc, 1, [TEXT_WIDTH_IN], borders=False)
        c = t.cell(0, 0)
        cell_fill(c, C_ALT_ROW)
        cell_margins(c, 100, 100, 160)
        row_flags(t.rows[0])
        p = c.paragraphs[0]
        spacing(p, 0, 0, 1.15)
        for i, line in enumerate(code.rstrip("\n").split("\n")):
            if i:
                p.add_run().add_break()
            self.s.run(p, line if line else " ", font="code")
        self.para(0, 4, 1.0)

    def section(self, sec):
        self.heading(sec["heading"], 2)
        written = 0
        for n in sec["notes"]:
            if "code" in n:
                self.code_block(n["code"])
                continue
            p = self.cloze(n)
            written += 1
            if written == 1:
                keep_next(p)  # keep the heading with at least two statements

    def organizer(self, org):
        self.heading(org["heading"], 3)
        cols, rows = org["columns"], org["rows"]
        given = set(org.get("given_columns", [0]))
        rel = org.get("widths") or [1] * len(cols)
        widths = [TEXT_WIDTH_IN * w / sum(rel) for w in rel]
        t = new_table(self.doc, 1 + len(rows), widths)
        hdr = t.rows[0]
        row_flags(hdr, header=True)
        for j, name in enumerate(cols):
            c = hdr.cells[j]
            cell_fill(c, C_VERY_DARK)
            cell_margins(c, 100, 100)
            c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            spacing(p, 0, 0, 1.15)
            self.s.run(p, name, bold=True, color=C_WHITE)
        for i, row in enumerate(rows):
            tr = t.rows[i + 1]
            row_flags(tr)
            for j, val in enumerate(row):
                c = tr.cells[j]
                cell_fill(c, C_WHITE if i % 2 == 0 else C_ALT_ROW)
                c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                p = c.paragraphs[0]
                spacing(p, 0, 0, 1.15)
                if j in given:
                    cell_margins(c, 120 if self.teacher else 200, 120 if self.teacher else 200)
                    self._cell_text(p, val, bold=True, color=C_TEXT)
                elif self.teacher:
                    cell_margins(c, 120, 120)
                    self._cell_text(p, val, bold=True, color=C_DARK)
                    self.answers += 1
                else:
                    cell_margins(c, 420, 420)
                    self.s.run(p, "")
                    self.blanks += 1
        self.para(0, 6, 1.0)

    def _cell_text(self, p, val, bold, color):
        for k, part in enumerate(val.replace("\\n", "\n").split("\n")):
            if k:
                p.add_run().add_break()
            self.s.run(p, part, bold=bold, color=color)

    def examples(self, examples):
        self.heading("Examples to Explore", 2)
        for ex in examples:
            p = self.para(6, 2, 1.2)
            keep_next(p)
            self.s.run(p, ex["label"], bold=True, color=C_DARK)
            p = self.para(0, 4, 1.25)
            self.s.rich(p, ex["summary"])
            for prompt in ex.get("prompts") or []:
                p = self.doc.add_paragraph()
                Lists.apply(p, self.lists.bullet)
                spacing(p, 0, 3, 1.2)
                self.s.rich(p, prompt, color=C_MEDIUM)

    def review(self, lesson):
        self.heading("Lesson Review", 2)
        num_id = self.lists.new_review_list()
        for q in lesson["review"]:
            p = self.doc.add_paragraph()
            Lists.apply(p, num_id)
            spacing(p, 8, 4, 1.2)
            keep_next(p)
            self.s.rich(p, q["question"], bold=True)
            if self.teacher:
                t = new_table(self.doc, 1, [TEXT_WIDTH_IN], borders=False)
                c = t.cell(0, 0)
                cell_fill(c, C_CALLOUT)
                cell_margins(c, 120, 120, 140)
                row_flags(t.rows[0])
                cp = c.paragraphs[0]
                spacing(cp, 0, 0, 1.3)
                self.s.run(cp, "Suggested answer: ", bold=True, color=C_VERY_DARK)
                self.s.rich(cp, q["answer"], bold=True, color=C_DARK)
                self.para(0, 4, 1.0)
            else:
                n = q.get("lines", 3)
                for k in range(n):
                    lp = self.doc.add_paragraph()
                    spacing(lp, 0, 0, exact_pt=26)
                    rule_lines(lp)
                    self.s.run(lp, " ")
                    keep_next(lp, k < n - 1)

    def lesson(self, lesson, first):
        if not first and (lesson.get("page_break_before") or self.packet.get("lesson_page_breaks")):
            self.doc.add_page_break()
        p = self.para(0 if first else 14, 2, 1.2)
        keep_next(p)
        self.s.run(p, f"LESSON {lesson['number']} • {self.packet.get('course_label', self.packet['course'].upper())}",
                   bold=True, color=C_MEDIUM)
        self.heading(lesson["title"], 1)
        if not self.teacher:
            self.id_fields()
        # The lesson opening (label through learning targets) moves as one block.
        self.callout("Guiding question:", lesson["guiding_question"], C_GUIDING_Q)
        self.heading("Learning Targets", 2)
        for k, t in enumerate(lesson["targets"]):
            tp = self.doc.add_paragraph()
            Lists.apply(tp, self.lists.checkbox)
            spacing(tp, 0, 5, 1.15)
            keep_next(tp, k < len(lesson["targets"]) - 1)
            self.s.rich(tp, t)
        for sec in lesson["sections"]:
            self.section(sec)
        if lesson.get("examples"):
            self.examples(lesson["examples"])
        for org in lesson.get("organizers") or []:
            self.organizer(org)
        self.review(lesson)

    def build(self):
        self.title_page()
        for i, lesson in enumerate(self.lessons):
            self.lesson(lesson, i == 0)
        return self.doc


# ------------------------------------------------------------ output checks

def all_runs(doc):
    def walk(container):
        for p in container.paragraphs:
            yield from p.runs
        for t in getattr(container, "tables", []):
            for row in t.rows:
                for c in row.cells:
                    yield from walk(c)
    yield from walk(doc)
    for s in doc.sections:
        yield from walk(s.header)
        yield from walk(s.footer)


def all_text(doc):
    return "\n".join(r.text for r in all_runs(doc))


def check_output(student_path, teacher_path, lessons):
    problems = []
    docs = {"student": Document(student_path), "teacher": Document(teacher_path)}
    for name, d in docs.items():
        small = [r.text for r in all_runs(d) if r.font.size is not None and r.font.size.pt < MIN_PT]
        if small:
            problems.append(f"{name}: text below {MIN_PT} pt: {small[:3]}")
        text = all_text(d)
        if BLANK in text:
            problems.append(f"{name}: unreplaced blank marker")
        if SLIDE_REF.search(text):
            problems.append(f"{name}: a slide reference appears in the document")
        numbering = d.part.numbering_part.element
        tags = [el.tag for el in numbering if el.tag in (qn("w:abstractNum"), qn("w:num"))]
        if qn("w:num") in tags and qn("w:abstractNum") in tags[tags.index(qn("w:num")):]:
            problems.append(f"{name}: numbering definitions are out of order")
    heads = {n: [p.text for p in d.paragraphs if p.style.name.startswith("Heading")]
             for n, d in docs.items()}
    if heads["student"] != heads["teacher"]:
        problems.append("student and teacher section order differ")
    teacher_bold = {r.text for r in all_runs(docs["teacher"]) if r.bold}
    for lesson in lessons:
        for sec in lesson["sections"]:
            for n in sec["notes"]:
                for a in n.get("answers", []):
                    if a not in teacher_bold:
                        problems.append(f"teacher key is missing answer {a!r}")
    return problems


# ------------------------------------------------------------ pdf / render

def to_pdf(docx_path, out_dir):
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None, "LibreOffice not found; PDFs not created (export from Word instead)"
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run([soffice, f"-env:UserInstallation=file://{profile}", "--headless",
                        "--convert-to", "pdf", "--outdir", str(out_dir), str(docx_path)],
                       check=True, capture_output=True, timeout=180)
    pdf = out_dir / (docx_path.stem + ".pdf")
    return (pdf if pdf.exists() else None), None


def render_pages(pdf, render_dir):
    if not shutil.which("pdftoppm"):
        return "pdftoppm not found; page images not created"
    render_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["pdftoppm", "-r", "70", "-png", str(pdf), str(render_dir / pdf.stem)],
                   check=True, capture_output=True, timeout=180)
    return None


def pdf_pages(pdf):
    try:
        out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
        m = re.search(r"Pages:\s+(\d+)", out)
        return int(m.group(1)) if m else None
    except FileNotFoundError:
        return None


# ------------------------------------------------------------ main

def output_paths(out_dir, stem, overwrite):
    candidate, n = stem, 2
    while not overwrite and any((out_dir / f"{candidate}_{k}.{e}").exists()
                                for k in ("Student", "Teacher_Key") for e in ("docx", "pdf")):
        candidate, n = f"{stem}_r{n}", n + 1
    return {k: out_dir / f"{candidate}_{k}.docx" for k in ("Student", "Teacher_Key")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("packet", help="packet JSON file")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--pdf", action="store_true", help="also export PDFs with LibreOffice")
    ap.add_argument("--render-dir", help="write PNG page images here for visual inspection (implies --pdf)")
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)

    data = json.loads(Path(args.packet).read_text(encoding="utf-8"))
    try:
        packet, lessons, warnings = validate(data)
    except ContentError as e:
        print("CONTENT NEEDS FIXING:")
        for line in str(e).splitlines():
            print("  - " + line)
        return 1
    for w in warnings:
        print("Note: " + w)
    if args.validate_only:
        print("Content validation passed")
        return 0

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = output_paths(out_dir, packet["output_stem"], args.overwrite)

    counts = {}
    for key, teacher in (("Student", False), ("Teacher_Key", True)):
        b = Builder(packet, lessons, teacher)
        b.build().save(paths[key])
        counts[key] = b.answers if teacher else b.blanks
    problems = check_output(paths["Student"], paths["Teacher_Key"], lessons)
    if counts["Student"] != counts["Teacher_Key"]:
        problems.append(f"{counts['Student']} student blanks but {counts['Teacher_Key']} teacher answers")
    if problems:
        print("OUTPUT CHECK FAILED:")
        for p in problems:
            print("  - " + p)
        return 2

    print(f"Student packet: {paths['Student']}")
    print(f"Teacher key:    {paths['Teacher_Key']}")
    print(f"Blanks and organizer cells: {counts['Student']} (all answered in the key)")

    if args.pdf or args.render_dir:
        for key in ("Student", "Teacher_Key"):
            pdf, err = to_pdf(paths[key], out_dir)
            if err:
                print("Limitation: " + err)
                break
            pages = pdf_pages(pdf)
            print(f"PDF: {pdf}" + (f" ({pages} pages)" if pages else ""))
            if args.render_dir:
                err = render_pages(pdf, Path(args.render_dir))
                if err:
                    print("Limitation: " + err)
        print("Note: LibreOffice substitutes fonts it does not have (such as Aptos). "
              "Check final pagination in Word when possible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
