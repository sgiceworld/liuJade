#!/usr/bin/env python3
"""hunan 藏品库详情 XHR 抓包: 点第一条目, 捕获详情 API + 大图。2026-11-19"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r'd:/liuJade/scraped_data/_site_probe/hunan_db')
OUT.mkdir(parents=True, exist_ok=True)
captured = []


def on_response(resp):
    url = resp.url
    if any(x in url for x in ('.jpg', '.png', '.otf', '.js', '.css')):
        return
    try:
        body = resp.text()
    except Exception:
        body = ''
    captured.append({'url': url, 'status': resp.status, 'body': body})
    print(f'[RESP] {resp.status} len={len(body)} {url[:130]}', flush=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/125 Safari/537.36 JadeResearchBot/1.0')
        page = ctx.new_page()
        page.on('response', on_response)
        page.goto('https://de.hnmuseum.com/collection/', timeout=60000,
                  wait_until='domcontentloaded')
        page.wait_for_timeout(8000)
        # 点击第一条目 (卡片/链接)
        try:
            page.locator('.collection-item, .card, a, li').first
            # 更稳: 找含 藏品名称 文本的链接
            loc = page.locator('text=黄克强大印').first
            if loc.count() > 0:
                loc.click(timeout=8000)
                print('[+] clicked 黄克强大印', flush=True)
            else:
                # 任意第一条卡片
                page.locator('img').nth(5).click(timeout=8000)
                print('[+] clicked img[5]', flush=True)
        except Exception as e:
            print(f'[!] click failed: {e}', flush=True)
        page.wait_for_timeout(10000)
        with open(OUT / 'detail_capture.jsonl', 'w', encoding='utf-8') as f:
            for c in captured:
                f.write(json.dumps(c, ensure_ascii=False) + '\n')
        print(f'[*] 捕获 {len(captured)} 条', flush=True)
        (OUT / 'detail_page.html').write_text(page.content(), encoding='utf-8')
        browser.close()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
