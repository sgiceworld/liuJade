#!/usr/bin/env python3
"""
古玉鉴真 — Playwright 定向抓包 (含 POST 请求体) (2026-11-26)

用法: python scripts/probe_pw_post.py <site> <url> <click1> [click2 ...]
记录非静态请求的 method/url/post_data/status/body 前缀, 落盘
scraped_data/_site_probe/domestic_20261126/<site>_pw/post_capture.jsonl
"""
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r'd:/liuJade/scraped_data/_site_probe/domestic_20261126')
STATIC_RE = re.compile(r'\.(js|css|png|jpg|jpeg|gif|svg|ico|woff2?|ttf|map|mp4|mp3|otf|webp)(\?|$)', re.I)
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/125 Safari/537.36 JadeResearchBot/1.0')

captured = []


def on_response(resp):
    url = resp.url
    if STATIC_RE.search(url):
        return
    if any(x in url for x in ('cnzz', 'rumt', 'map.qq', 'pr.map', 'whitelist')):
        return
    try:
        status = resp.status
    except Exception:
        status = -1
    ctype = ''
    try:
        ctype = resp.headers.get('content-type', '') or ''
    except Exception:
        pass
    body = ''
    if 'json' in ctype:
        try:
            body = resp.text()[:2500]
        except Exception:
            body = ''
    post = ''
    try:
        if resp.request.method == 'POST':
            post = resp.request.post_data or ''
    except Exception:
        pass
    rec = {'method': resp.request.method, 'url': url, 'status': status,
           'ctype': ctype, 'post_data': post[:1200], 'body': body}
    captured.append(rec)
    print(f'  [{resp.request.method}] {status} {url[:120]}', flush=True)
    if post:
        print(f'      POST: {post[:300]}', flush=True)


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    site = sys.argv[1]
    url = sys.argv[2]
    clicks = sys.argv[3:]
    work = OUT / f'{site}_pw'
    work.mkdir(parents=True, exist_ok=True)

    print(f'=== {site} {url} clicks={clicks} ===', flush=True)
    with sync_playwright() as p:
        # 国内站强制直连 (2026-11-27: 系统代理 Clash 残留,
        # --no-proxy-server 无效, 须用 --proxy-server=direct://)
        browser = p.chromium.launch(headless=True, args=['--proxy-server=direct://'])
        ctx = browser.new_context(user_agent=UA, viewport={'width': 1440, 'height': 900})
        page = ctx.new_page()
        page.on('response', on_response)
        try:
            page.goto(url, timeout=60000, wait_until='domcontentloaded')
        except Exception as e:
            print(f'  [!] goto 失败: {e}', flush=True)
            browser.close()
            return
        page.wait_for_timeout(6000)

        for t in clicks:
            ok = False
            for sel in (f'text={t}', f'a:has-text("{t}")', f'li:has-text("{t}")',
                        f'div:has-text("{t}")', f'span:has-text("{t}")'):
                try:
                    loc = page.locator(sel)
                    n = loc.count()
                    if n == 0:
                        continue
                    best = None
                    for i in range(min(n, 30)):
                        el = loc.nth(i)
                        try:
                            if not el.is_visible():
                                continue
                            box = el.bounding_box()
                            if box and 10 < box['width'] < 1200 and 5 < box['height'] < 250:
                                best = el
                                break
                        except Exception:
                            continue
                    if best:
                        best.click(timeout=6000)
                        print(f'  [+] clicked {sel}', flush=True)
                        ok = True
                        break
                except Exception:
                    continue
            page.wait_for_timeout(6000)
            if not ok:
                print(f'  [!] 未点击 {t}', flush=True)
        # 滚动触发懒加载
        for _ in range(4):
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(1200)

        out_f = work / 'post_capture.jsonl'
        with open(out_f, 'a', encoding='utf-8') as f:
            for c in captured:
                f.write(json.dumps(c, ensure_ascii=False) + '\n')
        print(f'[*] {site}: {len(captured)} 条 → {out_f}', flush=True)
        browser.close()


if __name__ == '__main__':
    main()
