#!/usr/bin/env python3
"""
古玉鉴真 — 国内站快速侦察 (2026-11-26)

对 reachable 国内站逐个: robots.txt → 首页提取藏品入口链接 → 候选入口页
判断静态列表 vs JS 渲染。直连 (trust_env=False), 每请求随机 3-8s 延时,
证据落盘 scraped_data/_site_probe/domestic_20261126/。
"""
import json
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import truststore

truststore.inject_into_ssl()

OUT = Path(r'd:/liuJade/scraped_data/_site_probe/domestic_20261126')
OUT.mkdir(parents=True, exist_ok=True)

SITES = [
    ('nanjing', 'https://www.njmuseum.com'),
    ('shanxi', 'https://www.shanximuseum.com'),
    ('liaoning', 'https://www.lnmuseum.com.cn'),
    ('sichuan', 'https://www.scmuseum.cn'),
    ('guangdong', 'https://www.gdmuseum.com'),
    ('gansu', 'https://www.gansumuseum.com'),
    ('guangxi', 'https://www.gxmuseum.com'),
    ('fujian', 'https://www.fjbwy.com'),
    ('jiangxi', 'https://www.jxmuseum.cn'),
    ('chongqing', 'https://www.3gmuseum.cn'),
    ('yin_ruins', 'https://www.ayyx.com'),
    ('sanxingdui', 'https://www.sxd.cn'),
]

# 藏品入口关键词 (中文博物馆常见栏目名)
COLL_RE = re.compile(r'藏品|典藏|文物|珍宝|珍品|精品|馆藏|collection|treasure|relic|wenwu|cangpin|zangpin', re.I)
# 首页链接里排除明显非藏品栏目
EXCLUDE_RE = re.compile(r'(login|register|weixin|weibo|douyin|video|news|notice|about|contact|visit|guide|ticket|job|zhaopin|yuyue|booking|member|download)', re.I)

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/125 Safari/537.36 JadeResearchBot/1.0')

results = {}


def jitter():
    time.sleep(random.uniform(3, 8))


def get(s, url, **kw):
    kw.setdefault('timeout', 20)
    r = s.get(url, **kw)
    if r.encoding in (None, 'ISO-8859-1'):
        r.encoding = r.apparent_encoding or 'utf-8'
    return r


def probe(site_id, base):
    rec = {'site': site_id, 'base': base, 'robots': None, 'home_links': [],
           'candidates': []}
    s = requests.Session()
    s.trust_env = False
    s.headers.update({'User-Agent': UA})
    host = urlparse(base).netloc
    try:
        r = get(s, urljoin(base, '/robots.txt'))
        rec['robots'] = {'status': r.status_code,
                         'text': r.text[:1500]}
    except Exception as e:
        rec['robots'] = {'error': f'{type(e).__name__}: {e}'}
    print(f"[{site_id}] robots: {rec['robots'].get('status', 'ERR')}", flush=True)
    jitter()

    try:
        r = get(s, base + '/')
        rec['home'] = {'status': r.status_code, 'len': len(r.text),
                       'title': (re.search(r'<title>([^<]*)</title>', r.text) or [None, ''])[1]}
        # 提取含藏品关键词的链接
        seen = set()
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.S):
            href, text = m.group(1).strip(), re.sub(r'<[^>]+>', '', m.group(2)).strip()
            if not COLL_RE.search(text + href):
                continue
            if EXCLUDE_RE.search(href):
                continue
            u = urljoin(base, href)
            if urlparse(u).netloc != host or u in seen:
                continue
            seen.add(u)
            rec['home_links'].append({'href': u, 'text': text[:40]})
            if len(rec['home_links']) >= 12:
                break
        print(f"[{site_id}] 首页 {r.status_code}, 藏品候选链接 {len(rec['home_links'])}", flush=True)
        (OUT / f'{site_id}_home.html').write_text(r.text, encoding='utf-8')
    except Exception as e:
        rec['home'] = {'error': f'{type(e).__name__}: {e}'}
        print(f"[{site_id}] 首页错误: {e}", flush=True)
        results[site_id] = rec
        return
    jitter()

    # 探测每个候选链接: 是否有条目链接 (静态) 或 JS 壳
    for c in rec['home_links'][:6]:
        u = c['href']
        try:
            r = get(s, u)
            n_items = len(re.findall(r'<a[^>]+href="[^"]*(?:detail|show|view|content|info|_id)[^"]*"[^>]*>', r.text))
            n_json = len(re.findall(r'(collectionList|api/|/api|list\?|getList|ajax)', r.text, re.I))
            c['status'] = r.status_code
            c['len'] = len(r.text)
            c['static_item_links'] = n_items
            c['api_hints'] = n_json
            c['title'] = (re.search(r'<title>([^<]*)</title>', r.text) or [None, ''])[1][:60]
            print(f"    {u[:80]} → {r.status_code} items={n_items} api_hints={n_json}", flush=True)
        except Exception as e:
            c['error'] = f'{type(e).__name__}: {e}'
            print(f"    {u[:80]} → ERR {e}", flush=True)
        jitter()
    results[site_id] = rec
    with open(OUT / 'recon.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    return rec


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print('── 国内站侦察开始 (直连, 3-8s 延时) ──', flush=True)
    for sid, base in SITES:
        print(f"\n=== {sid} {base} ===", flush=True)
        try:
            probe(sid, base)
        except Exception as e:
            print(f"[{sid}] 探测异常: {e}", flush=True)
            results[sid] = {'site': sid, 'error': str(e)}
    print('\n── 侦察完成 ──', flush=True)
    for sid in results:
        r = results[sid]
        links = r.get('home_links') or []
        print(f"\n{sid}: 候选 {len(links)}", flush=True)
        for c in links:
            print(f"    {c.get('href','')[:90]} | {c.get('status','?')} "
                  f"items={c.get('static_item_links','?')} api={c.get('api_hints','?')} "
                  f"| {c.get('text','')[:20]}", flush=True)


if __name__ == '__main__':
    main()
