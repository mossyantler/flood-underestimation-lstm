#!/usr/bin/env python3
"""Build versioned HTML pages from docx backups using pandoc."""
import subprocess
import re
import os

ROOT = '/Users/jang-minyeop/Project/CAMELS'

VERSIONS = [
    {
        'docx': 'draft_original_backup_20260527_005437.docx',
        'out': 'docs/paper/versions/v1_original.html',
        'name': 'v1_original.html',
        'label': 'v1',
        'date': '2026-05-27 00:47',
        'desc': '초기 목차 초안',
    },
    {
        'docx': 'draft_original_backup_20260527_013119.docx',
        'out': 'docs/paper/versions/v2_expanded.html',
        'name': 'v2_expanded.html',
        'label': 'v2',
        'date': '2026-05-27 01:31',
        'desc': '이론 + 수식 확장',
    },
    {
        'docx': 'draft.docx',
        'out': 'docs/paper/versions/v3_current_docx.html',
        'name': 'v3_current_docx.html',
        'label': 'v3',
        'date': '2026-05-27 (진행중)',
        'desc': '현재 작업중 docx',
    },
]

CSS = """\
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Georgia', 'Times New Roman', serif;
    font-size: 11pt;
    line-height: 1.8;
    color: #1a1a1a;
    background: #f8f7f4;
    margin: 0;
  }
  .layout { display: flex; min-height: 100vh; }
  .sidebar {
    width: 210px;
    min-width: 210px;
    background: #1a365d;
    color: #fff;
    padding: 24px 0;
    position: sticky;
    top: 0;
    height: 100vh;
    overflow-y: auto;
    flex-shrink: 0;
  }
  .sidebar-header {
    font-size: 10.5pt;
    font-weight: bold;
    color: #90cdf4;
    padding: 0 16px 12px;
    border-bottom: 1px solid #2c5282;
    margin-bottom: 8px;
    line-height: 1.4;
  }
  .sidebar ul { list-style: none; padding: 0; margin: 0; }
  .sidebar li a {
    display: block;
    padding: 8px 16px;
    color: #bee3f8;
    text-decoration: none;
    font-size: 9pt;
    line-height: 1.5;
    border-left: 3px solid transparent;
    transition: background 0.15s;
    font-family: sans-serif;
  }
  .sidebar li a:hover { background: #2a4a7f; color: #fff; }
  .sidebar li a.active { background: #2a4a7f; border-left-color: #63b3ed; color: #fff; }
  .sidebar li a small { color: #90cdf4; display: block; font-size: 8pt; }
  .sidebar li.sep { border-top: 1px solid #2c5282; margin: 8px 0; }
  .sidebar-footer { padding: 12px 16px 0; border-top: 1px solid #2c5282; margin-top: 10px; }
  .sidebar-footer a { color: #90cdf4; font-size: 8.5pt; text-decoration: none; font-family: sans-serif; }
  .sidebar-footer a:hover { color: #fff; }
  .main-content { flex: 1; min-width: 0; }
  @media (max-width: 700px) {
    .layout { flex-direction: column; }
    .sidebar { width: 100%; height: auto; position: relative; }
  }
  @media print {
    .sidebar { display: none; }
    .page-wrapper { box-shadow: none; padding: 40px; }
  }
  .page-wrapper {
    max-width: 900px;
    margin: 0 auto;
    background: #fff;
    padding: 60px 80px;
    box-shadow: 0 2px 20px rgba(0,0,0,0.08);
    min-height: 100vh;
  }
  .title-block {
    text-align: center;
    margin-bottom: 40px;
    padding-bottom: 30px;
    border-bottom: 2px solid #2c5282;
  }
  .paper-title {
    font-size: 18pt;
    font-weight: bold;
    line-height: 1.4;
    color: #1a365d;
    margin-bottom: 16px;
  }
  .paper-date { font-size: 10pt; color: #718096; }
  .toc {
    background: #f0f4f8;
    border: 1px solid #cbd5e0;
    border-radius: 6px;
    padding: 24px 32px;
    margin-bottom: 48px;
  }
  .toc h2 {
    font-size: 13pt;
    color: #2d3748;
    margin-bottom: 16px;
    border-bottom: 1px solid #cbd5e0;
    padding-bottom: 8px;
  }
  .toc ol { list-style: none; padding: 0; margin: 0; }
  .toc > ol > li { margin-bottom: 6px; font-weight: bold; font-size: 10.5pt; }
  .toc > ol > li > ol {
    margin-top: 4px;
    margin-left: 20px;
    list-style: none;
  }
  .toc > ol > li > ol > li {
    font-weight: normal;
    margin-bottom: 2px;
    font-size: 10pt;
  }
  .toc > ol > li > ol > li > ol {
    margin-top: 2px;
    margin-left: 18px;
    list-style: none;
  }
  .toc > ol > li > ol > li > ol > li {
    font-weight: normal;
    margin-bottom: 1px;
    font-size: 9.5pt;
    color: #4a5568;
  }
  .toc a { color: #2b6cb0; text-decoration: none; }
  .toc a:hover { text-decoration: underline; }
  h1.chapter {
    font-size: 16pt;
    color: #1a365d;
    border-bottom: 2px solid #2c5282;
    padding-bottom: 8px;
    margin-top: 48px;
    margin-bottom: 24px;
  }
  h2.section {
    font-size: 13pt;
    color: #2c5282;
    margin-top: 32px;
    margin-bottom: 14px;
  }
  h3.subsection {
    font-size: 11.5pt;
    color: #2d3748;
    margin-top: 20px;
    margin-bottom: 10px;
    font-style: italic;
  }
  p { margin-bottom: 12px; text-align: justify; }
  .table-container { margin: 20px 0 28px 0; overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; font-size: 10pt; }
  th { background: #2c5282; color: #fff; padding: 8px 12px; text-align: center; font-weight: bold; }
  td { padding: 7px 12px; border: 1px solid #e2e8f0; text-align: center; }
  tr:nth-child(even) td { background: #f7fafc; }
  tr:hover td { background: #ebf4ff; }
  td:first-child { text-align: left; font-weight: 500; }
  .figure-container { margin: 24px 0 8px 0; text-align: center; }
  .figure-container img {
    max-width: 100%;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }
  p.figure-caption {
    font-size: 9.5pt;
    color: #4a5568;
    margin-top: 4px;
    margin-bottom: 24px;
    text-align: center;
    font-style: italic;
  }
  ul, ol { padding-left: 24px; margin-bottom: 12px; }
  li { margin-bottom: 4px; }
  .mjx-chtml { font-size: 105% !important; }
  .references-section { margin-top: 40px; }
  .references-section ol { padding-left: 24px; }
  .references-section li { font-size: 10pt; margin-bottom: 10px; line-height: 1.6; color: #2d3748; }
"""

