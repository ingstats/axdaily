#!/usr/bin/env python3
"""기사 원문 링크에서 대표 사진(og:image) 주소를 모아 data/thumbs.json 에 저장한다.

- data/issues/*.json 의 모든 기사 출처 링크를 훑는다.
- 이미 주소를 찾은 링크는 다시 열지 않는다. 못 찾은 링크는 다음 실행 때 다시 시도한다.
- 결과: {"기사 링크": "대표 사진 주소", ...}  (사이트가 기사 제목 옆 작은 사진으로 씀)
GitHub Actions(.github/workflows/thumbs.yml)가 발행물이 올라올 때마다 실행한다.
"""
import glob, html, json, os, re, sys
from urllib.parse import urljoin, quote
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'thumbs.json')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 AXDailyBot/1.0 (+https://axdaily.site/)'
KEYS = ['og:image:secure_url', 'og:image', 'og:image:url', 'twitter:image', 'twitter:image:src']
META = re.compile(r'<meta\b[^>]*>', re.I)
ATTR = re.compile(r'([\w:-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'>]+))')
CHARSET = re.compile(rb'<meta[^>]+charset=["\']?\s*([\w-]+)', re.I)


def pick_image(page, base):
    """HTML 문자열에서 대표 사진 주소를 고른다 (og → twitter 순)."""
    found = {}
    for tag in META.findall(page):
        a = {k.lower(): (v1 or v2 or v3) for k, v1, v2, v3 in ATTR.findall(tag)}
        key = (a.get('property') or a.get('name') or '').strip().lower()
        val = (a.get('content') or '').strip()
        if key in KEYS and val and key not in found:
            found[key] = val
    for k in KEYS:
        if k in found:
            u = urljoin(base, html.unescape(found[k]))
            if u.startswith('//'):
                u = 'https:' + u
            if re.match(r'^https?://', u):
                return quote(u, safe=":/?#[]@!$&'()*+,;=%~")
    return ''


def fetch(url):
    req = Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8'})
    with urlopen(req, timeout=15) as r:
        raw = r.read(800_000)
        cs = r.headers.get_content_charset()
        final = r.geturl()
    if not cs:
        m = CHARSET.search(raw[:4000])
        cs = m.group(1).decode('ascii', 'ignore') if m else 'utf-8'
    try:
        page = raw.decode(cs, 'replace')
    except LookupError:
        page = raw.decode('utf-8', 'replace')
    return page, final


def main():
    try:
        thumbs = json.load(open(OUT, encoding='utf-8'))
    except (OSError, ValueError):
        thumbs = {}
    urls = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'issues', '*.json'))):
        try:
            issue = json.load(open(f, encoding='utf-8'))
        except ValueError:
            continue
        for sec in issue.get('sections', []):
            for it in sec.get('items', []):
                for src in it.get('sources', []):
                    u = src.get('url')
                    if u and u not in urls:
                        urls.append(u)
    new = miss = 0
    for u in urls:
        if thumbs.get(u):
            continue
        try:
            page, final = fetch(u)
            img = pick_image(page, final)
        except Exception as e:  # 사이트가 막거나 느리면 다음 실행 때 다시
            print(f'건너뜀 {u}: {e}', file=sys.stderr)
            img = ''
        if img:
            thumbs[u] = img
            new += 1
        else:
            miss += 1
    thumbs = {k: thumbs[k] for k in sorted(thumbs)}
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(thumbs, fh, ensure_ascii=False, indent=1)
        fh.write('\n')
    print(f'기사 링크 {len(urls)}개 · 새로 찾음 {new} · 못 찾음 {miss} · 전체 {len(thumbs)}')


if __name__ == '__main__':
    main()
