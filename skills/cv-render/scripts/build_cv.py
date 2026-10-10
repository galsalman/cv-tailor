#!/usr/bin/env python3
"""Build a one-page, single-column, ATS-safe CV (.docx) from cv-spec.json + profile.yaml.

The spec carries only the choices and the wording of bullets/summary. Everything factual -
name, contact details, job titles, employers, dates, degrees, skill names - is taken from the
profile here, so it cannot drift. The fact check runs first; nothing is written if it fails.

Layout (fixed on purpose): no tables, text boxes, columns, images or Word header/footer;
contact details as plain text in the body; one reading order for every parser.

Usage:
  python build_cv.py --profile profile.yaml --spec jobs/<slug>/cv-spec.json --out jobs/<slug>/
"""
import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', 'hebrew-docx', 'scripts'))

from docx import Document  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402

import fact_check  # noqa: E402
from profile_lib import Index, fmt_range, fmt_ym, load_json, load_yaml, t  # noqa: E402
from rtl import add_para  # noqa: E402

FONT = 'Arial'
INK = '1A1A1A'
GRAY = '555555'
RULE = '8A8A8A'

TITLES = {
    'en': {'summary': 'Summary', 'experience': 'Experience', 'projects': 'Projects',
           'education': 'Education', 'skills': 'Skills', 'languages': 'Languages'},
    'he': {'summary': 'תמצית', 'experience': 'ניסיון תעסוקתי', 'projects': 'פרויקטים',
           'education': 'השכלה', 'skills': 'כישורים', 'languages': 'שפות'},
}
EXPECTED = {'en': 'Expected {date}', 'he': 'סיום צפוי: {date}'}
SEP = '  |  '
BULLET_INDENT = 220  # twips


