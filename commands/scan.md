---
description: Scan Israeli job sites for new postings that fit your profile and add the best ones to your tracker as scan suggestions (runs on a schedule, or by hand)
argument-hint: [auto]
---

# /scan

Find NEW, realistic job postings that fit the user's profile, judge them honestly, and add the
best few to the tracker as `suggested` rows. You never apply anywhere and never contact anyone.

Mode: `$ARGUMENTS`. **`auto` means nobody is watching** (the scheduled task started this run):
never ask a question, never wait for input; make the best decision and note it in the run
summary. Without `auto`, the user is present: report as you go, but still don't ask questions
unless something blocks the run.

The job-search folder is the current working directory.

## 0. Preconditions

- `profile.yaml` and `cv-tailor.config.json` must exist, and `cv-tailor.config.json` must have
  a `scan` section with search terms. If not: in `auto` mode write a run record with
  `status: "error"` and a summary saying `/cv-tailor:scan-setup` is needed, then stop. Otherwise
  tell the user to run `/cv-tailor:scan-setup`.
- **Dry run:** if the file `scan/DRY_RUN` exists, do everything except writing to the tracker
  (no rows, no run record in the tracker). Say "DRY RUN" in the local record and final output.
- Get the real time once, for the run stamp: `python -c "import datetime;print(datetime.datetime.now().astimezone().isoformat(timespec='seconds'))"`.
  Stamp = `YYYY-MM-DD_HHMM` from it. Never guess the time.

## 1. Collect (no AI)

```
python "${CLAUDE_PLUGIN_ROOT}/scanner/fetch_listings.py" --root .
```
Run it with a 10-minute timeout. It prints the candidates file it wrote
(`scan/results/candidates_<stamp>.json`: a list of `{site, url, title, requirements}`, where
`requirements` is a snippet of the posting's requirements). If it fails or finds nothing, record
that in the run summary; do not fall back to scraping other sites yourself.

## 2. Ground yourself

Read `profile.yaml` (facts, targets, situation, rules), the `scan` section of the config
(`prefer`, `skip`, `locations`, `maxReport`), and `${CLAUDE_PLUGIN_ROOT}/agents/placement-expert.md`:
judge every posting the way it does. Count only `verified` profile items; compute experience
from the dates; an `in-progress` degree is not a degree yet.

## 3. Shortlist from the snippets

Read the whole candidates file. Drop:
- anything outside the user's `targets` tracks and `scan.prefer`;
- anything matching `scan.skip`;
- anything whose snippet shows a hard gate the user fails: a required experience floor well above
  theirs, a required degree field they don't hold, a "must" skill that is not a verified
  profile item, senior / lead / manager titles when the profile is junior;
- postings that look closed or older than about 14 days.

Don't drop a posting only because its title is vague: if the snippet fits, keep it. Expect to
drop most. Keep at most about 15.

## 4. Read the shortlist in full

Open each shortlisted URL with WebFetch and read the full requirements (the snippet can be cut
or miss a gate). Closed (404/410), login-walled or blocked: skip it, don't guess. Never report
a fact you could not read on the page.

## 5. Don't repeat

Read every existing tracker row (see `${CLAUDE_PLUGIN_ROOT}/dashboard/TRACKING.md`), whatever its
status, including `skipped` rows the user dismissed. Skip any posting whose link, or whose
company + role, is already there.

## 6. Pick and record

Rank what's left; keep the best `scan.maxReport` (default 7), strongest first. Fewer is fine;
none is a fine outcome. Never pad with weak fits.

For each, write a tracker row (TRACKING.md), id `<stamp-date>_<company>_<role>` slug:
- `company`, `role`, `location`, `link`, `dateFound` (today)
- `submissionStatus: "suggested"`, `responseStatus: "waiting"`, `source: "scan"`
- `skillsMatchPercent` (placement-expert's definition)
- `verdict`: 2-4 sentences in the user's language: the verdict word (apply / maybe / long
  shot), which mandatory requirements their real experience covers (by name, not id), the main
  gap or risk.
- `plan`: 1-2 sentences: which experience to lead with if they build a CV for it.

## 7. Run record

Write the run (TRACKING.md, "Scan runs"): `id` = stamp, `startedAt`, `status`, `collected`
(entries in the candidates file), `evaluated` (postings opened in full), `reported` (rows
added), `addedList` (one line each: "company — role (location) · verdict word"), `summary`
(1-2 sentences: what was mostly rejected and why).

Also append a section to `scan/results/<YYYY-MM-DD>.md`: the run time, each reported posting
(company — role — location — link — verdict), each skipped shortlisted posting with a one-line
reason, and whether the tracker writes succeeded.

## 8. Final output

A short summary in the user's language: checked, reported (company — role — verdict),
skipped by reason, tracker write result. Suggest `/cv-tailor:tailor-cv <link>` for the
strongest one.
