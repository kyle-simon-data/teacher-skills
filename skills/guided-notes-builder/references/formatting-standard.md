# Guided notes formatting standard

The full specification `scripts/build_notes.py` implements. Use it when changing the script, checking a packet by hand, or diagnosing a layout problem.

## Goals

A classroom-ready student packet and matching teacher key that:

- follow the instructional sequence of the sources
- give enough context for students to complete every blank
- explicitly cover every concept on an accompanying test
- print cleanly in grayscale and photocopy well
- leave generous handwriting space
- never mention slides, slide numbers or "student-facing" material

## Page setup

| Setting | Value |
|---|---|
| Page | US Letter, portrait |
| Margins | top 0.70 in, bottom 0.65 in, left and right 0.75 in |
| Header and footer distance | 0.30 in |

No fixed-height rows or elements that can clip text; paragraphs, tables and cells grow with their content.

## Typography

| Element | Style |
|---|---|
| Packet title | 28 pt bold Aptos Display |
| Lesson title | 18 pt bold Aptos Display |
| Major heading | 14 pt bold Aptos Display |
| Minor heading (organizers) | 11.5 pt bold Aptos |
| Body and cloze text | 10.5 pt Aptos |
| Teacher answers | 10.5 pt bold, dark gray |
| Code | Courier New, at least 10.5 pt |

Nothing anywhere, including tables, headers, footers and teacher answers, is smaller than 10.5 pt.

## Grayscale palette

| Role | Hex |
|---|---|
| Main headings, table headers | `#202020` |
| Secondary emphasis, teacher answers | `#3F3F3F` |
| Supporting text | `#595959` |
| Alternating table rows, code blocks | `#F2F2F2` |
| Directions callout, teacher answer areas | `#EEEEEE` |
| Guiding-question callout | `#E7E7E7` |
| Main text | `#111111` |
| Table-header text | `#FFFFFF` |

## Title page

Centered, with generous white space, in this order:

1. Course label
2. Packet title
3. Unit or chapter subtitle
4. Student: `[Unit] - Guided Notes Packet`; teacher: `TEACHER ANSWER KEY`
5. Student: Name, Class and Date fields; teacher: `Completed answers appear in bold dark-gray text.`
6. A one- or two-sentence overview naming the actual topics and what students will be able to do afterward
7. Packet contents (one line per lesson)

No decorative rules.

## Headers and footers

- Student header, right-aligned: `[Course] • Guided Notes`
- Teacher header, right-aligned: `[Course] • Teacher Key`
- Footer, centered: `[Course] • [Unit] | [page]`, using an automatic page-number field

## Lesson structure

1. Small label: `LESSON 2.1 • [COURSE]`
2. Lesson title
3. Name, Class and Date fields (student only)
4. Full-width light-gray guiding-question callout
5. Learning targets with square checkboxes
6. Guided notes under descriptive headings
7. Organizers, when useful
8. Lesson review

## Page flow

- Lessons, sections, organizers and reviews flow naturally. Don't force each onto a new page; break only to prevent crowding or an awkward split.
- Avoid significant unused space at the bottom of instructional pages. The title page and final page may have white space.
- Keep a section heading with at least two note statements. No single orphan line or isolated final statement on either side of a page break.
- Use widow/orphan control and targeted keep-with-next rather than keeping whole sections together.
- Keep each review question with its writing lines, and keep each teacher answer area whole.
- Organizer tables may continue across pages, with a repeated header row and rows that never split.
- Student and teacher versions keep the same section order. Similar pagination is nice, but don't add blank space to force it.

## Lists

- Learning targets: real Word list, Aptos square checkbox `☐`
- Notes statements: real Word list, Aptos dot bullet `•`
- Review questions: real Word decimal numbering, restarting for each lesson
- Wrapped lines align under the text with a hanging indent
- Never type bullet characters into ordinary paragraphs
- In numbering.xml, every abstract numbering definition comes before every concrete numbering instance; each list is single-level with a unique identifier. (Word interprets malformed definitions differently from other renderers.)

## Student term blanks

Visible underscore blanks in the sentence, in the body font, about 30 percent longer than the answer needs:

```text
base  = clamp(answer character count + 4, minimum 10, maximum 30)
blank = round(base × 1.30)        # 13 to 39 underscores
```

- Near-black underscores
- The blank stays in its sentence and wraps naturally; never shrink the font to fit it
- Don't place a blank directly against letters or punctuation that handwriting would collide with
- Cloze paragraphs: 1.5 line spacing, about 2 pt before and 7 pt after

## Code and technical notation

- Preserve exact syntax, indentation and operators
- Literal code in a readable monospace font (Courier New), at least 10.5 pt
- Student blanks stay in the body font, even when the answer is code
- Distinguish code from prose without relying on color
- Examples match between student and teacher versions; never invent output for incomplete or ambiguous code

## Teacher key

- Every student blank replaced with the exact answer, in bold dark gray
- The same wording, order, headings and bullets as the student packet
- Every organizer cell completed
- A suggested answer directly beneath every review question

## Organizers

- Full text width, with intentional column widths
- Very dark gray header row with centered bold white text, repeated on each page
- Alternating white and very light gray rows, content vertically centered
- Generous top and bottom padding in the student version for handwriting; compact but readable in the teacher version
- Rows never split across pages

## Review

- Numbered with real Word numbering
- Students get about three ruled lines per question (more or fewer as the expected answer requires). Lines run the full text width, margin to margin, using paragraph borders rather than fixed-length underscores
- Teacher version: a light-gray suggested-answer area directly beneath each question, never split across pages

## Quality checklist

Content:

- Only the requested scope; topics in source order
- No slide references
- Every blank has a teacher answer; every organizer cell is completed
- Review questions are answerable from the notes
- With a test: every question explicitly covered

Formatting:

- Checkboxes for targets, dot bullets for notes
- Blanks follow the sizing rule; nothing below 10.5 pt
- No awkward table or answer-area splits, orphaned headings, nearly empty accidental pages, clipped or overlapping text, or missing glyphs
- Matching section order in both versions
- The overview names the real topics and capabilities
- Review lines reach the right margin
- No significant unused bottom space on instructional pages, and no unnecessary forced breaks

Render:

1. Export both documents to PDF and page images
2. Inspect every page at a readable size
3. Fix any overflow, clipping, awkward wrapping, split answer area or bad break
4. Rebuild and re-inspect after every fix
5. Deliver only the final .docx and PDF files

## Renderer notes

- LibreOffice substitutes fonts it doesn't have (Aptos is bundled with Microsoft 365), so page breaks can differ from Word. Check final pagination in Word when possible.
- In LibreOffice, an empty paragraph between a table and a keep-with-next heading breaks the keep chain. The builder therefore puts no spacer paragraph after the guiding-question callout.
- Consecutive tables with no paragraph between them merge into one table in Word, so the builder keeps a small spacer paragraph after code blocks, organizers and teacher answer areas.
