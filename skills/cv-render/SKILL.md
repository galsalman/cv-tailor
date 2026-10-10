---
name: cv-render
description: cv-tailor's CV toolchain - fact check a cv-spec.json against profile.yaml, build a one-page single-column ATS-safe .docx (Hebrew or English), render it to PDF through Word with a page count and PNG preview, and show what an ATS parser extracts. Use inside /tailor-cv, or whenever a cv-tailor CV has to be rebuilt, re-rendered or re-checked.
---

# cv-render

Four scripts in `${CLAUDE_PLUGIN_ROOT}/skills/cv-render/scripts/`. Run them from the user's
job-search folder. Python 3.9+ with `python-docx`, `pyyaml`, `docx2pdf`, `pymupdf`.
Always call `python` (or `py` where `python` is missing), never `python3`: on Windows `python3`
is often the Microsoft Store stub, which reports every library as missing.

| Script | Does | Exit code |
|---|---|---|
| `fact_check.py --profile profile.yaml` | Checks the profile alone: unique ids, valid statuses, dates | 1 on errors |
| `fact_check.py --profile profile.yaml --spec jobs/<slug>/cv-spec.json` | Blocks unapproved or do-not-use claims, claims moved between jobs, new numbers, unsupported durations, a degree phrased as complete, duplicates; warns on Hebrew bidi-risky phrasing | 1 on errors |
| `build_cv.py --profile … --spec … --out jobs/<slug>/` | Runs the fact check, then writes `<fileName>.docx` (keeps a `.bak` of the previous one) | non-zero if the check fails |
| `render_pdf.py jobs/<slug>/<fileName>.docx` | Word → PDF on a temp copy, page count, `<fileName>.png` preview | 0 = one page, 2 = longer, 1 = failed |
| `ats_extract.py jobs/<slug>/<fileName>.docx` | Raw text in parser order, regex contact fields, PDF text layer, parsing risks | 0 |

The spec format is defined in the `cv-builder-expert` agent. Facts (names, titles, employers,
dates, degrees, contact details, skill names) are never in the spec: `build_cv.py` reads them from
the profile. Approvals live in `jobs/<slug>/approvals.json` and are written by `/tailor-cv` after
asking the user, never by an agent.

Set `CV_TAILOR_TODAY=YYYY-MM-DD` to pin "today" when testing durations.

The layout is fixed on purpose: A4, Arial, no tables, text boxes, columns, images or Word
header/footer, contact details as plain text in the body. Hebrew paragraphs go through
`${CLAUDE_PLUGIN_ROOT}/skills/hebrew-docx/scripts/rtl.py`; see that skill for the bidi rules.
