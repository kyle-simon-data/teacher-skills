# Guided Notes Builder

An [Agent Skill](https://agentskills.io) that turns lesson slides into a print-ready guided-notes packet for students and a matching teacher answer key, in Word and PDF.

Give your AI assistant a slide deck (or other lesson materials), tell it the course and unit, and optionally attach the unit test. It writes the notes and produces:

- **`..._Student.docx` / `.pdf`**: fill-in-the-blank notes, organizers with room to write, and a lesson review with ruled lines
- **`..._Teacher_Key.docx` / `.pdf`**: the same packet with every answer filled in

## What the packets look like

- A title page with the unit overview and contents
- For each lesson: a guiding question, checkbox learning targets, and cloze notes under headings that follow the order of your slides
- Blanks sized to the answer (about 30% longer than the word needs) so students have room to write
- Optional comparison organizers, code examples in a monospace font, and a numbered review with full-width writing lines
- Grayscale throughout, so it photocopies cleanly
- Real Word lists and headings, so you can still edit the packet in Word afterward

## Covering the test

Attach the unit test and the AI checks every question against the notes before building. It adds missing material where the topic is taught, not as a separate "test facts" list. Anything the test asks that your slides never teach is flagged for you rather than made up.

## Install

**Claude (web, desktop or mobile):** download this folder and zip it, keeping the folder name `guided-notes-builder`. Then go to **Customize → Skills**, click **+**, choose **Create skill → Upload a skill**, and select the zip. Code execution must be turned on in your settings.

**Claude Code:** copy this folder into `~/.claude/skills/` (for you) or `.claude/skills/` (for one project).

**Other tools:** any AI tool that supports the Agent Skills format can use the folder as is.

Then ask something like: *"Make guided notes and a teacher key from these slides for Unit 3. Here's the unit test too."*

## Using the script directly

The builder needs Python 3.8+ and `python-docx`. PDF export and page previews also need LibreOffice and poppler (`pdftoppm`).

```bash
pip install python-docx
python scripts/build_notes.py examples/sample_packet.json --out-dir output --render-dir output/pages
```

Packet content is plain JSON, so nothing in your curriculum is ever run as code. See [`examples/sample_packet.json`](examples/sample_packet.json) and [`SKILL.md`](SKILL.md) for the format. Existing files are never overwritten; new versions get `_r2`, `_r3` suffixes.

Run the tests from this folder with:

```bash
python -m unittest discover tests
```

## Limitations

- Packets use Aptos, which comes with Microsoft 365. Without it, another font is substituted and page breaks can shift. Check the final layout in Word.
- The script checks structure, answers and formatting. Accuracy and source coverage depend on the AI's reading of your materials, so review the teacher key before printing.
- Layout is designed for US Letter paper.

## Folder layout

```text
SKILL.md                          instructions the AI follows
scripts/build_notes.py            builds, checks and renders the packet
references/formatting-standard.md full formatting specification
examples/sample_packet.json
tests/test_build_notes.py
```

Part of [teacher-skills](../../README.md). MIT licensed.
