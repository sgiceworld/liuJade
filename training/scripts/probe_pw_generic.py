#!/usr/bin/env python3
"""
古玉鉴真 — 通用 Playwright XHR 抓包探测 (2026-11-26)

用法: python scripts/probe_pw_generic.py <site_id> <entry_url>
流程: 打开入口页 → 点藏品/文物/典藏 栏目 → 点玉器/玉石 分类 →
滚动触发懒加载 → 捕获全部非静态 XHR/fetch 响应落盘。
证据: scraped_data/_site_probe/domestic_20261126/<site_id>_pw/
(参照 capital_museum 挖接口手法; 探测期守 3-8s 延时)
"""
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r'd:/liuJade/scraped_data/_site_probe/domestic_20261126')
STATIC_RE = re.compile(r'\.(js|css|png|jpg|jpeg|gif|svg|ico|woff2?|ttf|map|mp4|mp3)(\?|$)', re.I)

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/125 Safari/537.36 JadeResearchBot/1.0')

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
        ctype = resp.headers.get('content-type', '') or ''
    except Exception:
        pass
    body = ''
    if 'json' in ctype or 'text' in ctype or status != 200:
        try:
            body = resp.text()
        except Exception:
            body = ''
    captured.append({'method': resp.request.method, 'url': url,
                     'status': status, 'ctype': ctype, 'body': body[:4000]})
    print(f'  [XHR] {resp.request.method} {status} {ctype[:24]:24s} {url[:130]}', flush=True)


def try_click(page, texts, timeout_ms=5000):
    """按文本找可点元素 (从最短到最长, 避免导航壳), 返回是否点击成功。"""
    for t in texts:
        for sel in (f'text={t}', f'a:has-text("{t}")', f'li:has-text("{t}")',
                    f'div:has-text("{t}")', f'span:has-text("{t}")'):
            try:
                loc = page.locator(sel)
                n = loc.count()
                if n == 0:
                    continue
                # 选最小的可见元素 (最像分类标签而不是整块容器)
                best = None
                for i in range(min(n, 25)):
                    el = loc.nth(i)
                    try:
                        if not el.is_visible():
                            continue
                        box = el.bounding_box()
                        if box and box['width'] < 1200 and box['height'] < 200:
                            best = el
                            break
                    except Exception:
                        continue
                if best:
                    best.click(timeout=timeout_ms)
                    print(f'  [+] clicked {sel} (text={t})', flush=True)
                    return True
            except Exception:
                continue
    return False


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    site = sys.argv[1]
    entry = sys.argv[2]
    work = OUT / f'{site}_pw'
    work.mkdir(parents=True, exist_ok=True)

    print(f'=== {site} {entry} ===', flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, viewport={'width': 1440, 'height': 900})
        page = ctx.new_page()
        page.on('response', on_response)

        try:
            page.goto(entry, timeout=60000, wait_until='domcontentloaded')
        except Exception as e:
            print(f'  [!] goto 失败: {e}', flush=True)
            browser.close()
            return
        page.wait_for_timeout(6000)

        # 1. 点藏品类栏目
        clicked = try_click(page, ['藏品', '文物', '典藏', '馆藏', '珍宝', '镇馆之宝', '精品'])
        page.wait_for_timeout(7000)

        # 2. 点玉器分类
        clicked2 = try_click(page, ['玉器', '玉石', '玉', '玉类'])
        page.wait_for_timeout(7000)

        # 3. 滚动触发懒加载
        for _ in range(6):
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(1200)

        # 4. 翻页
        try:
            nxt = page.locator('text=下一页').first
            if nxt.count() > 0 and nxt.is_visible():
                nxt.click(timeout=6000)
                print('  [+] 点击下一页', flush=True)
                page.wait_for_timeout(6000)
        except Exception:
            pass

        # 落盘
        with open(work / 'capture.jsonl', 'w', encoding='utf-8') as f:
            for c in captured:
                f.write(json.dumps(c, ensure_ascii=False) + '\n')
        (work / 'page.html').write_text(page.content(), encoding='utf-8')
        page.screenshot(path=str(work / 'page.png'), full_page=False)
        print(f'[*] {site}: 捕获 {len(captured)} 条 XHR, 已存 {work}', flush=True)
        browser.close()


if __name__ == '__main__':
    main()