MATHJAX = """\
<script>
  MathJax = {
    tex: {
      inlineMath: [['\\\\(', '\\\\)']],
      displayMath: [['\\\\[', '\\\\]']],
      tags: 'ams'
    }
  };
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js" async></script>"""


def toc_level(text):
    t = text.strip()
    if re.match(r'^\d+\.\d+\.\d+', t):
        return 3
    if re.match(r'^\d+\.\d+', t):
        return 2
    return 1


def build_toc(items):
    if not items:
        return '<div class="toc"><h2>목차</h2><p>목차 없음</p></div>'

    lines = ['<div class="toc">', '<h2>목차 (Table of Contents)</h2>', '<ol>']
    depth = 1

    for href, text in items:
        lv = toc_level(text)
        if lv == 1:
            while depth > 1:
                lines.append('</li></ol>')
                depth -= 1
            lines.append(f'<li><a href="{href}">{text}</a>')
        elif lv == 2:
            if depth < 2:
                lines.append('<ol>')
                depth = 2
            elif depth == 3:
                lines.append('</li></ol>')
                depth = 2
            lines.append(f'<li><a href="{href}">{text}</a>')
        else:
            if depth < 3:
                lines.append('<ol>')
                depth = 3
            lines.append(f'<li><a href="{href}">{text}</a></li>')

    while depth > 1:
        lines.append('</li></ol>')
        depth -= 1
    lines.append('</li>')
    lines.append('</ol>')
    lines.append('</div>')
    return '\n'.join(lines)


