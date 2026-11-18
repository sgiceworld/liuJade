#!/usr/bin/env python3
"""
古玉鉴真 — 国内站客户端 API 抓包探测 (通用)

用法:
    python probe_site_api.py --site guobo --url https://www.chnmuseum.cn/zp/
        [--click "selector" ...] [--click-text "玉器"]

Playwright headless 打开目标页, 捕获 XHR/fetch (非静态资源) 请求与 JSON
响应, 落盘 scraped_data/_site_probe/{site}/capture.jsonl + page.html +
page.png。--click-text 点击含指定文本的元素触发列表加载。

伦理: 单次浏览器会话, 少量页面加载, 不并发不重放。
2026-11-18
"""
import argparse
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

STATIC_RE = re.compile(r'\.(js|css|png|jpg|jpeg|gif|svg|ico|woff2?|ttf|map)(\?|$)', re.I)
API_HINT_RE = re.compile(r'api|list|search|json|ajax|data|query|collection', re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', required=True)
    ap.add_argument('--url', required=True)
    ap.add_argument('--click-text', nargs='*', default=[])
    ap.add_argument('--scroll', type=int, default=4)
    ap.add_argument('--wait-ms', type=int, default=6000)
    args = ap.parse_args()

    out = Path(r'd:/liuJade/scraped_data/_site_probe') / args.site
    out.mkdir(parents=True, exist_ok=True)
    captured = []

    def on_response(resp):
        url = resp.url
        if STATIC_RE.search(url):
            return
        try:
            status = resp.status
        except Exception:
            status = -1
        ctype = ''
        try:
            ctype = resp.headers.get('content-type', '')
        except Exception:
            pass
        body = ''
        if 'json' in ctype:
            try:
                body = resp.text()
            except Exception:
                body = ''
        captured.append({'method': resp.request.method, 'url': url,
                         'status': status, 'ctype': ctype, 'body': body})
        flag = '★' if ('json' in ctype and body) else ' '
        print(f'[{flag}] {resp.request.method} {status} {url[:130]}', flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/125 Safari/537.36 JadeResearchBot/1.0',
            viewport={'width': 1440, 'height': 900},
        )
        page = ctx.new_page()
        page.on('response', on_response)

        print(f'[*] goto {args.url}', flush=True)
        page.goto(args.url, timeout=60000, wait_until='domcontentloaded')
        page.wait_for_timeout(args.wait_ms)

        for txt in args.click_text:
            try:
                loc = page.locator(f'text={txt}').first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=8000)
                    print(f'[+] clicked text={txt}', flush=True)
                    page.wait_for_timeout(args.wait_ms)
                else:
                    print(f'[!] text={txt} 不可见, 跳过', flush=True)
            except Exception as e:
                print(f'[!] click text={txt} 失败: {e}', flush=True)

        for _ in range(args.scroll):
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(1200)

        # 保存
        with open(out / 'capture.jsonl', 'w', encoding='utf-8') as f:
            for c in captured:
                f.write(json.dumps(c, ensure_ascii=False) + '\n')
        print(f'[*] 捕获 {len(captured)} 条 → {out / "capture.jsonl"}', flush=True)
        (out / 'page.html').write_text(page.content(), encoding='utf-8')
        page.screenshot(path=str(out / 'page.png'), full_page=False)
        print('[*] page.html + page.png saved', flush=True)
        browser.close()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
