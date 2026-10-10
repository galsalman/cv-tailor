#!/usr/bin/env python3
"""Shared helpers for cv-tailor scripts: load profile.yaml, index items by id, compute dates."""
import datetime as _dt
import json
import os
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit('PyYAML is missing. Install it with: python -m pip install pyyaml')

MONTHS = {
    'en': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    'he': ['ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני', 'יולי', 'אוגוסט', 'ספטמבר',
           'אוקטובר', 'נובמבר', 'דצמבר'],
}
MONTHS_LONG_EN = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
                  'September', 'October', 'November', 'December']
PRESENT = {'en': 'Present', 'he': 'היום'}


def load_yaml(path):
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def t(value, lang):
    """Localized text: a {en, he} dict or a plain string."""
    if value is None:
        return ''
    if isinstance(value, dict):
        return (value.get(lang) or value.get('en') or value.get('he') or '').strip()
    return str(value).strip()


def today():
    override = os.environ.get('CV_TAILOR_TODAY')  # YYYY-MM-DD, for tests
    if override:
        return _dt.date.fromisoformat(override)
    return _dt.date.today()


def parse_ym(value):
    """'2024-12' -> (2024, 12). 'present' -> today's (year, month). None/'' -> None."""
    if value is None or value == '':
        return None
    s = str(value).strip().lower()
    if s == 'present':
        d = today()
        return d.year, d.month
    parts = s.split('-')
    return int(parts[0]), int(parts[1])


def months_between(start, end):
    """Whole months from start to end. Deliberately conservative (2024-12 -> 2026-10 is 22):
    month precision can't tell how much of the first and last month was worked, so a duration
    claim is never allowed to round up."""
    a, b = parse_ym(start), parse_ym(end)
    if not a or not b:
        return 0
    return (b[0] - a[0]) * 12 + (b[1] - a[1])


def fmt_duration(months, lang='en'):
    y, m = divmod(months, 12)
    if lang == 'he':
        return f'{y} שנים ו-{m} חודשים'
    return f'{y} years {m} months'


def fmt_ym(value, lang, long=False):
    ym = parse_ym(value)
    if str(value).strip().lower() == 'present':
        return PRESENT[lang]
    if not ym:
        return ''
    y, m = ym
    if lang == 'en':
        return f'{(MONTHS_LONG_EN if long else MONTHS["en"])[m - 1]} {y}'
    return f'{MONTHS["he"][m - 1]} {y}'


def fmt_range(start, end, lang):
    return f'{fmt_ym(start, lang)} – {fmt_ym(end, lang)}'


def total_experience_months(profile):
    """Months covered by any experience entry, counting overlapping periods once (same
    conservative convention as months_between: the end month is not counted)."""
    covered = set()
    for exp in profile.get('experience') or []:
        a, b = parse_ym(exp.get('start')), parse_ym(exp.get('end'))
        if not a or not b:
            continue
        y, m = a
        while (y, m) < b:
            covered.add((y, m))
            m += 1
            if m > 12:
                y, m = y + 1, 1
    return len(covered)


class Index:
    """Every id in the profile -> (kind, item, parent)."""

    def __init__(self, profile):
        self.profile = profile
        self.items = {}
        self.duplicates = []
        for exp in profile.get('experience') or []:
            self._add(exp, 'experience', None)
            for b in exp.get('bullets') or []:
                self._add(b, 'bullet', exp)
        for proj in profile.get('projects') or []:
            self._add(proj, 'project', None)
            for b in proj.get('bullets') or []:
                self._add(b, 'project-bullet', proj)
        for kind, key in (('education', 'education'), ('skill', 'skills'), ('language', 'languages')):
            for item in profile.get(key) or []:
                self._add(item, kind, None)

    def _add(self, item, kind, parent):
        iid = item.get('id')
        if not iid:
            return
        if iid in self.items:
            self.duplicates.append(iid)
        self.items[iid] = (kind, item, parent)

    def get(self, iid):
        return self.items.get(iid)


def claim_state(item, parent=None):
    """'ok', 'ask' (needs the user's approval) or 'never' for a claim item.

    Items without a status (experience entries, education, languages) are facts, not claims: 'ok'.
    A bullet inherits the stricter state of its parent project.
    """
    def own(it):
        if it is None or 'status' not in it:
            return 'ok'
        status = str(it.get('status', '')).strip().lower()
        if status == 'do-not-use':
            return 'never'
        if status == 'verified' and it.get('explainable', False) is True:
            return 'ok'
        return 'ask'

    order = {'ok': 0, 'ask': 1, 'never': 2}
    states = [own(item), own(parent)]
    return max(states, key=order.get)
