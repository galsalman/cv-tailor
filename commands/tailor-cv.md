---
description: Judge a job posting against your profile, then build an honest one-page CV for it, check it for ATS, render the PDF and log it in your tracker
argument-hint: <posting URL or pasted posting text>
---

# /tailor-cv

You orchestrate the cv-tailor pipeline for one posting. The order is fixed and every step
is required: **verdict → plan → your questions to the user → build + fact check → render →
ATS → tracker**. Never build a CV before the verdict, and never skip the fact check or render.

Subagents cannot ask the user anything. Every question goes through you, with
`AskUserQuestion`. Speak to the user in the language in `cv-tailor.config.json` (default Hebrew).

Posting: $ARGUMENTS

## 0. Workspace

The job-search folder is the current working directory. It must contain `profile.yaml` and
`cv-tailor.config.json`. If either is missing, stop and tell the user to run `/cv-tailor:cv-setup`.

Run the profile check and stop on errors:
`python "${CLAUDE_PLUGIN_ROOT}/skills/cv-render/scripts/fact_check.py" --profile profile.yaml`

If `$ARGUMENTS` is empty, ask the user for the posting link or text.

## 1. Save the posting

- A URL: fetch it with WebFetch and ask for the full posting text verbatim (title, company,
  location, every requirement line). If the fetch fails or returns a login wall (common on
  LinkedIn), ask the user to paste the text.
- A path to a local file (`.md`, `.txt`, `.pdf`, `.docx`): read it.
- Pasted text: use it as is.

Pick a slug `YYYY-MM-DD_<company>_<role>` (today's date, lowercase ASCII, dashes, short).
Check the tracker for an existing row with the same link, or the same company and role
(see `${CLAUDE_PLUGIN_ROOT}/dashboard/TRACKING.md`). If one exists, show its status and verdict
and ask whether to redo it before going on.

Write `jobs/<slug>/posting.md`: source URL, date fetched, then the posting text.

## 2. Verdict: placement-expert

Run the `placement-expert` agent with: the job-search folder path, `jobs/<slug>/posting.md`,
and the instruction to follow its output format. Save its whole answer to `jobs/<slug>/verdict.md`.
Parse the JSON block at the end.

Log the row now (see TRACKING.md): company, role, location, link, dateFound,
`skillsMatchPercent`, a 1-3 sentence `verdict`, `jobFolder`, `submissionStatus: not_submitted`.

Show the user the verdict line, the hard gaps and the strongest angle.

If the verdict is `not_now`: ask the user whether to stop here (set `submissionStatus: skipped`
and finish) or build anyway. Building anyway is the user's call; respect it, and keep the
hard gaps visible in the final summary.

## 3. Plan: hr-recruiter-expert

Run the `hr-recruiter-expert` agent with the folder, posting and verdict paths. Save its answer to
`jobs/<slug>/plan.md` and parse its JSON block.

## 4. Ask the user what they stand behind

Collect `needsConfirmation` from the verdict and the plan. For each item, show the user the item's
text from `profile.yaml` and why it would help, and ask one question: can you explain this in an
interview and stand behind it? Use `AskUserQuestion` (multi-select is fine for a batch). Never
pre-tick anything.

Write `jobs/<slug>/approvals.json` yourself, never through a subagent:
`{"approved": [ids the user said yes to], "date": "YYYY-MM-DD"}` (an empty list is fine).
If the user said an item is wrong or out of date, offer to fix `profile.yaml` (with their
wording), and re-run the profile check.

CV language: the posting's language by default. If `preferences.cv_languages` has both and the
posting doesn't make it obvious, ask.

## 5. Build: cv-builder-expert

Run the `cv-builder-expert` agent with: the folder, `jobs/<slug>/` (posting, verdict, plan,
approvals), the CV language, and the slug. It writes `cv-spec.json`, runs the fact check,
builds the .docx and renders the PDF.

If it reports that it needs an item that isn't approved, ask the user (step 4 rules), update
`approvals.json`, and run it again. If it can't fit one page after two rounds, show the user
what it would cut next and let them choose.

Show the user the PNG preview path. For a Hebrew CV, open the PNG with Read to look at it, and
ask the user to check the numbers, brackets and mixed Hebrew/English lines with their own eyes:
your own reading of rendered bidi text is not reliable. If they spot a broken line, have the
builder reword that line (not add code) and re-render.

## 6. ATS: ats-screener

Run the `ats-screener` agent with the .docx and posting paths. Save its answer to
`jobs/<slug>/ats-report.md` and parse its JSON block.

If it lists `fixable` items, run `cv-builder-expert` once more with exactly those fixes, then
re-render, then run `ats-screener` once more only to measure the fixed file (overwrite
`ats-report.md`). Do not loop: one fix round at most, and no fixes from the second scan.
`cvMatchPercent` in the tracker is always the number from the last real scan, never a projection. `needsConfirmation` items go to the user as in
step 4. `realGaps` are reported, never "fixed".

## 7. Log and hand over

Update the row: `submissionStatus: cv_ready`, `cvMatchPercent`, `cvFile`, `plan` (1-3 sentences).

Final message to the user, short, in their language:
- The verdict and fit percent.
- The files (PDF, DOCX) as links.
- What leads, what was cut, every wording the builder flagged for their confirmation.
- Real gaps the CV does not cover.
- For a Hebrew CV: submit the .docx when the portal accepts it (its text is clean; the PDF's text
  layer glues Hebrew to English words, see the ATS report).
- Next step: submit it themselves, then run `/cv-tailor:track` (e.g. "submitted to <company>")
  so the tracker starts counting days.
