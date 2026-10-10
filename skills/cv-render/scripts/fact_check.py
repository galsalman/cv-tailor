#!/usr/bin/env python3
"""Fact check a cv-spec.json against profile.yaml BEFORE any document is written.

Blocking errors (exit code 1):
  - a ref/source id that doesn't exist, is the wrong kind, or belongs to another employer
  - a claim that is do-not-use, or self-reported / not explainable without the user's approval
  - free text that names a skill the user may not claim (e.g. "Python" marked do-not-use)
  - free text that copies a forbidden or unapproved claim under another source
  - a number in a bullet or the summary that its source doesn't contain (inflation)
  - a duration ("3+ years", "שנתיים") longer than the profile's dates support
  - an in-progress degree phrased as completed
  - the same source used twice (one item presented as two)
  - layout below the readability floors (body < 9pt, margins < 0.8cm)
Warnings (exit code 0): heavy rephrasing, skill spelling overrides, Hebrew bidi-risky phrasing.

Usage:
  python fact_check.py --profile profile.yaml --spec jobs/<slug>/cv-spec.json [--approvals ...]
  (approvals default to approvals.json next to the spec)
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from profile_lib import (Index, claim_state, fmt_duration, load_json, load_yaml,  # noqa: E402
                         months_between, parse_ym, t, total_experience_months)

CLAIM_KINDS = ('bullet', 'project', 'project-bullet', 'skill')
HEB = re.compile(r'[֐-׿]')
NUM = re.compile(r'\d+(?:[.,]\d+)?')
WORD = re.compile(r'[\w֐-׿]+', re.UNICODE)

NUMBER_WORDS_EN = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7,
                   'eight': 8, 'nine': 9, 'ten': 10}
DUR_EN = re.compile(
    r'(?P<q>about|around|nearly|almost|over|more than|~)?\s*\+?(?P<n>\d+(?:\.\d+)?|'
    + '|'.join(NUMBER_WORDS_EN) + r')\s*(?P<plus>\+)?\s*(?:-\s*)?(?:years?|yrs?)\b', re.I)
DUR_HE = re.compile(
    r'(?P<q>כ-?|כמעט\s+|מעל\s+|יותר מ-?|למעלה מ-?)?\+?(?P<n>\d+(?:\.\d+)?)\s*(?P<plus>\+)?\s*שנ(?:ים|ות)')
DUR_HE_TWO = re.compile(r'(?P<q>כ-?|כמעט\s+|מעל\s+|יותר מ-?|למעלה מ-?)?שנתיים(?P<plus>\s*\+)?')

COMPLETED_DEGREE = [
    re.compile(r'\b(holds?|holding|earned|completed|graduated with)\s+(an?\s+)?'
               r'(B\.?\s?A|B\.?\s?Sc|M\.?\s?A|M\.?\s?Sc|MBA|bachelor|master|degree)', re.I),
    re.compile(r'\b(B\.?\s?A|B\.?\s?Sc|M\.?\s?A|M\.?\s?Sc|degree|bachelor\'?s?)\s+(graduate|holder)\b', re.I),
    re.compile(r'\bgraduated\b', re.I),
    re.compile(r'(בעל|בעלת)\s+תואר'),
    re.compile(r'בוגר(ת)?\s+(תואר|ה?אוניברסיט|ה?מכלל)'),
    re.compile(r'סיימתי\s+(את\s+)?ה?תואר'),
]


def words(text):
    return {w.lower() for w in WORD.findall(text or '') if len(w) > 1}


def overlap(a, b):
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def numbers(text):
    return {n.replace(',', '') for n in NUM.findall(text or '')}


def item_texts(item):
    """Every language version of an item's text/name, for comparisons."""
    out = []
    for key in ('text', 'name', 'degree'):
        v = item.get(key)
        if isinstance(v, dict):
            out.extend(x for x in v.values() if x)
        elif v:
            out.append(str(v))
    return out