class CV:
    def __init__(self, profile, spec):
        self.profile, self.spec = profile, spec
        self.lang = spec['language']
        self.idx = Index(profile)
        layout = spec.get('layout') or {}
        self.body = float(layout.get('bodySize', 9.5))
        self.margin = float(layout.get('marginCm', 1.3))
        self.doc = Document()

    # -- primitives ------------------------------------------------------------------------
    def para(self, parts, size=None, after=0, before=0, **kw):
        return add_para(self.doc, parts, font=FONT, size=size or self.body, after=after,
                        before=before, **kw)

    def section(self, key):
        self.para([(TITLES[self.lang][key], True, INK)], size=self.body + 2, before=140, after=50,
                  border_bottom=RULE)

    def bullets(self, items):
        for b in items:
            self.para('-  ' + b['text'].strip(), after=15, indent=BULLET_INDENT)

    def entry(self, title, meta):
        parts = [(title, True, INK)]
        if meta:
            parts.append((SEP + meta, False, GRAY))
        self.para(parts, size=self.body + 0.5, before=60, after=20)

    # -- document ----------------------------------------------------------------------------
    def setup(self):
        s = self.doc.sections[0]
        s.page_width, s.page_height = Cm(21.0), Cm(29.7)
        s.left_margin = s.right_margin = Cm(self.margin)
        s.top_margin = s.bottom_margin = Cm(max(0.8, self.margin - 0.3))
        normal = self.doc.styles['Normal']
        normal.font.name = FONT
        normal.font.size = Pt(self.body)
        rpr = normal.element.get_or_add_rPr()
        fonts = rpr.find(qn('w:rFonts'))
        if fonts is None:
            fonts = rpr.makeelement(qn('w:rFonts'), {})
            rpr.append(fonts)
        for attr in ('w:ascii', 'w:hAnsi', 'w:cs'):
            fonts.set(qn(attr), FONT)
        normal.paragraph_format.space_after = Pt(0)
        normal.paragraph_format.line_spacing = 1.05
        if self.lang == 'he':
            sect = s._sectPr
            sect.append(sect.makeelement(qn('w:bidi'), {}))

    def header(self):
        person = self.profile.get('person') or {}
        self.para([(t(person.get('name'), self.lang), True, INK)], size=20, align='center', after=20)
        if self.spec.get('headline'):
            self.para([(self.spec['headline'].strip(), False, GRAY)], size=self.body + 1.5,
                      align='center', after=30)
        contact = [person.get('phone'), person.get('email'), t(person.get('location'), self.lang),
                   person.get('linkedin')]
        self.para([(SEP.join(c for c in contact if c), False, GRAY)], align='center', after=40)

    def summary(self):
        text = (self.spec.get('summary') or {}).get('text')
        if text:
            self.section('summary')
            self.para(text.strip(), after=20)

    def experience(self):
        entries = self.spec.get('experience') or []
        if not entries:
            return
        self.section('experience')
        for e in entries:
            _, exp, _ = self.idx.get(e['ref'])
            title = t(exp.get('title'), self.lang) + SEP + t(exp.get('employer'), self.lang)
            meta = fmt_range(exp.get('start'), exp.get('end'), self.lang)
            loc = t(exp.get('location'), self.lang)
            self.entry(title, meta + (SEP + loc if loc else ''))
            self.bullets(e.get('bullets') or [])

    def projects(self):
        entries = self.spec.get('projects') or []
        if not entries:
            return
        self.section('projects')
        for e in entries:
            _, proj, _ = self.idx.get(e['ref'])
            self.entry(t(proj.get('name'), self.lang), '')
            self.bullets(e.get('bullets') or [])

    def education(self):
        entries = self.spec.get('education') or []
        if not entries:
            return
        self.section('education')
        for e in entries:
            _, edu, _ = self.idx.get(e['ref'])
            if edu.get('status') == 'in-progress':
                when = EXPECTED[self.lang].format(date=fmt_ym(edu.get('expected'), self.lang))
            else:
                when = fmt_ym(edu.get('end'), self.lang)
            title = t(edu.get('degree'), self.lang)
            inst = t(edu.get('institution'), self.lang)
            self.entry(title + (SEP + inst if inst else ''), when)
            notes = t(edu.get('notes'), self.lang)
            if notes:
                self.para([(notes, False, GRAY)], after=10)

    def skills(self):
        groups = self.spec.get('skills') or []
        if not groups:
            return
        self.section('skills')
        joiner = ', ' if self.lang == 'en' else ' · '
        for g in groups:
            names = []
            for it in g.get('items') or []:
                if isinstance(it, dict):
                    names.append(it['text'].strip())
                else:
                    names.append(str(self.idx.get(it)[1]['name']))
            parts = []
            if g.get('label'):
                parts.append((g['label'].strip() + ': ', True, INK))
            parts.append((joiner.join(names), False, None))
            self.para(parts, after=15)

    def languages(self):
        ids = self.spec.get('languages') or []
        if not ids:
            return
        self.section('languages')
        out = []
        for iid in ids:
            lang_item = self.idx.get(iid)[1]
            level = t(lang_item.get('level'), self.lang)
            out.append(t(lang_item.get('name'), self.lang) + (f' ({level})' if level else ''))
        self.para(' · '.join(out), after=10)

    def build(self):
        self.setup()
        self.header()
        order = self.spec.get('sections') or ['summary', 'experience', 'projects', 'education',
                                               'skills', 'languages']
        for key in order:
            getattr(self, key)()
        return self.doc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--profile', required=True)
    ap.add_argument('--spec', required=True)
    ap.add_argument('--out', required=True, help='output folder')
    ap.add_argument('--approvals', help='approvals.json (default: next to the spec)')
    args = ap.parse_args()

    profile = load_yaml(args.profile)
    spec = load_json(args.spec)
    ap_path = args.approvals or os.path.join(os.path.dirname(os.path.abspath(args.spec)), 'approvals.json')
    approvals = load_json(ap_path).get('approved', []) if os.path.exists(ap_path) else []

    errors, warnings, _ = fact_check.check(profile, spec, approvals)
    for w in warnings:
        print('WARNING: ' + w)
    if errors:
        for e in errors:
            print('ERROR: ' + e)
        sys.exit('Fact check failed - nothing was written. Run fact_check.py for details.')

    doc = CV(profile, spec).build()
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, spec['fileName'] + '.docx')
    if os.path.exists(path):
        shutil.copy2(path, path + '.bak')
        print('backup: ' + path + '.bak')
    doc.save(path)
    print('saved: ' + path)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
