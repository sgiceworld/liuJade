#!/usr/bin/env python3
"""
古玉鉴真 — 四川博物院典藏页定向抓包 (2026-11-27)

打开 /Explore/Collection, 落盘渲染后 DOM (找玉器分类 tab 结构),
尝试点击 玉器/玉石 分类, 捕获 queryArchivesList 的 POST body 与响应。
证据: scraped_data/_site_probe/domestic_20261126/sichuan_pw/
"""
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r'd:/liuJade/scraped_data/_site_probe/domestic_20261126/sichuan_pw')
OUT.mkdir(parents=True, exist_ok=True)
STATIC_RE = re.compile(r'\.(js|css|png|jpg|jpeg|gif|svg|ico|woff2?|ttf|map|mp4|mp3|otf|webp)(\?|$)', re.I)
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/125 Safari/537.36 JadeResearchBot/1.0')

captured = []


def on_response(resp):
    url = resp.url
    if STATIC_RE.search(url) or any(x in url for x in ('cnzz', 'rumt', 'map.qq')):
        return
    if 'sw-cms-cloud' not in url and 'scmuseum.cn/japi' not in url:
        return
    ctype = resp.headers.get('content-type', '') or ''
    body = ''
    if 'json' in ctype:
        try:
            body = resp.text()[:3000]
        except Exception:
            pass
    post = ''
    try:
        post = resp.request.post_data or ''
    except Exception:
        pass
    rec = {'method': resp.request.method, 'url': url, 'status': resp.status,
           'ctype': ctype, 'post_data': post[:800], 'body': body}
    captured.append(rec)
    print(f'  [POST] {url[:100]}', flush=True)
    print(f'      POST: {post[:400]}', flush=True)


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    with sync_playwright() as p:
        # 国内站强制直连 (2026-11-27: 系统代理 Clash 残留; --no-proxy-server
        # 无效, 须用 --proxy-server=direct://)
        browser = p.chromium.launch(headless=True, args=['--proxy-server=direct://'])
        ctx = browser.new_context(user_agent=UA, viewport={'width': 1440, 'height': 900})
        page = ctx.new_page()
        page.on('response', on_response)
        try:
            page.goto('https://www.scmuseum.cn/Explore/Collection',
                      timeout=60000, wait_until='domcontentloaded')
        except Exception as e:
            print(f'[!] goto 失败: {e}', flush=True)
            browser.close()
            return
        page.wait_for_timeout(8000)

        # 落盘渲染后 DOM
        dom = page.content()
        (OUT / 'collection_page.html').write_text(dom, encoding='utf-8')
        print(f'[*] DOM 落盘 {len(dom)} 字节', flush=True)

        # 先点馆藏精品 tab (默认内容未加载)
        for t in ('馆藏精品', '藏品总目'):
            for sel in (f'text={t}', f'a:has-text("{t}")', f'li:has-text("{t}")',
                        f'div:has-text("{t}")', f'span:has-text("{t}")'):
                try:
                    loc = page.locator(sel)
                    if loc.count() == 0:
                        continue
                    best = None
                    for i in range(min(loc.count(), 25)):
                        el = loc.nth(i)
                        try:
                            if not el.is_visible():
                                continue
                            box = el.bounding_box()
                            if box and 5 < box['width'] < 1200 and 5 < box['height'] < 200:
                                best = el
                                break
                        except Exception:
                            continue
                    if best:
                        best.click(timeout=6000)
                        print(f'[+] clicked {sel} ({t})', flush=True)
                        break
                except Exception:
                    continue
        page.wait_for_timeout(8000)
        for _ in range(4):
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(1200)
        dom2 = page.content()
        (OUT / 'collection_tab1.html').write_text(dom2, encoding='utf-8')
        print(f'[*] tab 后 DOM 落盘 {len(dom2)} 字节', flush=True)

        # 藏品总目: 先展开材质下拉, 再点「宝玉石」
        try:
            ch = page.locator('.searchbox .choose').first
            if ch.count() and ch.is_visible():
                ch.click(timeout=6000)
                print('[+] 展开材质下拉', flush=True)
        except Exception:
            pass
        page.wait_for_timeout(2000)
        for sel in ('li:has-text("宝玉石")', 'text=宝玉石'):
            try:
                loc = page.locator(sel)
                for i in range(min(loc.count(), 5)):
                    el = loc.nth(i)
                    if el.is_visible():
                        el.click(timeout=6000)
                        print(f'[+] clicked {sel} ({i})', flush=True)
                        break
            except Exception:
                continue
        page.wait_for_timeout(2000)
        try:
            btn = page.locator('button.btn').first
            if btn.count() and btn.is_visible():
                btn.click(timeout=6000)
                print('[+] clicked 搜索', flush=True)
        except Exception:
            pass
        page.wait_for_timeout(8000)
        for _ in range(4):
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(1200)

        # 找玉器 tab: 打印含玉字的可点击元素
        for t in ('玉器', '玉石', '玉'):
            for sel in (f'text={t}', f'a:has-text("{t}")', f'li:has-text("{t}")',
                        f'div:has-text("{t}")', f'span:has-text("{t}")'):
                try:
                    loc = page.locator(sel)
                    n = loc.count()
                    if n:
                        print(f'[?] {sel} count={n}', flush=True)
                        for i in range(min(n, 8)):
                            el = loc.nth(i)
                            vis = el.is_visible() if el else False
                            txt = el.inner_text()[:40].replace('\n', ' ') if vis else ''
                            print(f'      {i}: visible={vis} text={txt!r}', flush=True)
                except Exception:
                    continue

        # 点击玉器分类
        clicked = False
        for t in ('玉器', '玉石'):
            for sel in (f'text={t}', f'a:has-text("{t}")', f'li:has-text("{t}")',
                        f'div:has-text("{t}")', f'span:has-text("{t}")'):
                try:
                    loc = page.locator(sel)
                    if loc.count() == 0:
                        continue
                    best = None
                    for i in range(min(loc.count(), 25)):
                        el = loc.nth(i)
                        try:
                            if not el.is_visible():
                                continue
                            box = el.bounding_box()
                            if box and 5 < box['width'] < 1200 and 5 < box['height'] < 200:
                                best = el
                                break
                        except Exception:
                            continue
                    if best:
                        best.click(timeout=6000)
                        print(f'[+] clicked {sel} ({t})', flush=True)
                        clicked = True
                        break
                except Exception:
                    continue
            if clicked:
                break
        page.wait_for_timeout(8000)
        if clicked:
            for _ in range(4):
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(1200)

        with open(OUT / 'archives_capture.jsonl', 'w', encoding='utf-8') as f:
            for c in captured:
                f.write(json.dumps(c, ensure_ascii=False) + '\n')
        print(f'[*] 捕获 queryArchivesList {len(captured)} 条', flush=True)
        browser.close()


if __name__ == '__main__':
    main()
