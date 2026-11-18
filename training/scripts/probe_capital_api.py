#!/usr/bin/env python3
"""
古玉鉴真 — capital_museum (首都博物馆) 客户端 API 抓包探测

用 Playwright headless 打开藏品页, 点击「玉器」分类, 捕获 XHR/fetch
请求与 JSON 响应, 落盘供分析 (参照 colbase 挖接口手法)。
2026-11-18
"""
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r'd:/liuJade/scraped_data/_capital_probe/playwright_capture')
OUT.mkdir(parents=True, exist_ok=True)

BASE = 'https://www.capitalmuseum.org.cn'
STATIC_RE = re.compile(r'\.(js|css|png|jpg|jpeg|gif|svg|ico|woff2?|ttf|map)(\?|$)', re.I)

captured = []  # (method, url, status, body_text)


def on_response(resp):
    url = resp.url
    if STATIC_RE.search(url):
        return
    try:
        status = resp.status
    except Exception:
        status = -1
    body = ''
    ctype = ''
    try:
        ctype = resp.headers.get('content-type', '')
    except Exception:
        pass
    if 'json' in ctype or status != 200 or not STATIC_RE.search(url):
        try:
            body = resp.text()
        except Exception:
            body = ''
    if not STATIC_RE.search(url):
        captured.append((resp.request.method, url, status, body[:2000]))
        print(f'[XHR] {resp.request.method} {status} {url[:120]}', flush=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/125 Safari/537.36 JadeResearchBot/1.0',
            viewport={'width': 1440, 'height': 900},
        )
        page = ctx.new_page()
        page.on('response', on_response)

        print(f'[*] goto {BASE}/collection', flush=True)
        page.goto(f'{BASE}/collection', timeout=60000, wait_until='domcontentloaded')
        page.wait_for_timeout(6000)

        # 找「玉器」分类链接并点击
        try:
            links = page.locator('a, li, div', has_text='玉器')
            print(f'[*] 含玉器文本元素数: {links.count()}', flush=True)
            for i in range(min(links.count(), 20)):
                el = links.nth(i)
                txt = (el.inner_text() or '').strip()
                href = el.get_attribute('href') or ''
                print(f'    [{i}] text={txt[:20]!r} href={href[:80]!r} tag={el.evaluate("e=>e.tagName")}',
                      flush=True)
        except Exception as e:
            print(f'[!] 玉器元素查找失败: {e}', flush=True)

        # 尝试点击玉器
        clicked = False
        for sel in ['a:has-text("玉器")', 'li:has-text("玉器")', 'text=玉器']:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    loc.click(timeout=8000)
                    clicked = True
                    print(f'[+] clicked {sel}', flush=True)
                    break
            except Exception as e:
                print(f'[!] click {sel} 失败: {e}', flush=True)
        page.wait_for_timeout(8000)
        if not clicked:
            print('[!] 未能点击玉器分类', flush=True)

        # 滚动触发懒加载 + 尝试翻页
        for _ in range(6):
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(1500)

        # 翻页按钮
        for sel in ['.pagination', 'ul.pagination', '[class*=page]', 'button:has-text("下一页")',
                    'text=下一页', 'text=2']:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    print(f'[+] 发现翻页候选: {sel}', flush=True)
            except Exception:
                pass
        try:
            nxt = page.locator('text=下一页').first
            if nxt.count() > 0 and nxt.is_visible():
                nxt.click(timeout=8000)
                print('[+] 点击下一页', flush=True)
                page.wait_for_timeout(6000)
        except Exception as e:
            print(f'[!] 翻页失败: {e}', flush=True)

        # 保存捕获
        with open(OUT / 'capture.jsonl', 'w', encoding='utf-8') as f:
            for method, url, status, body in captured:
                f.write(json.dumps({'method': method, 'url': url,
                                    'status': status, 'body': body},
                                   ensure_ascii=False) + '\n')
        print(f'[*] 捕获 {len(captured)} 条, 已存 {OUT / "capture.jsonl"}', flush=True)
        page.screenshot(path=str(OUT / 'page.png'), full_page=False)
        html = page.content()
        (OUT / 'page.html').write_text(html, encoding='utf-8')
        print('[*] screenshot + html saved', flush=True)
        browser.close()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
