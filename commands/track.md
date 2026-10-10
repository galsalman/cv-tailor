---
description: Update an application in your tracker - submitted, got a reply, interview scheduled, rejected - or show what's in flight
argument-hint: <what happened, e.g. "submitted to Acme" or "Acme interview on 2026-11-03">
---

# /track

Update the user's application tracker from what they tell you. Speak in the language in
`cv-tailor.config.json` (default Hebrew). How to read and write rows:
`${CLAUDE_PLUGIN_ROOT}/dashboard/TRACKING.md`.

What happened: $ARGUMENTS

## With no arguments

List what's in flight, grouped: CV ready but not submitted, submitted and waiting (with days
waited; 10+ days counts as no reply), in process (with the next stage date), recently rejected.
Then ask what changed.

## With an update

1. Find the row by company and role. More than one match, or none: ask, never guess.
2. Map what the user said to fields:
   - submitted → `submissionStatus: submitted`, `dateSubmitted` (today unless they gave a date),
     `responseStatus: waiting`
   - positive reply / call / interview / recorded video → `responseStatus: positive`,
     `interviewStage` (`phone`, `video`, `interview`, `offer`), `stageDate` if given,
     `stageDone: false`
   - stage happened → `stageDone: true`, `stageDoneDate`
   - rejected → `responseStatus: negative`
   - anything else worth keeping → append a dated line to `notes`
3. Show the user the change in one line, then write it.

## Follow-ups

When a submitted job has waited 10+ days with no reply, or a stage was done 10+ days ago with no
news, offer the `reconnect-advisor` agent: it checks the company's current situation and drafts
a short follow-up message. Pass it the row and the job folder.
