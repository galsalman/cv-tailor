#!/usr/bin/env python3
"""Local application tracker for cv-tailor (used when the claude.ai dashboard isn't available).

Keeps tracker/applications.json in the user's job-search folder as the source of truth, and
regenerates tracker/dashboard.html + tracker/applications.js on every change, so the page opens
straight from disk (file://) with no server.

Usage (run from the job-search folder):
  python tracker.py init                                  # create tracker/ with an empty list
  python tracker.py upsert --id <slug> --data-file row.json   # merge fields into one row
  python tracker.py get --id <slug>
  python tracker.py list                                  # one line per row
  python tracker.py export-csv [--out tracker/applications.csv]
  python tracker.py log-run --data-file run.json            # record one scan run (keeps the last 30)

Row fields (all optional except id): company, role, location, link, dateFound, submissionStatus
(suggested | not_submitted | cv_ready | submitted | skipped), source (scan | manual), responseStatus (waiting | positive | negative),
interviewStage (none | phone | video | interview | offer), stageDate, stageDone, stageDoneDate,
dateSubmitted, skillsMatchPercent, cvMatchPercent, verdict, plan, cvFile, jobFolder, notes.
"""
import argparse
import csv
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, 'dashboard.html')
FIELDS = ['id', 'company', 'role', 'location', 'link', 'dateFound', 'submissionStatus',
          'responseStatus', 'interviewStage', 'stageDate', 'stageDone', 'stageDoneDate',
          'dateSubmitted', 'skillsMatchPercent', 'cvMatchPercent', 'verdict', 'plan', 'cvFile',
          'jobFolder', 'notes', 'source']
ENUMS = {
    'submissionStatus': {'suggested', 'not_submitted', 'cv_ready', 'submitted', 'skipped'},
    'responseStatus': {'waiting', 'positive', 'negative'},
    'interviewStage': {'none', 'phone', 'video', 'interview', 'offer'},
}
SKELETON = ('<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<style>body{margin:0}[hidden]{display:none!important}</style></head><body>\n')


def paths(root):
    t = os.path.join(root, 'tracker')
    return t, os.path.join(t, 'applications.json')


def language(root):
    cfg = os.path.join(root, 'cv-tailor.config.json')
    try:
        with open(cfg, encoding='utf-8') as f:
            return json.load(f).get('language', 'he')
    except (OSError, ValueError):
        return 'he'


def load_runs(root):
    runs = os.path.join(paths(root)[0], 'scan_runs.json')
    if not os.path.exists(runs):
        return []
    with open(runs, encoding='utf-8') as f:
        return json.load(f)


def load(root):
    _, data = paths(root)
    if not os.path.exists(data):
        return []
    with open(data, encoding='utf-8') as f:
        return json.load(f)


def save(root, rows):
    tdir, data = paths(root)
    os.makedirs(tdir, exist_ok=True)
    tmp = data + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    os.replace(tmp, data)
    payload = json.dumps({'language': language(root), 'rows': rows, 'scanRuns': load_runs(root)},
                         ensure_ascii=False)
    with open(os.path.join(tdir, 'applications.js'), 'w', encoding='utf-8') as f:
        f.write('window.CV_TAILOR_DATA = ' + payload.replace('</', '<\\/') + ';\n')
    with open(TEMPLATE, encoding='utf-8') as f:
        page = f.read()
    page = page.replace('<!--CV_TAILOR_LOCAL_DATA-->', '<script src="applications.js"></script>')
    with open(os.path.join(tdir, 'dashboard.html'), 'w', encoding='utf-8') as f:
        f.write(SKELETON + page + '\n</body></html>\n')


def validate(row):
    for key, allowed in ENUMS.items():
        if key in row and row[key] not in allowed:
            sys.exit(f'{key} must be one of {sorted(allowed)}, got {row[key]!r}')
    unknown = set(row) - set(FIELDS)
    if unknown:
        sys.exit(f'unknown fields: {sorted(unknown)}. Allowed: {FIELDS}')


def cmd_upsert(root, row_id, data_file):
    with open(data_file, encoding='utf-8') as f:
        patch = json.load(f)
    patch.pop('id', None)
    validate(patch)
    rows = load(root)
    for row in rows:
        if row.get('id') == row_id:
            row.update(patch)
            action = 'updated'
            break
    else:
        row = {'id': row_id, 'dateFound': datetime.date.today().isoformat(),
               'submissionStatus': 'not_submitted', 'responseStatus': 'waiting'}
        row.update(patch)
        rows.append(row)
        action = 'added'
    save(root, rows)
    print(f'{action}: {row_id}')
    print('dashboard: ' + os.path.join(paths(root)[0], 'dashboard.html'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default='.', help='job-search folder (default: current folder)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('init')
    up = sub.add_parser('upsert')
    up.add_argument('--id', required=True)
    up.add_argument('--data-file', required=True)
    g = sub.add_parser('get')
    g.add_argument('--id', required=True)
    sub.add_parser('list')
    lr = sub.add_parser('log-run')
    lr.add_argument('--data-file', required=True)
    ex = sub.add_parser('export-csv')
    ex.add_argument('--out')
    args = ap.parse_args()
    root = os.path.abspath(args.root)

    if args.cmd == 'init':
        save(root, load(root))
        print('dashboard: ' + os.path.join(paths(root)[0], 'dashboard.html'))
    elif args.cmd == 'upsert':
        cmd_upsert(root, args.id, args.data_file)
    elif args.cmd == 'get':
        row = next((r for r in load(root) if r.get('id') == args.id), None)
        print(json.dumps(row, ensure_ascii=False, indent=2) if row else f'no row with id {args.id}')
    elif args.cmd == 'list':
        for r in sorted(load(root), key=lambda r: r.get('dateFound', ''), reverse=True):
            print(f"{r.get('id')} | {r.get('company', '')} | {r.get('role', '')} | "
                  f"{r.get('submissionStatus', '')}/{r.get('responseStatus', '')} | {r.get('dateFound', '')}")
    elif args.cmd == 'log-run':
        with open(args.data_file, encoding='utf-8') as f:
            run = json.load(f)
        runs = [r for r in load_runs(root) if r.get('id') != run.get('id')] + [run]
        runs = sorted(runs, key=lambda r: r.get('startedAt', ''))[-30:]
        os.makedirs(paths(root)[0], exist_ok=True)
        with open(os.path.join(paths(root)[0], 'scan_runs.json'), 'w', encoding='utf-8') as f:
            json.dump(runs, f, ensure_ascii=False, indent=2)
        save(root, load(root))
        print('run logged: ' + str(run.get('id')))
    elif args.cmd == 'export-csv':
        out = args.out or os.path.join(paths(root)[0], 'applications.csv')
        with open(out, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
            w.writeheader()
            w.writerows(load(root))
        print('csv: ' + out)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
