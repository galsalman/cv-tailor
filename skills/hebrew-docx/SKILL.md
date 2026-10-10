---
name: hebrew-docx
description: Rules and helpers for Hebrew and mixed Hebrew/English Word (.docx) files built with python-docx — paragraph direction, per-script runs, brackets, numbers, complex-script fonts — verified against Microsoft Word rather than theory. Use whenever cv-tailor builds or edits a Hebrew CV, or when a Hebrew .docx looks fine elsewhere but comes out scrambled in Word (English on the wrong side, mirrored brackets, reversed numbers).
---

# Hebrew DOCX (python-docx + Microsoft Word)

Adapted from the `hebrew-document-generator` skill by skills-il (MIT license), narrowed to
DOCX and corrected after a long debugging session on real CV content. Where this file and the
original disagree, this file wins: its rules were confirmed by rendering variants in Word and
checking them by eye.

The helpers live in `scripts/rtl.py`. Use `add_para()` for every paragraph. Don't re-derive it.

## The rules

1. **Paragraph direction.** Any paragraph containing a Hebrew letter gets `<w:bidi/>`. A
   paragraph with Latin text and no Hebrew is LTR and left-aligned. An all-neutral paragraph
   (digits/punctuation) defaults to RTL in a Hebrew document.
2. **Split every line into runs by script.** Hebrew letters in one run, Latin letters and
   digits in another. Spaces and punctuation attach to the current run. Never put a whole
   mixed line in one run.
3. **Flag `<w:rtl/>` on every Hebrew run, unconditionally**, even when the paragraph also
   contains English. *This contradicts the original skill*, which said never to flag rtl in a
   mixed paragraph. That gate broke multi-clause lines such as `X | Y (SAP), Z`: Word
   reordered the clauses around the `|`. Unconditional rtl + rule 4 renders them correctly.
4. **Move brackets across a direction boundary, in both directions.** An opening bracket at the
   end of a run moves into the next run, and a closing bracket at the start of a run moves into
   the previous run, whenever the two runs differ in direction. Both `נתונים (Big Data)` and
   the mirror case `3 (כ-6 חודשים)` need it. One-directional handling leaves the other case
   with mirrored brackets.
5. **Exception: a bracket group that mixes a Hebrew word and a Latin word inside**, e.g.
   `(דוחות Power BI)`, is emitted as ONE run with NO rtl flag and no further splitting.
   Splitting or flagging it scrambled the word order or the bracket glyphs. Brackets with only
   Hebrew inside, or only Latin/digits inside, are not this case.
6. **Trailing spaces and separators before a direction change move to the start of the next
   run.** Word trims trailing whitespace at a direction boundary (gluing words together), and a
   separator left at the end of an English/number run (`|`, `–`, `-`, `·`, `:`, `/`) is drawn on
   the wrong side of the line. Verified in Word: `דצמבר 2024 – היום`,
   `Example Academy  |  מאי 2024` and a contact line `050-0000000  |  x@y.com  |  תל אביב` all
   broke with the separator left behind and render correctly once it moves (confirmed by a
   human reading the rendered Hebrew CV, not only by Claude); lines that were already correct
   did not change. A trailing **comma** is not moved (see the table below).
7. **Every run sets the complex-script font and size**: `w:rFonts` with `w:cs`, plus `w:szCs`
   (and `w:bCs` for bold). Hebrew is a complex script in Word, so `w:ascii`/`w:sz` alone never
   reach Hebrew glyphs, and the font or size "silently does nothing".
8. **Never** call python-bidi's `get_display()` on DOCX text (Word applies the bidi algorithm
   itself, and pre-shaping double-reverses it). **Never** insert Unicode directional marks or
   isolates (U+2066-2069). Word can render them as visible boxes.

## Phrasing patterns that still render wrong — reword, don't fight

Even with every rule above, these patterns came out misplaced in Word. The reliable fix is to
reword the sentence, not to add more code:

| Pattern | Example of the problem | Reword to |
|---|---|---|
| Comma right after a Latin word, before Hebrew | `ו-SQL, ניתוח נתונים` | join with ו: `SQL וניתוח נתונים` |
| A number right next to a Latin term | `Excel, 12 דוחות` | put Hebrew between them, or move the number into a Hebrew clause |
| A Latin word followed by a period at the end of the paragraph | `...בעזרת Python.` | end the line with a Hebrew word, or drop the final period |
| A bracketed term that isn't load-bearing | `נתונים גדולים (Big Data)` | drop the bracket: `נתונים גדולים` |
| Brackets around a number + Hebrew word | `קורס SQL (40 שעות)` | `קורס SQL בהיקף 40 שעות` |
| A Hebrew label with an English alternative in a subtitle | `אנליסט נתונים (Data Analyst)` | pick one language for that line |

Cutting a non-essential mixed-language parenthetical is a legitimate fix, not a stopgap.

## Verifying — only Word counts

- **The same text can render differently in two layouts.** Word's bidi reordering depends on
  where the line actually wraps. A fix verified at one column width isn't guaranteed at
  another, so re-verify after any layout change.
- **Render through Word itself** (docx2pdf or Word COM export), not LibreOffice or a preview
  app. Those are more forgiving and hide Word-only bugs.
- **A page count proves nothing about bidi.** Look at the rendered image.
- **Don't trust your own reading of rendered bidi text.** Re-reading the same rendered line can
  produce contradictory conclusions. Show the user the PNG preview and ask them to check
  numbers, brackets and mixed lines. When genuinely unsure between candidates, build a small
  diagnostic .docx with 2-4 labeled variants of the line and render them together.
- **If the user hand-fixed a .docx in Word, never regenerate over it.** Edit the existing file:
  open it with python-docx, find the paragraph by its text, clear its runs and rebuild them with
  `rtl_segments()` from `scripts/rtl.py`. Or move or edit the existing runs' `.text` directly.

## Known limit: the PDF text layer

Word's PDF export of a correctly rendered mixed line drops the space at each switch between
Hebrew and English or digits in the PDF's text layer: the page shows `שאילתות SQL`, a text
extractor reads `שאילתותSQL`. Splitting the boundary space into its own unflagged run fixed the
text layer in tests but broke the visible line in Word (`מ- 6ל- 4שעות`), so it was rejected:
what the recruiter sees wins. The .docx text is clean. For Hebrew CVs, submit the .docx when the
portal accepts it; `ats_extract.py` reports the glued pairs so the user knows.

## Tables (not used by cv-tailor's CV layout)

If you ever need a Hebrew table, per-cell direction is not enough: set
`table.table_direction = WD_TABLE_DIRECTION.RTL` (emits `<w:bidiVisual/>`) so the first
logical column lands on the right, keep the data in logical order (don't reverse it yourself),
and run each cell's text through `add_para`. cv-tailor's CVs are single-column with no tables
because ATS parsers often scramble table reading order.
