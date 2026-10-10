#!/usr/bin/env python3
"""Render a .docx to PDF, count pages, and write PNG previews for a visual check.

Renderer order:
  1. Microsoft Word, via docx2pdf (Windows/macOS). The conversion runs on a copy in a temp
     folder, because Word's export can hang on files inside some synced/user folders.
  2. LibreOffice (soffice --headless) if Word isn't available. WARNING: LibreOffice is more
     forgiving with Hebrew bidi than Word and can hide bugs the employer will see in Word.

Prints a JSON summary. Exit code 0 = exactly one page, 2 = more than one page, 1 = failure.

Usage:
  python render_pdf.py path/to/cv.docx [--dpi 110] [--timeout 180]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile


def via_word(src, dst, timeout):
    code = 'import sys; from docx2pdf import convert; convert(sys.argv[1], sys.argv[2])'
    r = subprocess.run([sys.executable, '-c', code, src, dst], capture_output=True, text=True,
                       timeout=timeout)
    return os.path.exists(dst), (r.stderr or r.stdout).strip()[-500:]


def via_libreoffice(src, outdir, timeout):
    exe = shutil.which('soffice') or shutil.which('libreoffice')
    if not exe:
        return False, 'LibreOffice not found'
    r = subprocess.run([exe, '--headless', '--convert-to', 'pdf', '--outdir', outdir, src],
                       capture_output=True, text=True, timeout=timeout)
    dst = os.path.join(outdir, os.path.splitext(os.path.basename(src))[0] + '.pdf')
    return os.path.exists(dst), (r.stderr or r.stdout).strip()[-500:]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('docx')
    ap.add_argument('--dpi', type=int, default=110)
    ap.add_argument('--timeout', type=int, default=180)
    args = ap.parse_args()

    docx = os.path.abspath(args.docx)
    base = os.path.splitext(docx)[0]
    pdf = base + '.pdf'
    result = {'docx': docx, 'pdf': pdf, 'renderer': None, 'pages': None, 'png': [], 'notes': []}

    with tempfile.TemporaryDirectory(prefix='cv-tailor-') as tmp:
        src = os.path.join(tmp, 'cv.docx')
        dst = os.path.join(tmp, 'cv.pdf')
        shutil.copy2(docx, src)
        ok, log = False, ''
        try:
            import docx2pdf  # noqa: F401
            ok, log = via_word(src, dst, args.timeout)
            if ok:
                result['renderer'] = 'word'
        except ImportError:
            log = 'docx2pdf not installed (python -m pip install docx2pdf)'
        except subprocess.TimeoutExpired:
            log = f'Word export timed out after {args.timeout}s'
        if not ok:
            result['notes'].append('Word render failed: ' + log)
            try:
                ok, log = via_libreoffice(src, tmp, args.timeout)
            except subprocess.TimeoutExpired:
                ok, log = False, 'LibreOffice timed out'
            if ok:
                result['renderer'] = 'libreoffice'
                result['notes'].append('Rendered with LibreOffice: Hebrew bidi problems that only '
                                       'Word shows may be hidden. Check the file in Word.')
            else:
                result['notes'].append('LibreOffice render failed: ' + log)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                sys.exit(1)
        shutil.copy2(dst, pdf)

    import fitz  # pymupdf
    with fitz.open(pdf) as doc:
        result['pages'] = doc.page_count
        # how much of the last page holds text: low on a one-page CV = room for more content
        last = doc[-1]
        bottoms = [b[3] for b in last.get_text('blocks') if b[4].strip()]
        if bottoms:
            result['lastPageFill'] = round(max(bottoms) / last.rect.height, 2)
        for i, page in enumerate(doc):
            png = base + ('.png' if i == 0 else f'-p{i + 1}.png')
            page.get_pixmap(dpi=args.dpi).save(png)
            result['png'].append(png)
    for stale in range(result['pages'] + 1, 10):  # drop previews of pages that no longer exist
        old = base + f'-p{stale}.png'
        if os.path.exists(old):
            os.remove(old)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result['pages'] == 1 else 2)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
