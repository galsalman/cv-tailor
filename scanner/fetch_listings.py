#!/usr/bin/env python3
"""Collect NEW job postings from Israeli job sites for the cv-tailor scan (no AI involved).

Reads the search terms and sites from the "scan" section of cv-tailor.config.json, fetches the
search-result pages, extracts posting links, drops links seen in earlier runs, then fetches each
new posting's title and a short requirements snippet. The scan agent reads these snippets
instead of whole pages, which keeps usage low.

Output (in the job-search folder):
  scan/results/candidates_<stamp>.json   [{site, url, title, requirements}]
  scan/seen_urls.txt                     every link already listed, one per line

Sites: drushim, alljobs, jobmaster. "linkedin" (its public guest search) only if the user added
it to scan.sites themselves: LinkedIn's terms forbid automated collection.

Usage:
  python fetch_listings.py [--root <job-search folder>] [--max-new 80]
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
SITES = ('drushim', 'alljobs', 'jobmaster', 'linkedin')
LINK_PATTERNS = {
    'drushim': (r'/job/\d+/[0-9a-f]+/', 'https://www.drushim.co.il'),
    'alljobs': (r'/Search/UploadSingle\.aspx\?JobID=\d+', 'https://www.alljobs.co.il'),
    'jobmaster': (r'/jobs/checknum\.asp\?key=\d+', 'https://www.jobmaster.co.il'),
    'linkedin': (r'https://[a-z]{2,3}\.linkedin\.com/jobs/view/[^"?&]+|/jobs/view/[^"?&]+',
                 'https://www.linkedin.com'),
}
REQ_MARKERS = ['דרישות התפקיד', 'דרישות המשרה', 'דרישות:', 'דרישות', 'מה אנחנו מחפשים',
               'Requirements', 'Qualifications', "What we're looking for", "What you'll need"]


def q(s):
    return urllib.parse.quote(s, safe='')  # a '/' in a term (אנליסט/ית) must not split the path


def search_urls(sites, terms_he, terms_en):
    for t in terms_he + terms_en:
        if 'drushim' in sites:
            yield 'drushim', f'https://www.drushim.co.il/jobs/search/{q(t)}/'
        if 'alljobs' in sites:
            yield 'alljobs', f'https://www.alljobs.co.il/SearchResultsGuest.aspx?page=1&freetxt={q(t)}'
        if 'jobmaster' in sites:
            yield 'jobmaster', f'https://www.jobmaster.co.il/jobs/?q={q(t)}'
        if 'linkedin' in sites:
            # f_TPR=r86400: posted in the last 24 hours
            yield 'linkedin', ('https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search'
                               f'?keywords={q(t)}&location=Israel&f_TPR=r86400&start=0')


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'he,en;q=0.8'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', errors='replace')


def requirements(text):
    """Plain-text snippet of the requirements section (or the page description)."""
    body = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', text, flags=re.S | re.I)
    body = html.unescape(re.sub(r'<[^>]+>', ' ', body))
    body = re.sub(r'\s+', ' ', body)
    for marker in REQ_MARKERS:
        i = body.find(marker)
        if i != -1:
            return body[i:i + 700].strip()
    m = re.search(r'<meta[^>]+(?:name|property)="(?:og:)?description"[^>]+content="([^"]*)"', text, re.I)
    return html.unescape(m.group(1)).strip()[:700] if m else ''


def page_title(text):
    m = re.search(r'<title[^>]*>(.*?)</title>', text, re.S | re.I)
    t = html.unescape(m.group(1)) if m else ''
    return re.sub(r'\s+', ' ', t).strip()[:200]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default='.', help='job-search folder (default: current folder)')
    ap.add_argument('--max-new', type=int, default=None, help='cap on new postings opened per run')
    args = ap.parse_args()

    root = Path(args.root).resolve()
    try:
        cfg = json.loads((root / 'cv-tailor.config.json').read_text(encoding='utf-8')).get('scan') or {}
    except (OSError, ValueError) as e:
        sys.exit(f'cannot read cv-tailor.config.json in {root}: {e}')
    sites = [s for s in cfg.get('sites', ['drushim', 'alljobs', 'jobmaster']) if s in SITES]
    terms = cfg.get('terms') or {}
    terms_he, terms_en = list(terms.get('he') or []), list(terms.get('en') or [])
    if not (terms_he or terms_en):
        sys.exit('scan.terms is empty in cv-tailor.config.json - run /cv-tailor:scan-setup first')
    max_new = args.max_new or int(cfg.get('maxNew', 80))

    scan_dir = root / 'scan'
    seen_file = scan_dir / 'seen_urls.txt'
    seen = set(seen_file.read_text(encoding='utf-8').split()) if seen_file.exists() else set()

    found, errors = {}, []
    for site, url in search_urls(sites, terms_he, terms_en):
        try:
            text = fetch(url)
        except Exception as e:  # noqa: BLE001 - log and continue
            errors.append(f'{site} {url[:90]}: {e}')
            continue
        pattern, base = LINK_PATTERNS[site]
        for link in set(re.findall(pattern, text)):
            full = link if link.startswith('http') else base + link
            full = full.split('?trk=')[0]
            if full not in seen:
                found.setdefault(full, site)
        time.sleep(1)  # be polite to the sites

    # Take sites in turn so no single site fills the cap; the rest wait for the next run.
    by_site = {}
    for full, site in found.items():
        by_site.setdefault(site, []).append(full)
    picked = []
    while len(picked) < max_new and any(by_site.values()):
        for site in list(by_site):
            if by_site[site] and len(picked) < max_new:
                picked.append((by_site[site].pop(0), site))

    candidates = []
    for full, site in picked:
        title, req = '', ''
        try:
            text = fetch(full)
            title, req = page_title(text), requirements(text)
        except Exception as e:  # noqa: BLE001
            title = f'(could not open: {e})'
        candidates.append({'site': site, 'url': full, 'title': title, 'requirements': req})
        time.sleep(0.5)

    stamp = time.strftime('%Y-%m-%d_%H%M')
    out = scan_dir / 'results' / f'candidates_{stamp}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(candidates, ensure_ascii=False, indent=1), encoding='utf-8')
    with seen_file.open('a', encoding='utf-8') as f:
        for c in candidates:
            f.write(c['url'] + '\n')

    print(f'sites={",".join(sites)} candidates={len(candidates)} new_total={len(found)} '
          f'search_errors={len(errors)} file={out}')
    for e in errors[:20]:
        print('ERROR', e)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