def transform(raw):
    body = raw

    # Fix image paths: pandoc media/ → ../docx_images/
    body = body.replace('src="media/image', 'src="../docx_images/image')

    # Extract and remove TOC block
    toc_html = ''
    toc_m = re.search(r'<h1 class="TOC-Heading"[^>]*>.*?</h1>', body)
    if toc_m:
        toc_start = toc_m.start()
        rest = body[toc_m.end():]
        # Next real h1 (without TOC-Heading class)
        next_m = re.search(r'<h1 (?!class="TOC)', rest)
        toc_end = toc_m.end() + (next_m.start() if next_m else len(rest))
        toc_block = body[toc_start:toc_end]

        # Extract TOC links
        raw_items = re.findall(r'<p><a href="(#[^"]+)">(.*?)</a></p>', toc_block, re.DOTALL)
        items = []
        for href, raw_text in raw_items:
            text = re.sub(r'<[^>]+>', '', raw_text).strip()
            text = re.sub(r'\s+\d+\s*$', '', text).strip()
            if text and not text.startswith('그림') and not text.startswith('표'):
                items.append((href, text))
        toc_html = build_toc(items)
        body = body[:toc_start] + body[toc_end:]

    # Add heading classes
    body = re.sub(r'<h1 id="([^"]+)">', r'<h1 class="chapter" id="\1">', body)
    body = re.sub(r'<h2 id="([^"]+)">', r'<h2 class="section" id="\1">', body)
    body = re.sub(r'<h3 id="([^"]+)">', r'<h3 class="subsection" id="\1">', body)

    # Wrap tables
    body = body.replace('<table>', '<div class="table-container"><table>')
    body = body.replace('</table>', '</table></div>')

    # Wrap standalone images in figure-container
    body = re.sub(
        r'<p>(<img [^>]+/>)\s*</p>',
        r'<div class="figure-container">\1</div>',
        body
    )

    # Caption paragraphs: <p>그림 N.M ... or <p>표 N.M ...
    body = re.sub(
        r'<p>((?:그림|표)\s+[\d.]+[^<]*)</p>',
        r'<p class="figure-caption">\1</p>',
        body
    )

    # Mark references section
    body = re.sub(
        r'(<h1 class="chapter" id="참고문헌[^"]*">)',
        r'<div class="references-section">\1',
        body
    )
    if '<div class="references-section">' in body:
        body = body.rstrip() + '\n</div>'

    return body.strip(), toc_html


def make_sidebar(active_name):
    items = []
    for v in VERSIONS:
        cls = ' class="active"' if v['name'] == active_name else ''
        items.append(
            f'    <li><a href="{v["name"]}"{cls}>'
            f'{v["label"]} — {v["desc"]}'
            f'<br><small>{v["date"]}</small></a></li>'
        )
    items.append('    <li class="sep"></li>')
    items.append('    <li><a href="../paper_draft.html">HTML 논문 초안<br><small>수식 + 그림 포함</small></a></li>')
    return (
        '<nav class="sidebar">\n'
        '  <div class="sidebar-header">📋 버전 기록</div>\n'
        '  <ul>\n'
        + '\n'.join(items) + '\n'
        '  </ul>\n'
        '  <div class="sidebar-footer"><a href="../../index.html">← 변경 이력 홈</a></div>\n'
        '</nav>'
    )


def make_html(body, toc_html, v):
    sidebar = make_sidebar(v['name'])
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Flood LSTM — {v["label"]}: {v["desc"]}</title>
<style>
{CSS}
</style>
{MATHJAX}
</head>
<body>
<div class="layout">
{sidebar}
<div class="main-content">
<div class="page-wrapper">

<div class="title-block" id="top">
  <div class="paper-title">Reducing Extreme Flood Underestimation with<br>Probabilistic Extensions of Multi-Basin LSTM Models</div>
  <div class="paper-date">버전: {v["label"]} ({v["desc"]}) &nbsp;|&nbsp; {v["date"]} &nbsp;|&nbsp; 상태: 초안</div>
</div>

{toc_html}

{body}

</div><!-- page-wrapper -->
</div><!-- main-content -->
</div><!-- layout -->
</body>
</html>"""


def convert(v):
    docx_path = os.path.join(ROOT, v['docx'])
    out_path = os.path.join(ROOT, v['out'])

    result = subprocess.run(
        ['pandoc', docx_path, '-t', 'html', '--mathjax', '--wrap=none'],
        capture_output=True, text=True, cwd=ROOT
    )
    if result.returncode != 0:
        print(f"[ERROR] pandoc failed for {v['label']}: {result.stderr[:200]}")
        return

    body, toc_html = transform(result.stdout)
    html = make_html(body, toc_html, v)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"[OK] {v['out']} ({len(html):,} chars)")


if __name__ == '__main__':
    for v in VERSIONS:
        convert(v)