def duration_claims(text):
    """Yield (claimed_years, qualifier, plus, matched_text) for each duration phrase."""
    for m in DUR_EN.finditer(text):
        n = m.group('n').lower()
        n = NUMBER_WORDS_EN.get(n, None) or float(n)
        yield float(n), (m.group('q') or '').strip().lower(), bool(m.group('plus')), m.group(0).strip()
    for m in DUR_HE.finditer(text):
        yield float(m.group('n')), (m.group('q') or '').strip(), bool(m.group('plus')), m.group(0).strip()
    for m in DUR_HE_TWO.finditer(text):
        yield 2.0, (m.group('q') or '').strip(), bool(m.group('plus')), m.group(0).strip()


def duration_ok(years, qualifier, plus, months):
    need = years * 12
    if qualifier in ('about', 'around', '~', 'כ-', 'כ'):
        return months >= need - 3
    if qualifier in ('nearly', 'almost', 'כמעט'):
        return months >= need - 12 and months < need
    return months >= need  # plain, "+", "over", "more than", "מעל", "יותר מ"


def check(profile, spec, approvals):
    errors, warnings, facts = [], [], []
    idx = Index(profile)
    lang = spec.get('language')
    approved = set(approvals or [])

    for dup in idx.duplicates:
        errors.append(f'profile.yaml: id "{dup}" is used more than once; ids must be unique')
    if lang not in ('he', 'en'):
        errors.append('spec.language must be "he" or "en"')
        lang = 'en'

    # ---- facts the builder may rely on --------------------------------------------------
    total = total_experience_months(profile)
    facts.append(f'total experience: {fmt_duration(total)} ({total} months)')
    exp_months = {}
    for exp in profile.get('experience') or []:
        mm = months_between(exp.get('start'), exp.get('end'))
        exp_months[exp.get('id')] = mm
        facts.append(f'{exp.get("id")}: {exp.get("start")} -> {exp.get("end")} = {fmt_duration(mm)}')
    in_progress = [e for e in profile.get('education') or [] if e.get('status') == 'in-progress']
    for e in in_progress:
        facts.append(f'{e.get("id")}: in progress, expected {e.get("expected")}')

    # ---- layout floors -------------------------------------------------------------------
    layout = spec.get('layout') or {}
    if float(layout.get('bodySize', 9.5)) < 9:
        errors.append('layout.bodySize is below the 9pt floor')
    if float(layout.get('marginCm', 1.3)) < 0.8:
        errors.append('layout.marginCm is below the 0.8cm floor')

    used_sources, used_refs = {}, {}
    free_texts = []  # (where, text, source_item_or_None, context_months)

    def use_claim(where, iid, expect_kinds, parent_id=None):
        """Validate one referenced id; return its (kind, item, parent) or None."""
        hit = idx.get(iid)
        if not hit:
            errors.append(f'{where}: unknown id "{iid}"')
            return None
        kind, item, parent = hit
        if kind not in expect_kinds:
            errors.append(f'{where}: "{iid}" is a {kind}, expected {"/".join(expect_kinds)}')
            return None
        if parent_id and kind in ('bullet', 'project-bullet') and (parent or {}).get('id') != parent_id:
            errors.append(f'{where}: "{iid}" belongs to "{(parent or {}).get("id")}", '
                          f'not "{parent_id}" - claims may not move between entries')
            return None
        # education/experience/language "status" means something else (in-progress etc.)
        state = claim_state(item, parent) if kind in CLAIM_KINDS else 'ok'
        if state == 'never':
            errors.append(f'{where}: "{iid}" is marked do-not-use')
        elif state == 'ask' and iid not in approved:
            errors.append(f'{where}: "{iid}" is self-reported or not explainable and the user '
                          f'has not approved it (approvals.json)')
        return hit

    def mark_used(where, iid, bucket):
        if iid in bucket:
            errors.append(f'{where}: "{iid}" is used twice ({bucket[iid]}) - one item, one entry')
        else:
            bucket[iid] = where

    # ---- experience ----------------------------------------------------------------------
    for i, entry in enumerate(spec.get('experience') or []):
        ref = entry.get('ref')
        where = f'experience[{i}]'
        if not use_claim(where, ref, ('experience',)):
            continue
        mark_used(where, ref, used_refs)
        for j, b in enumerate(entry.get('bullets') or []):
            bw = f'{where}.bullets[{j}]'
            hit = use_claim(bw, b.get('source'), ('bullet',), parent_id=ref)
            mark_used(bw, b.get('source'), used_sources)
            free_texts.append((bw, b.get('text', ''), hit[1] if hit else None, exp_months.get(ref)))

    # ---- projects ------------------------------------------------------------------------
    for i, entry in enumerate(spec.get('projects') or []):
        ref = entry.get('ref')
        where = f'projects[{i}]'
        if not use_claim(where, ref, ('project',)):
            continue
        mark_used(where, ref, used_refs)
        for j, b in enumerate(entry.get('bullets') or []):
            bw = f'{where}.bullets[{j}]'
            src = b.get('source')
            kinds = ('project-bullet', 'project')
            hit = use_claim(bw, src, kinds, parent_id=ref) if src != ref else idx.get(ref)
            mark_used(bw, src, used_sources)
            free_texts.append((bw, b.get('text', ''), hit[1] if hit else None, None))

    # ---- education / languages -----------------------------------------------------------
    for i, entry in enumerate(spec.get('education') or []):
        if use_claim(f'education[{i}]', entry.get('ref'), ('education',)):
            mark_used(f'education[{i}]', entry.get('ref'), used_refs)
    for i, iid in enumerate(spec.get('languages') or []):
        if use_claim(f'languages[{i}]', iid, ('language',)):
            mark_used(f'languages[{i}]', iid, used_refs)

    # ---- skills ----------------------------------------------------------------------------
    for i, group in enumerate(spec.get('skills') or []):
        for j, it in enumerate(group.get('items') or []):
            where = f'skills[{i}].items[{j}]'
            iid = it if isinstance(it, str) else it.get('source')
            hit = use_claim(where, iid, ('skill',))
            mark_used(where, iid, used_sources)
            if isinstance(it, dict) and hit:
                warnings.append(f'{where}: "{hit[1].get("name")}" will print as "{it.get("text")}" '
                                f'- confirm this is the same thing')
                free_texts.append((where, it.get('text', ''), hit[1], None))

    # ---- summary / headline ----------------------------------------------------------------
    summary = spec.get('summary') or {}
    summary_sources = []
    for k, iid in enumerate(summary.get('sources') or []):
        hit = use_claim(f'summary.sources[{k}]', iid,
                        ('bullet', 'project-bullet', 'project', 'skill', 'experience', 'education'))
        if hit:
            summary_sources.append(hit[1])
    if summary.get('text'):
        free_texts.append(('summary', summary['text'], summary_sources, None))
    if spec.get('headline'):
        free_texts.append(('headline', spec['headline'], [], None))

    # ---- free-text checks ------------------------------------------------------------------
    blocked_skills = []
    blocked_claims = []
    for iid, (kind, item, parent) in idx.items.items():
        if kind not in CLAIM_KINDS:
            continue
        state = claim_state(item, parent)
        if state == 'never' or (state == 'ask' and iid not in approved):
            if kind == 'skill' and item.get('name'):
                blocked_skills.append((iid, str(item['name']), state))
            if kind in ('bullet', 'project-bullet'):
                blocked_claims.append((iid, item, state))

    for where, text, src, ctx_months in free_texts:
        if not text:
            errors.append(f'{where}: empty text')
            continue
        # forbidden skill names
        for iid, name, state in blocked_skills:
            if re.search(r'(?<![\w])' + re.escape(name) + r'(?![\w])', text, re.I):
                why = 'do-not-use' if state == 'never' else 'not approved'
                errors.append(f'{where}: mentions "{name}" ({iid} is {why})')
        # forbidden claims copied under another source
        for iid, item, state in blocked_claims:
            if isinstance(src, dict) and src.get('id') == iid:
                continue
            if any(overlap(text, other) >= 0.7 for other in item_texts(item)):
                errors.append(f'{where}: text closely matches "{iid}", which is '
                              f'{"do-not-use" if state == "never" else "not approved"}')
        # numbers must come from the source(s)
        sources = src if isinstance(src, list) else ([src] if src else [])
        allowed_nums = set()
        for s in sources:
            for tx in item_texts(s) + [str(s.get('context', ''))]:
                allowed_nums |= numbers(tx)
        duration_spans = [c[3] for c in duration_claims(text)]
        scrubbed = text
        for span in duration_spans:
            scrubbed = scrubbed.replace(span, ' ')
        for n in numbers(scrubbed) - allowed_nums:
            errors.append(f'{where}: number "{n}" does not appear in its source - no new numbers')
        # durations
        months = ctx_months if ctx_months is not None else total
        for years, q, plus, span in duration_claims(text):
            if not duration_ok(years, q, plus, months):
                errors.append(f'{where}: "{span}" is not supported - the dates give '
                              f'{fmt_duration(months)}')
        # degree phrasing
        if in_progress:
            for rx in COMPLETED_DEGREE:
                m = rx.search(text)
                if m:
                    errors.append(f'{where}: "{m.group(0)}" reads as a completed degree, but '
                                  f'{in_progress[0].get("id")} is in progress')
        # drift from the source
        if isinstance(src, dict) and src.get('text'):
            best = max((overlap(text, o) for o in item_texts(src)), default=0)
            if best < 0.35:
                warnings.append(f'{where}: wording moved far from "{src.get("id")}" - confirm the '
                                f'user would say this in an interview')
        # Hebrew bidi-risky phrasing (see skills/hebrew-docx/SKILL.md)
        if lang == 'he' and HEB.search(text):
            if re.search(r'[A-Za-z][A-Za-z0-9]*,\s*[֐-׿]', text):
                warnings.append(f'{where}: comma right after a Latin word before Hebrew - Word '
                                f'misplaces it; join with ו instead')
            if re.search(r'[A-Za-z][.]?\s*$', text):
                warnings.append(f'{where}: line ends with a Latin word - end it with Hebrew')
            if re.search(r'[A-Za-z],?\s+\d|\d,?\s+[A-Za-z]', text):
                warnings.append(f'{where}: a number sits right next to a Latin term - put Hebrew '
                                f'between them')
            first = next((c for c in text if c.isalpha()), '')
            if where.startswith(('experience', 'projects')) and first and not HEB.match(first):
                warnings.append(f'{where}: Hebrew bullet starts with a Latin word - the bullet '
                                f'dash will land on the wrong side; start with a Hebrew verb')

    # ---- Hebrew bidi risks in text that comes straight from the profile ---------------------
    if lang == 'he':
        profile_lines = []
        for e in spec.get('experience') or []:
            hit = idx.get(e.get('ref'))
            if hit:
                profile_lines += [t(hit[1].get('title'), 'he'), t(hit[1].get('employer'), 'he')]
        for e in spec.get('education') or []:
            hit = idx.get(e.get('ref'))
            if hit:
                profile_lines += [t(hit[1].get('degree'), 'he'), t(hit[1].get('institution'), 'he')]
        for e in spec.get('projects') or []:
            hit = idx.get(e.get('ref'))
            if hit:
                profile_lines.append(t(hit[1].get('name'), 'he'))
        for line in filter(None, profile_lines):
            if re.search(r'\(\s*\d|\d\s*\)', line) and HEB.search(line):
                warnings.append(f'profile text "{line}": brackets around a number in a Hebrew line '
                                f'render mirrored in Word - reword it in profile.yaml (e.g. "בהיקף 40 שעות")')
            if re.search(r'[A-Za-z][A-Za-z0-9]*,\s*[֐-׿]', line):
                warnings.append(f'profile text "{line}": comma right after a Latin word before Hebrew '
                                f'- reword it in profile.yaml')

    # ---- file name ---------------------------------------------------------------------------
    name_en = t((profile.get('person') or {}).get('name'), 'en')
    last = name_en.split()[-1] if name_en else ''
    if not spec.get('fileName'):
        errors.append('spec.fileName is missing')
    elif last and last.lower() not in spec['fileName'].lower():
        warnings.append(f'fileName "{spec["fileName"]}" does not contain the last name "{last}"')

    return errors, warnings, facts


