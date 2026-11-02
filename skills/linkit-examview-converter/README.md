# LinkIt Exam View Converter

An [Agent Skill](https://agentskills.io) that turns an existing test and answer key into a file LinkIt! can import, so teachers don't have to retype questions by hand.

Give your AI assistant a test in almost any format (a Word document, a PDF, pasted text, a numbered list) and it produces:

- **`<title>_linkit.zip`**, uploaded to a LinkIt item set with the **Exam View** button
- **`<title>_companion_matrix.csv`**, a spreadsheet listing every question, its answer, and whether it was imported or needs manual entry

## Why this exists

LinkIt's Exam View import accepts a Blackboard pool package, the format ExamView exports for Blackboard 6.0-7.0. Test uploads showed some behavior that isn't documented anywhere obvious:

- Only multiple-choice items import. Other item types are **skipped silently**, with no error.
- Text that isn't wrapped in a CDATA section imports as **blank**.
- The **QTI** button rejects the file. The **Exam View** button accepts it.

This skill handles all of that. True/false questions become two-choice multiple choice. Matching questions become one multiple-choice item per term. Anything that can't be imported (essay, fill in the blank, multiple response, ordering) is listed in the companion matrix so nothing gets lost.

## What gets imported

| Question type | Result |
|---|---|
| Multiple choice (one answer, 2-5 choices) | Imported |
| True/false | Imported as two-choice multiple choice |
| Matching (3 or more pairs) | One 1-point item per term |
| Multiple response, fill in the blank, ordering, inline choice, essay | Listed for manual entry |
| Questions with no answer key | Listed for manual entry |

Note that matching items are worth 1 point each, so a test's point total can change.

## Install

**Claude (web, desktop or mobile):** download this folder and zip it, keeping the folder name `linkit-examview-converter`. Then go to **Customize → Skills**, click **+**, choose **Create skill → Upload a skill**, and select the zip. Code execution must be turned on in your settings.

**Claude Code:** copy this folder into `~/.claude/skills/` (for you) or `.claude/skills/` (for one project).

**Other tools:** any AI tool that supports the Agent Skills format can use the folder as is.

Then ask something like: *"Convert this test and answer key for LinkIt."*

## Using the script directly

The build script uses only the Python standard library (Python 3.8+):

```bash
python scripts/build_linkit.py questions.json --out-dir output
```

See [`examples/sample_questions.json`](examples/sample_questions.json) for the input format. Existing output files are never overwritten; new versions get `_r2`, `_r3` suffixes.

Run the tests from this folder with:

```bash
python -m unittest discover tests
```

## Limitations

- Import behavior was confirmed by test uploads in October 2026. LinkIt may change; if an upload fails, please open an issue.
- Local validation confirms the file matches the tested format. It can't guarantee LinkIt will accept it.
- The skill converts existing tests. It doesn't write questions.
- Review the companion matrix before giving the test, especially converted matching items.

## Folder layout

```text
SKILL.md                     instructions the AI follows
scripts/build_linkit.py      builds and validates the zip and matrix
references/format-spec.md    file format and observed LinkIt behavior
examples/sample_questions.json
tests/test_build_linkit.py
```

Part of [teacher-skills](../../README.md). MIT licensed. Not affiliated with or endorsed by LinkIt!, ExamView or Blackboard. Product names belong to their owners.
