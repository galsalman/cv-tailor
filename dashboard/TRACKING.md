# Writing to the application tracker

Read `cv-tailor.config.json` in the job-search folder. `dashboard.mode` decides where rows go.

## The row

One row per job, keyed by the job's slug (`YYYY-MM-DD_<company>_<role>`, lowercase ASCII,
letters/digits/dashes, the same name as its `jobs/` folder). Fields, all optional except the id:

| Field | Values |
|---|---|
| `company`, `role`, `location`, `link` | text, as written in the posting |
| `dateFound` | `YYYY-MM-DD` |
| `submissionStatus` | `not_submitted`, `cv_ready`, `submitted`, `skipped` |
| `responseStatus` | `waiting`, `positive`, `negative` |
| `interviewStage` | `none`, `phone`, `video`, `interview`, `offer` |
| `stageDate`, `dateSubmitted`, `stageDoneDate` | `YYYY-MM-DD` |
| `stageDone` | `true` / `false` |
| `skillsMatchPercent` | integer 0-100, from placement-expert |
| `cvMatchPercent` | integer 0-100, from ats-screener |
| `verdict` | 1-3 plain sentences: the verdict and its main reason, in the user's language |
| `plan` | 1-3 sentences: what leads, what was cut |
| `cvFile` | path of the PDF relative to the job-search folder |
| `jobFolder` | `jobs/<slug>` |
| `notes` | free text |

Write the patch (only the fields that changed) to `jobs/<slug>/row.json` first, as UTF-8 JSON.

## mode: "local"

```
python "${CLAUDE_PLUGIN_ROOT}/dashboard/tracker.py" upsert --id <slug> --data-file jobs/<slug>/row.json
```

It merges the patch into `tracker/applications.json` (creating the row if new) and regenerates
`tracker/dashboard.html`. Other subcommands: `list`, `get --id <slug>`, `export-csv`.

## mode: "artifact"

The rows live in the `applications` collection of the dashboard artifact at `dashboard.url`.
Use the `ArtifactData` tool (load it with ToolSearch if it is deferred):

1. `get` collection `applications`, doc id `<slug>`.
2. Missing: `set` it with the full row (add `submissionStatus: "not_submitted"`,
   `responseStatus: "waiting"` and `dateFound` if the patch doesn't have them).
   Present: `update` it with the patch.

If the artifact can't be reached (deleted, tools unavailable), say so, fall back to local mode
for this write, and tell the user to rerun `/cv-tailor:cv-setup` to reconnect a dashboard.

## Finding a row from what the user says

`list` (local) or an `ArtifactData` `list` of `applications` (artifact), then match on company
and role. If more than one row matches, ask the user which one. Never guess.
