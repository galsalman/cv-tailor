---
description: Set up the automatic job scan on this Windows computer - what to search for, a test run, and a scheduled task that keeps scanning while the computer is on
argument-hint: [stop | dry-run-off]
---

# /scan-setup

Set up (or change) the automatic job scan for the job-search folder in the current directory.
Speak in the language in `cv-tailor.config.json` (default Hebrew).

Argument: `$ARGUMENTS`
- `stop`: run `powershell -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scanner/uninstall-task.ps1"`,
  confirm it's removed, and finish. Nothing else.
- `dry-run-off`: delete `scan/DRY_RUN`, tell the user the scan now writes to the tracker, finish.

## 1. Requirements

- `profile.yaml` and `cv-tailor.config.json` exist (otherwise: `/cv-tailor:cv-setup` first).
- Windows. On macOS or Linux, explain that this setup is Windows-only for now and that
  `/cv-tailor:scan` can still be run by hand.
- Git for Windows: check `git --version`. The unattended scan needs its Bash shell. If missing,
  point to https://git-scm.com/downloads/win (default options), and continue after they install it.
- The Python libraries: `python -c "import docx, yaml, fitz, docx2pdf; print('ok')"`.

## 2. What to search for

Build a proposal from `profile.yaml` (targets, verified skills, situation, location) and show it.
Then let the user change it:

- `terms.he` / `terms.en`: 6-12 search phrases in each language, the way Israeli postings are
  titled (e.g. "אנליסט/ית תפעול", "Operations Analyst"). More phrases = more coverage = longer runs.
- `prefer`: what makes a posting a good fit, in plain words.
- `skip`: what always fails for them (hard gates, seniority, fields they don't want).
- `locations`: preferred areas; remote / hybrid OK or not.
- `maxReport`: how many suggestions per run at most (default 7).
- `sites`: `drushim`, `alljobs`, `jobmaster` by default. Offer `linkedin` only if the user asks,
  and say plainly: LinkedIn's terms of use forbid automated collection, and turning it on is
  their own choice and risk. Never add it by default.

Save it as the `scan` section of `cv-tailor.config.json`, keeping the other sections:
```json
"scan": {
  "sites": ["drushim", "alljobs", "jobmaster"],
  "terms": {"he": ["..."], "en": ["..."]},
  "prefer": ["..."], "skip": ["..."], "locations": ["..."],
  "maxReport": 7, "maxNew": 80,
  "times": ["09:30", "17:30"], "days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
}
```

## 3. Test run (dry)

Create the file `scan/DRY_RUN` (empty), then run the scan here, in front of the user, by
following `${CLAUDE_PLUGIN_ROOT}/commands/scan.md` (without `auto`). Show what it would have
suggested and why the rest was dropped. Tune `terms` / `prefer` / `skip` with the user if the
results look off, and re-run once if they changed a lot.

## 4. Schedule

Ask for the times and days (default 09:30 and 17:30, Sunday to Thursday). Explain:
- The scan runs only while the computer is on and they are signed in to Windows. A run that was
  missed (computer asleep or off) starts as soon as the computer is available again.
- Each run uses their Claude plan's usage (about one long conversation); runs stop after 25 minutes.
- In Windows power settings, "sleep" should be "never" when plugged in, or at least after the
  scan times, if they want every run.

Then install the task:
```
powershell -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/scanner/install-task.ps1" -Workspace "<this folder>" -Times "<times>" -Days "<days>"
```
(When the plugin was loaded with `--plugin-dir`, also pass `-PluginDir "<that folder>"`.)
Show the "Next run" line it prints.

## 5. Go live

The first scheduled runs stay dry while `scan/DRY_RUN` exists. Ask whether to go live now
(delete `scan/DRY_RUN`) or after they've seen a scheduled dry run in `scan/results/`.

Finish with a short summary:
- what is searched, on which sites, when
- where results appear: "scan suggestion" rows in the tracker, plus `scan/results/<date>.md`
- logs in `scan/logs/`
- how to change it (`/cv-tailor:scan-setup` again), run once now (`/cv-tailor:scan`),
  pause (create `scan/DRY_RUN`), or stop for good (`/cv-tailor:scan-setup stop`).
