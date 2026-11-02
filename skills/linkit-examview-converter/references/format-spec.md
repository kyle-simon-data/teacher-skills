# LinkIt Exam View package format

Reference for maintaining `scripts/build_linkit.py` or diagnosing an upload problem. Routine conversions do not need this file.

## Observed LinkIt behavior

Confirmed by test uploads in October 2026. LinkIt can change without notice; retest after any failure.

| Behavior | Consequence |
|---|---|
| Only `QUESTION_MULTIPLECHOICE` blocks are imported | Every item is a multiple-choice block |
| Other block types are skipped silently, with no error | Never write true/false, multiple-answer, fill-in-blank, matching or essay blocks |
| Text outside a CDATA section imports as blank | Every `<TEXT>` element with content is wrapped in CDATA |
| CDATA content is displayed as HTML | Literal `<`, `>` and `&` are HTML-escaped inside the CDATA |
| Items appear in file order; the key shows a letter by position | Write items and choices in the intended order |
| 2-5 choices per item import correctly | Do not pad or trim choice lists |
| `points` in `QUESTIONLIST` is honored | Write the real point value |
| `<b>` and `<br/>` render; `<code>` renders in pink monospace | Use `<code>` only when commands should be set apart |
| A `<p>` wrapper adds a blank line | Do not wrap text in `<p>` |
| The QTI button rejects the package with a manifest error | Upload with the Exam View button |

## Package layout

A zip with exactly two files in its root, both UTF-8 and starting with `<?xml version="1.0" encoding="UTF-8"?>`. No subdirectories, namespaces, schema locations or DOCTYPE.

| File | Contents |
|---|---|
| `imsmanifest.xml` | Manifest pointing at the pool |
| `res00001.dat` | The question pool |

### imsmanifest.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="man00001">
  <organization default="toc00001">
    <tableofcontents identifier="toc00001"/>
  </organization>
  <resources>
    <resource baseurl="res00001" file="res00001.dat" identifier="res00001" type="assessment/x-bb-pool">
      <title>{assessment_title, XML-escaped}</title>
    </resource>
  </resources>
</manifest>
```

### res00001.dat

```xml
<?xml version="1.0" encoding="UTF-8"?>
<POOL>
  <COURSEID value="IMPORT"/>
  <TITLE value="{assessment_title, attribute-escaped}"/>
  <DESCRIPTION>
    <TEXT></TEXT>
  </DESCRIPTION>
  <DATES>
    <CREATED value="2026-10-09 15:45:00Z"/>
    <UPDATED value="2026-10-09 15:45:00Z"/>
  </DATES>
  <QUESTIONLIST>
    <QUESTION id="q1" class="QUESTION_MULTIPLECHOICE" points="1"/>
  </QUESTIONLIST>
  <QUESTION_MULTIPLECHOICE id="q1">
    <BODY>
      <TEXT><![CDATA[Question stem]]></TEXT>
      <FLAGS>
        <ISHTML value="true"/>
        <ISNEWLINELITERAL value="false"/>
      </FLAGS>
    </BODY>
    <ANSWER id="q1_a1" position="1">
      <TEXT><![CDATA[Choice one]]></TEXT>
    </ANSWER>
    <ANSWER id="q1_a2" position="2">
      <TEXT><![CDATA[Choice two]]></TEXT>
    </ANSWER>
    <GRADABLE>
      <CORRECTANSWER answer_id="q1_a2"/>
      <FEEDBACK_WHEN_CORRECT></FEEDBACK_WHEN_CORRECT>
      <FEEDBACK_WHEN_INCORRECT></FEEDBACK_WHEN_INCORRECT>
    </GRADABLE>
  </QUESTION_MULTIPLECHOICE>
</POOL>
```

Identifiers are sequential: item `n` is `q{n}`, its choice `k` is `q{n}_a{k}`. `QUESTIONLIST` and the blocks list the same ids in the same order. A literal `]]>` in text is written as `]]]]><![CDATA[>`.

## Conversions

**True/false:** two answers, `True` (`a1`) then `False` (`a2`); the correct answer points at the matching one. A `QUESTION_TRUEFALSE` block is skipped by LinkIt.

**Matching** with N pairs (N ≥ 3; fewer pairs go to manual entry):

1. Choice list = right-side entries rotated by one: right 2, right 3, …, right N, right 1.
2. One item per left entry, in order. Stem = matching prompt + space + left text.
3. N ≤ 5: every item uses the full rotated list. N > 5: each item uses 5 choices, its own correct entry plus the next 4 in the rotated list (wrapping), kept in rotated-list order.
4. Each converted item is worth 1 point.

For N > 5, keeping rotated-list order means the correct answer is often in position A. Review the companion matrix if answer-position balance matters.

## Companion matrix columns

`Question Number, Question Text, Option A, Option B, Option C, Option D, Correct Answer, Additional Options, LinkIt Status`

Imported items come first, numbered in file order, with the answer as a letter; choices past D go in `Additional Options` as `E. text; F. text`. Manual items follow with a blank number and status `Not imported - enter manually ({type}, source question N)`.
