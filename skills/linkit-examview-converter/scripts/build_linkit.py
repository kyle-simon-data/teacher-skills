#!/usr/bin/env python3
"""Build a LinkIt "Exam View" upload package and companion matrix.

Input: a questions JSON file in the canonical structure described in
SKILL.md. Output (written to --out-dir):

  <title>_linkit.zip              Blackboard pool package for LinkIt's Exam View button
  <title>_companion_matrix.csv    every source question, imported or not

Standard library only. Python 3.8 or newer.

Usage:
  python build_linkit.py questions.json --out-dir OUTPUT_DIR [--overwrite]

Exit codes: 0 success, 1 input needs clarification, 2 validation failure.
"""

import argparse
import csv
import io
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from html import escape as html_escape
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape
import xml.etree.ElementTree as ET

VALID_TYPES = {
    "multiple_choice", "multiple_response", "true_false", "fill_in_blank",
    "matching", "ordering", "inline_choice", "essay",
}
MANUAL_TYPES = {"multiple_response", "fill_in_blank", "ordering", "inline_choice", "essay"}
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
MATRIX_COLUMNS = [
    "Question Number", "Question Text", "Option A", "Option B", "Option C",
    "Option D", "Correct Answer", "Additional Options", "LinkIt Status",
]


class ClarificationNeeded(Exception):
    """Raised when the source must be fixed or clarified before building."""


# ---------------------------------------------------------------- helpers

def snake_case(title):
    s = re.sub(r"[^0-9A-Za-z]+", "_", title).strip("_").lower()
    return s or "assessment"


def cdata(text, is_html=False):
    body = text if is_html else html_escape(text, quote=False)
    return "<![CDATA[" + body.replace("]]>", "]]]]><![CDATA[>") + "]]>"


def attr(text):
    return xml_escape(text, {'"': "&quot;"})


