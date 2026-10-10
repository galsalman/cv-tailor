---
description: Set up cv-tailor in this folder - build your profile with an honest status on every claim, and create your private application tracker
argument-hint: [path to an existing CV, optional]
---

# /cv-setup

Set up the current folder as the user's job-search folder. Speak in Hebrew unless the user writes
in English; ask their preferred language early and use it from then on.

Optional input: $ARGUMENTS (a path to an existing CV or a folder of CVs).

## 1. Check the folder

- If `profile.yaml` already exists, never overwrite it. Offer to review it instead: run the
  profile check (step 4) and walk through what it reports. Skip to step 5 if the dashboard is
  missing from `cv-tailor.config.json`.
- Otherwise copy `${CLAUDE_PLUGIN_ROOT}/templates/profile.template.yaml` to `profile.yaml`, and
  create `jobs/`.
- Point to `${CLAUDE_PLUGIN_ROOT}/examples/dana-levi/profile.yaml` as a filled-in example of a
  fictional person, if the user wants to see one.

## 2. Fill the profile

Explain in two sentences why the profile exists: it is the only source the CV builder may use,
and every claim in it carries a status, so no CV ever contains something the user can't defend.

**From an existing CV** (a path was given, or the user offers one): read it (`.docx` with
python-docx, `.pdf` with the pdf tooling available, `.txt`/`.md` directly). Draft the profile
from it, with **every bullet, skill and project marked `status: self-reported`,
`explainable: false`**. Nothing becomes verified without the user saying so.

**From scratch**: interview the user section by section (contact, situation, targets,
experience, education, skills, projects, languages). Ask a few questions at a time.

Then **review every claim with the user**, in batches of up to four (`AskUserQuestion`):
- Did you do this yourself, and could you show it? → `verified`, otherwise `self-reported`.
- Could you explain it in an interview if asked two follow-up questions? → `explainable`.
- Should this never appear on a CV? → `do-not-use`.
Push back gently on inflated wording ("led" when they took part, one system split into two
projects, a tool their AI assistant used counted as their own skill). Record the user's answer,
not your judgment.

Dates: exact `YYYY-MM` for every job; `present` for a current one. Education: `in-progress`
with an `expected` date until the degree is actually in hand.

Hebrew text: avoid the phrasing patterns in `${CLAUDE_PLUGIN_ROOT}/skills/hebrew-docx/SKILL.md`
(a comma right after an English word before Hebrew, brackets around a number, a line ending in
English). Titles and degree names go onto the CV exactly as written in the profile.

## 3. Targets

Ask which job tracks they're aiming for, in priority order, and which experience should lead a
CV for each (`targets[].lead_with`). Add their own standing rules to `rules`.

## 4. Check the profile

```
python "${CLAUDE_PLUGIN_ROOT}/skills/cv-render/scripts/fact_check.py" --profile profile.yaml
```

Fix every error with the user. Warnings about self-reported items are expected; mention how many.

Check the Python libraries with exactly this command (always `python`, never `python3`: on
Windows `python3` often opens the Microsoft Store stub, which has none of them):
`python -c "import docx, yaml, fitz, docx2pdf; print('ok')"`
If it fails, install them with `python -m pip install python-docx pyyaml docx2pdf pymupdf` after
the user agrees. If `python` itself isn't found, try `py` and use it in every later command. PDF rendering
needs Microsoft Word (Windows or macOS); without it, LibreOffice works but may hide Hebrew
layout problems Word would show.

## 5. The application tracker

Each user gets their own private, empty tracker. Never copy rows from anyone else.

**Preferred: a claude.ai dashboard** (when the `Artifact` tool is available in this session):
1. Copy `${CLAUDE_PLUGIN_ROOT}/dashboard/dashboard.html` to `tracker/dashboard-artifact.html` in
   this folder (the Artifact tool only publishes files from the working folder).
2. Publish it with the Artifact tool: `capabilities: {"db": {}}`, icon `list`, description
   "Private tracker for my job applications, filled in by cv-tailor."
3. With `ArtifactData`, `set` the document `main` in collection `settings` to
   `{"language": "<he or en>"}`.
4. One functional check: `list` the `applications` collection (it should be empty) and tell the
   user in one line that the dashboard is live and empty.

**Fallback: a local dashboard** (no Artifact tool, or the user prefers local):
```
python "${CLAUDE_PLUGIN_ROOT}/dashboard/tracker.py" init
```
It creates `tracker/dashboard.html`, which opens in any browser and refreshes its data each
time cv-tailor updates a row.

## 6. Save the config

Write `cv-tailor.config.json`:
```json
{"language": "he", "dashboard": {"mode": "artifact", "url": "<artifact url>"}}
```
(`"mode": "local", "url": ""` for the local tracker.)

Finish with a short summary: what's in the profile (counts by status), where the tracker is,
and the next step: `/cv-tailor:tailor-cv <posting link>`.
