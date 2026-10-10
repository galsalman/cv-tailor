#!/usr/bin/env python3
"""Show what a naive ATS parser extracts from a CV: raw text in document order, the contact
fields a regex finds, and anything hidden in places parsers often skip.

Reads the .docx (paragraphs, tables, text boxes, headers/footers) and, if a .pdf with the same
name exists, also the PDF text layer, since many portals parse the PDF instead.

Usage:
  python ats_extract.py path/to/cv.docx
"""
import argparse
import os
import re
import sys

from docx import Document
from docx.oxml.ns import qn

EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE = re.compile(r'(?:\+972[-\s]?|0)(?:[2-9]|5\d)[-\s]?\d{3}[-\s]?\d{4}|\+?\d[\d\s-]{8,}\d')


def docx_text(path):
    doc = Document(path)
    body = [p.text for p in doc.paragraphs]
    tables = []
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                tables.extend(p.text for p in cell.paragraphs)
    boxes = [''.join(t.text or '' for t in tx.iter(qn('w:t')))
             for tx in doc.element.body.iter(qn('w:txbxContent'))]
    hf = []
    for s in doc.sections:
        for part in (s.header, s.footer):
            if not part.is_linked_to_previous:
                hf.extend(p.text for p in part.paragraphs if p.text.strip())
    return body, tables, boxes, hf


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('docx')
    args = ap.parse_args()

    body, tables, boxes, hf = docx_text(args.docx)
    all_text = '\n'.join(body + tables + boxes + hf)

    print('=== DOCX TEXT IN DOCUMENT ORDER ===')
    for line in body:
        if line.strip():
            print(line)
    risks = []
    if tables:
        risks.append(f'{len(tables)} table cell paragraphs: parsers may read them out of order')
    if boxes:
        risks.append(f'{len(boxes)} text boxes: many parsers skip them entirely')
    if hf:
        risks.append(f'header/footer text ({len(hf)} lines): many parsers skip it')
    print('\n=== CONTACT FIELDS A REGEX FINDS ===')
    print('email:', EMAIL.findall(all_text) or 'NOT FOUND')
    print('phone:', PHONE.findall(all_text) or 'NOT FOUND')

    pdf = os.path.splitext(args.docx)[0] + '.pdf'
    if os.path.exists(pdf):
        import fitz
        with fitz.open(pdf) as d:
            pdf_text = '\n'.join(page.get_text() for page in d)
        print('\n=== PDF TEXT LAYER (what a portal that parses the PDF sees) ===')
        print(pdf_text.strip())
        if not EMAIL.search(pdf_text):
            risks.append('email not found in the PDF text layer')
        glued = re.findall(r'\S*(?:[֐-׿][A-Za-z0-9]|[A-Za-z0-9][֐-׿])\S*', pdf_text)
        if glued:
            risks.append(
                f'{len(glued)} Hebrew/English (or Hebrew/number) word pairs are glued together in the '
                f'PDF text layer, e.g. {", ".join(glued[:5])}. The page looks right, but a portal '
                f'that reads PDF text may miss these keywords. This comes from Word\'s PDF export '
                f'of mixed-direction lines. The DOCX text is clean: submit the .docx when the '
                f'portal accepts it.')

    print('\n=== PARSING RISKS ===')
    print('\n'.join('- ' + r for r in risks) if risks else 'none found')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