def unique_path(path, overwrite):
    if overwrite or not path.exists():
        return path
    n = 2
    while True:
        candidate = path.with_name(f"{path.stem}_r{n}{path.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def as_correct_list(q):
    c = q.get("correct")
    if c is None:
        return []
    if isinstance(c, int):
        return [c]
    return list(c)


# ---------------------------------------------------------- normalization

def normalize(data):
    """Split source questions into an import list and a manual list."""
    title = str(data.get("title") or "").strip()
    if not title:
        raise ClarificationNeeded("The questions file has no title.")
    questions = data.get("questions") or []
    if not questions:
        raise ClarificationNeeded("The questions file has no questions.")

    imports, manual, notes = [], [], []

    for idx, q in enumerate(questions):
        src = q.get("source_number", idx + 1)
        qtype = q.get("type", "multiple_choice")
        text = str(q.get("text", "")).strip()
        is_html = bool(q.get("html", False))
        points = q.get("points", 1)
        choices = [str(c) for c in q.get("choices", [])]
        correct = as_correct_list(q)

        if qtype not in VALID_TYPES:
            raise ClarificationNeeded(f"Source question {src}: unknown type '{qtype}'.")
        if not text:
            raise ClarificationNeeded(f"Source question {src}: question text is empty.")
        if "shuffle" in q:
            notes.append(f"Source question {src}: shuffle setting ignored (this format has none).")

        def to_manual(reason):
            manual.append({"src": src, "type": qtype, "text": text, "choices": choices,
                           "correct": correct, "pairs": q.get("pairs"),
                           "answer": q.get("answer"), "reason": reason})

        if qtype in MANUAL_TYPES:
            to_manual(f"{qtype} cannot be imported")
            continue

        if qtype == "true_false":
            ans = q.get("answer")
            if isinstance(ans, bool):
                k = 0 if ans else 1
            elif len(correct) == 1 and correct[0] in (0, 1):
                k = correct[0]
            else:
                choices = ["True", "False"]
                to_manual("no correct answer provided")
                notes.append(f"Source question {src}: no correct answer; listed for manual entry.")
                continue
            imports.append({"src": src, "text": text, "choices": ["True", "False"],
                            "correct": k, "points": points, "html": is_html,
                            "status": "Imported (true/false as two-choice multiple choice)"})
            continue

        if qtype == "multiple_choice":
            if len(choices) < 2:
                raise ClarificationNeeded(
                    f"Source question {src}: multiple choice needs at least 2 choices.")
            if not correct:
                to_manual("no correct answer provided")
                notes.append(f"Source question {src}: no correct answer; listed for manual entry.")
                continue
            if len(correct) > 1:
                qtype = "multiple_response"
                to_manual("more than one correct answer (multiple_response) cannot be imported")
                continue
            k = correct[0]
            if not 0 <= k < len(choices):
                raise ClarificationNeeded(
                    f"Source question {src}: correct index {k} is outside the choice list.")
            if len(choices) > 5:
                notes.append(f"Source question {src}: {len(choices)} choices; only 2-5 "
                             "choices have been confirmed to import correctly.")
            imports.append({"src": src, "text": text, "choices": choices, "correct": k,
                            "points": points, "html": is_html, "status": "Imported"})
            continue

        if qtype == "matching":
            pairs = q.get("pairs") or []
            if any(len(p) != 2 or not str(p[0]).strip() or not str(p[1]).strip() for p in pairs):
                raise ClarificationNeeded(
                    f"Source question {src}: every matching pair needs a left and a right entry "
                    "(unequal columns must be resolved first).")
            if len(pairs) < 3:
                to_manual("matching with fewer than 3 pairs is not converted")
                notes.append(f"Source question {src}: matching has fewer than 3 pairs; "
                             "listed for manual entry.")
                continue
            imports.extend(convert_matching(src, text, pairs, is_html))
            continue

    return title, imports, manual, notes


def convert_matching(src, prompt, pairs, is_html):
    lefts = [str(p[0]) for p in pairs]
    rights = [str(p[1]) for p in pairs]
    n = len(pairs)
    rotated = rights[1:] + rights[:1]
    items = []
    for i, left in enumerate(lefts):
        p = (i - 1) % n  # position of rights[i] in the rotated list
        if n <= 5:
            choices, correct = list(rotated), p
        else:
            window = sorted((p + j) % n for j in range(5))
            choices, correct = [rotated[j] for j in window], window.index(p)
        items.append({
            "src": src, "text": f"{prompt} {left}", "choices": choices,
            "correct": correct, "points": 1, "html": is_html,
            "status": f"Imported (converted from matching, source question {src})",
            "matching_left": left, "matching_right": rights[i],
        })
    return items


# ----------------------------------------------------------------- output

def build_manifest(title):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<manifest identifier="man00001">\n'
        '  <organization default="toc00001">\n'
        '    <tableofcontents identifier="toc00001"/>\n'
        '  </organization>\n'
        '  <resources>\n'
        '    <resource baseurl="res00001" file="res00001.dat" identifier="res00001" '
        'type="assessment/x-bb-pool">\n'
        f'      <title>{xml_escape(title)}</title>\n'
        '    </resource>\n'
        '  </resources>\n'
        '</manifest>\n'
    )