STATUSES = {'verified', 'self-reported', 'do-not-use'}


def check_profile(profile):
    """Structural check of profile.yaml on its own (run with no --spec)."""
    errors, warnings = [], []
    idx = Index(profile)
    for dup in idx.duplicates:
        errors.append(f'id "{dup}" is used more than once')
    if not t((profile.get('person') or {}).get('name'), 'en') and not t((profile.get('person') or {}).get('name'), 'he'):
        errors.append('person.name is empty')
    for iid, (kind, item, parent) in idx.items.items():
        where = f'{kind} "{iid}"'
        if kind in CLAIM_KINDS:
            st = item.get('status')
            if st not in STATUSES:
                errors.append(f'{where}: status must be one of {sorted(STATUSES)}, got {st!r}')
            if not isinstance(item.get('explainable'), bool):
                errors.append(f'{where}: explainable must be true or false')
        if kind == 'experience':
            ok = True
            for key in ('start', 'end'):
                try:
                    if not parse_ym(item.get(key)):
                        raise ValueError
                except (ValueError, IndexError, TypeError):
                    ok = False
                    errors.append(f'{where}: {key} must be YYYY-MM{" or present" if key == "end" else ""}')
            if ok and months_between(item.get('start'), item.get('end')) < 0:
                errors.append(f'{where}: end is before start')
        if kind == 'education':
            st = item.get('status')
            if st not in ('completed', 'in-progress'):
                errors.append(f'{where}: status must be completed or in-progress')
            if st == 'in-progress' and not item.get('expected'):
                errors.append(f'{where}: in-progress education needs an expected date (YYYY-MM)')
    for tg in profile.get('targets') or []:
        for ref in tg.get('lead_with') or []:
            if not idx.get(ref):
                errors.append(f'targets "{tg.get("track")}": lead_with "{ref}" is not an id in the profile')
    unreviewed = [i for i, (k, it, _) in idx.items.items()
                  if k in CLAIM_KINDS and it.get('status') == 'self-reported']
    if unreviewed:
        warnings.append(f'{len(unreviewed)} item(s) are self-reported and will need your OK '
                        f'before any CV uses them: {", ".join(unreviewed[:12])}')
    return errors, warnings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--profile', required=True)
    ap.add_argument('--spec', help='cv-spec.json; omit to check the profile on its own')
    ap.add_argument('--approvals', help='approvals.json (default: next to the spec)')
    args = ap.parse_args()

    profile = load_yaml(args.profile)
    if not args.spec:
        errors, warnings = check_profile(profile)
        for w in warnings:
            print('WARNING: ' + w)
        for e in errors:
            print('ERROR: ' + e)
        print('PROFILE CHECK: ' + ('FAILED' if errors else 'PASSED'))
        sys.exit(1 if errors else 0)

    spec = load_json(args.spec)
    ap_path = args.approvals or os.path.join(os.path.dirname(os.path.abspath(args.spec)), 'approvals.json')
    approvals = load_json(ap_path).get('approved', []) if os.path.exists(ap_path) else []

    errors, warnings, facts = check(profile, spec, approvals)
    print('FACTS')
    for f in facts:
        print('  ' + f)
    if warnings:
        print('WARNINGS')
        for w in warnings:
            print('  - ' + w)
    if errors:
        print('ERRORS (the CV will not be built until these are fixed)')
        for e in errors:
            print('  - ' + e)
        print('FACT CHECK: FAILED')
        sys.exit(1)
    print('FACT CHECK: PASSED')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
