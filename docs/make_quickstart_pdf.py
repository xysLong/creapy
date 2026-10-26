"""
docs/QUICKSTART.md -> docs/QUICKSTART.pdf with Qt's own HTML renderer (no LaTeX, no pandoc): the two-page hand-out.
Run:  QT_QPA_PLATFORM=offscreen python docs/make_quickstart_pdf.py
"""
import os
import re
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextDocument, QPdfWriter, QPageSize, QPageLayout
from PySide6.QtCore import QMarginsF, QSizeF

HERE = os.path.dirname(os.path.abspath(__file__))


def join_wrapped_lines(md):
    # a wrapped paragraph or list item becomes one line, so **bold** across a line break is still recognised
    out = []
    for line in md.splitlines():
        continuation = (out and out[-1].strip() and not out[-1].startswith(('#', '|'))
                        and line.startswith((' ', '\t')) or
                        (out and out[-1].strip() and not out[-1].startswith(('#', '|', '-', '*')) and
                         not re.match(r'^\s*(\d+\.|[-*#|])', line) and line.strip()))
        if continuation:
            out[-1] = out[-1].rstrip() + ' ' + line.strip()
        else:
            out.append(line)
    return '\n'.join(out)


def markdown_to_html(md):
    # the small Markdown subset used in QUICKSTART.md: headings, paragraphs, lists, tables, bold/italic/code
    html = []
    in_list = None
    in_table = False
    for line in join_wrapped_lines(md).splitlines():
        if line.startswith('|'):
            cells = [c.strip() for c in line.strip('|').split('|')]
            if all(re.fullmatch(r'-+', c) for c in cells):
                continue
            if not in_table:
                html.append('<table cellpadding="4" cellspacing="0" border="1" style="border-collapse: collapse;">')
                in_table = True
            html.append('<tr>' + ''.join(f'<td style="border: 1px solid #999; padding: 3px;">{inline(c)}</td>'
                                          for c in cells) + '</tr>')
            continue
        elif in_table:
            html.append('</table>')
            in_table = False
        m = re.match(r'^(#+)\s+(.*)', line)
        if m:
            if in_list:
                html.append(f'</{in_list}>')
                in_list = None
            level = len(m.group(1))
            html.append(f'<h{level}>{inline(m.group(2))}</h{level}>')
        elif re.match(r'^\s*[-*]\s+', line) or re.match(r'^\s*\d+\.\s+', line):
            kind = 'ol' if re.match(r'^\s*\d+\.', line) else 'ul'
            if in_list != kind:
                if in_list:
                    html.append(f'</{in_list}>')
                html.append(f'<{kind}>')
                in_list = kind
            item = re.sub(r'^\s*([-*]|\d+\.)\s+', '', line)
            html.append(f'<li>{inline(item)}</li>')
        elif line.strip() == '':
            if in_list:
                html.append(f'</{in_list}>')
                in_list = None
            html.append('')
        else:
            if in_list and line.startswith('  '):
                html[-1] = html[-1][:-5] + ' ' + inline(line.strip()) + '</li>'
            elif html and html[-1] and not html[-1].startswith('<') and not html[-1].endswith('>'):
                html[-1] += ' ' + inline(line)
            else:
                html.append(f'<p>{inline(line)}</p>' if not (html and html[-1].startswith('<p>') and not html[-1].endswith('</p>'))
                            else inline(line))
    if in_list:
        html.append(f'</{in_list}>')
    if in_table:
        html.append('</table>')
    return '\n'.join(html)


def inline(text):
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)
    return text


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    md = open(os.path.join(HERE, 'QUICKSTART.md'), encoding='utf-8').read()
    body = markdown_to_html(md)
    css = ("body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; color: #111; }"
           "h1 { font-size: 17pt; margin-bottom: 2pt; } h2 { font-size: 12pt; margin-top: 10pt; margin-bottom: 2pt; "
           "color: #1f4e8c; } p { margin: 3pt 0; } li { margin: 1pt 0; } td { font-size: 9pt; }"
           "code { font-family: Menlo, monospace; font-size: 8.5pt; background: #eef; }")
    doc = QTextDocument()
    doc.setDefaultStyleSheet(css)
    doc.setHtml(f"<html><body>{body}</body></html>")
    out = os.path.join(HERE, 'QUICKSTART.pdf')
    writer = QPdfWriter(out)
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageMargins(QMarginsF(16, 14, 16, 14), QPageLayout.Millimeter)
    writer.setResolution(72)  # 1 px = 1 pt, so the CSS point sizes are what they say
    doc.setPageSize(QSizeF(writer.width(), writer.height()))
    doc.print_(writer)
    print(f"written {out} ({doc.pageCount()} pages)")


if __name__ == '__main__':
    main()