def build_pool(title, items):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<POOL>",
        '  <COURSEID value="IMPORT"/>',
        f'  <TITLE value="{attr(title)}"/>',
        "  <DESCRIPTION>",
        "    <TEXT></TEXT>",
        "  </DESCRIPTION>",
        "  <DATES>",
        f'    <CREATED value="{stamp}"/>',
        f'    <UPDATED value="{stamp}"/>',
        "  </DATES>",
        "  <QUESTIONLIST>",
    ]
    for n, it in enumerate(items, 1):
        out.append(f'    <QUESTION id="q{n}" class="QUESTION_MULTIPLECHOICE" '
                   f'points="{attr(str(it["points"]))}"/>')
    out.append("  </QUESTIONLIST>")
    for n, it in enumerate(items, 1):
        out += [
            f'  <QUESTION_MULTIPLECHOICE id="q{n}">',
            "    <BODY>",
            f'      <TEXT>{cdata(it["text"], it["html"])}</TEXT>',
            "      <FLAGS>",
            '        <ISHTML value="true"/>',
            '        <ISNEWLINELITERAL value="false"/>',
            "      </FLAGS>",
            "    </BODY>",
        ]
        for k, choice in enumerate(it["choices"], 1):
            out += [
                f'    <ANSWER id="q{n}_a{k}" position="{k}">',
                f"      <TEXT>{cdata(choice, it['html'])}</TEXT>",
                "    </ANSWER>",
            ]
        out += [
            "    <GRADABLE>",
            f'      <CORRECTANSWER answer_id="q{n}_a{it["correct"] + 1}"/>',
            "      <FEEDBACK_WHEN_CORRECT></FEEDBACK_WHEN_CORRECT>",
            "      <FEEDBACK_WHEN_INCORRECT></FEEDBACK_WHEN_INCORRECT>",
            "    </GRADABLE>",
            "  </QUESTION_MULTIPLECHOICE>",
        ]
    out.append("</POOL>")
    return "\n".join(out) + "\n"


def option_cells(choices):
    first = [f"{c}" for c in choices[:4]] + [""] * (4 - min(4, len(choices)))
    extra = "; ".join(f"{LETTERS[i]}. {c}" for i, c in enumerate(choices[4:], 4))
    return first, extra


def manual_answer(m):
    if m.get("pairs"):
        return "; ".join(f"{p[0]} = {p[1]}" for p in m["pairs"])
    if m["choices"] and m["correct"]:
        return ", ".join(LETTERS[k] for k in m["correct"] if 0 <= k < len(m["choices"]))
    if m.get("answer") not in (None, ""):
        return str(m["answer"])
    return "(none provided)"


def build_matrix(imports, manual):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(MATRIX_COLUMNS)
    for n, it in enumerate(imports, 1):
        opts, extra = option_cells(it["choices"])
        w.writerow([n, it["text"], *opts, LETTERS[it["correct"]], extra, it["status"]])
    for m in manual:
        opts, extra = option_cells(m["choices"])
        w.writerow(["", m["text"], *opts, manual_answer(m), extra,
                    f"Not imported - enter manually ({m['type']}, source question {m['src']})"])
    return buf.getvalue()


# ------------------------------------------------------------- validation

