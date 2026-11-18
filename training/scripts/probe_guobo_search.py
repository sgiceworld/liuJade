#!/usr/bin/env python3
"""guobo /SearchAll POST 抓包: 捕获请求 body 与响应 JSON 全量。2026-11-18"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r'd:/liuJade/scraped_data/_site_probe/guobo_searchall')
OUT.mkdir(parents=True, exist_ok=True)

URL = ('https://www.chnmuseum.cn/qwjs/cpjs/'
       '?classification=3,406,&zhidi=3&pinlei=406')
captured = []


def main():
    def on_request(req):
        if 'SearchAll' in req.url:
            print(f'[REQ] {req.method} {req.url}', flush=True)
            print(f'  post_data: {req.post_data}', flush=True)

    def on_response(resp):
        if 'SearchAll' in resp.url:
            try:
                body = resp.text()
            except Exception:
                body = ''
            print(f'[RESP] {resp.status} len={len(body)}', flush=True)
            captured.append({'url': resp.url, 'status': resp.status,
                             'body': body})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/125 Safari/537.36 JadeResearchBot/1.0')
        page = ctx.new_page()
        page.on('request', on_request)
        page.on('response', on_response)
        page.goto(URL, timeout=60000, wait_until='domcontentloaded')
        page.wait_for_timeout(12000)
        with open(OUT / 'searchall.jsonl', 'w', encoding='utf-8') as f:
            for c in captured:
                f.write(json.dumps(c, ensure_ascii=False) + '\n')
        print(f'[*] 捕获 {len(captured)} 个 SearchAll 响应', flush=True)
        (OUT / 'page.html').write_text(page.content(), encoding='utf-8')
        browser.close()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