def validate_zip(zip_path, imports):
    errors = []
    with zipfile.ZipFile(zip_path) as zf:
        names = sorted(zf.namelist())
        if names != ["imsmanifest.xml", "res00001.dat"]:
            errors.append(f"zip must contain exactly imsmanifest.xml and res00001.dat, found {names}")
            return errors
        raw_manifest = zf.read("imsmanifest.xml").decode("utf-8")
        raw_pool = zf.read("res00001.dat").decode("utf-8")

    for name, raw in (("imsmanifest.xml", raw_manifest), ("res00001.dat", raw_pool)):
        if not raw.startswith('<?xml version="1.0" encoding="UTF-8"?>'):
            errors.append(f"{name}: missing UTF-8 XML declaration")
    try:
        manifest = ET.fromstring(raw_manifest)
        pool = ET.fromstring(raw_pool)
    except ET.ParseError as e:
        return errors + [f"XML is not well formed: {e}"]

    res = manifest.find("./resources/resource")
    if res is None or res.get("type") != "assessment/x-bb-pool" or \
            res.get("file") != "res00001.dat" or res.get("baseurl") != "res00001":
        errors.append("manifest resource attributes are wrong")

    question_tags = {el.tag for el in pool if el.tag.startswith("QUESTION_")}
    if question_tags - {"QUESTION_MULTIPLECHOICE"}:
        errors.append(f"non-multiple-choice blocks present: {question_tags}")

    list_ids = [q.get("id") for q in pool.findall("./QUESTIONLIST/QUESTION")]
    blocks = pool.findall("./QUESTION_MULTIPLECHOICE")
    block_ids = [b.get("id") for b in blocks]
    expected = [f"q{n}" for n in range(1, len(imports) + 1)]
    if list_ids != expected or block_ids != expected:
        errors.append("QUESTIONLIST ids and block ids must both run q1..qN in order")
    for q in pool.findall("./QUESTIONLIST/QUESTION"):
        if q.get("class") != "QUESTION_MULTIPLECHOICE":
            errors.append(f"{q.get('id')}: QUESTIONLIST class is not QUESTION_MULTIPLECHOICE")

    all_ids = set()
    for n, (b, it) in enumerate(zip(blocks, imports), 1):
        answers = b.findall("./ANSWER")
        ids = [a.get("id") for a in answers]
        if ids != [f"q{n}_a{k}" for k in range(1, len(answers) + 1)]:
            errors.append(f"q{n}: choice ids are not sequential")
        if len(answers) < 2:
            errors.append(f"q{n}: fewer than 2 choices")
        if all_ids & set(ids):
            errors.append(f"q{n}: duplicate ids")
        all_ids.update(ids)
        cas = b.findall("./GRADABLE/CORRECTANSWER")
        if len(cas) != 1 or cas[0].get("answer_id") not in ids:
            errors.append(f"q{n}: needs exactly one CORRECTANSWER pointing at its own choice")
        elif cas[0].get("answer_id") != f"q{n}_a{it['correct'] + 1}":
            errors.append(f"q{n}: correct answer does not match the source")
        texts = [a.findtext("TEXT") for a in answers]
        if texts != [html_escape(c, quote=False) if not it["html"] else c for c in it["choices"]]:
            errors.append(f"q{n}: choice text does not round-trip")
        if it["status"].startswith("Imported (true/false") and texts != ["True", "False"]:
            errors.append(f"q{n}: true/false choices must be True then False")

    for m in re.finditer(r"<TEXT>(.*?)</TEXT>", raw_pool, re.S):
        if m.group(1) and not m.group(1).startswith("<![CDATA["):
            errors.append("a TEXT element with content is not wrapped in CDATA")
            break
    return errors


# ------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("questions", help="questions JSON file")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--overwrite", action="store_true",
                    help="replace existing outputs instead of adding a _r2, _r3 suffix")
    args = ap.parse_args(argv)

    data = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    try:
        title, imports, manual, notes = normalize(data)
    except ClarificationNeeded as e:
        print(f"NEEDS CLARIFICATION: {e}")
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = snake_case(title)

    matrix_path = unique_path(out_dir / f"{stem}_companion_matrix.csv", args.overwrite)
    matrix_path.write_text(build_matrix(imports, manual), encoding="utf-8", newline="")

    zip_path = None
    if imports:
        zip_path = unique_path(out_dir / f"{stem}_linkit.zip", args.overwrite)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("imsmanifest.xml", build_manifest(title))
            zf.writestr("res00001.dat", build_pool(title, imports))
        errors = validate_zip(zip_path, imports)
        if errors:
            print("VALIDATION FAILED:")
            for e in errors:
                print("  - " + e)
            return 2

    source_total = len(data["questions"])
    accounted = len({it["src"] for it in imports}) + len(manual)
    if accounted != source_total:
        print(f"VALIDATION FAILED: {accounted} of {source_total} source questions accounted for")
        return 2

    matching_items = [it for it in imports if "matching_left" in it]
    print(f"Title: {title}")
    print(f"Zip: {zip_path if zip_path else '(none - nothing importable)'}")
    print(f"Companion matrix: {matrix_path}")
    print(f"Items in zip: {len(imports)}")
    print(f"Items converted from matching: {len(matching_items)}")
    print(f"Source questions left for manual entry: {len(manual)}")
    print(f"Source questions accounted for: {accounted} of {source_total}")
    if matching_items:
        print("Matching check (left entry -> answer the key resolves to):")
        for it in matching_items:
            resolved = it["choices"][it["correct"]]
            flag = "" if resolved == it["matching_right"] else "   <-- MISMATCH"
            print(f"  Q{it['src']}: {it['matching_left']} -> {resolved}{flag}")
    for n in notes:
        print("Note: " + n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
