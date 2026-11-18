#!/usr/bin/env python3
"""guobo 搜索变体探测: 页面内输入关键词/改分类触发 SearchAll, 全量留档。2026-11-18"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r'd:/liuJade/scraped_data/_site_probe/guobo_searchall')
OUT.mkdir(parents=True, exist_ok=True)
URL = 'https://www.chnmuseum.cn/qwjs/cpjs/'
captured = []


def on_response(resp):
    if 'SearchAll' in resp.url:
        try:
            body = resp.text()
        except Exception:
            body = ''
        captured.append({'url': resp.url, 'status': resp.status, 'body': body})
        print(f'[RESP] {resp.status} len={len(body)} {resp.url[:150]}', flush=True)


def run_case(page, case, word=None, set_js=None):
    """在页面内执行一个搜索用例 (改输入框/调用 searchStart)。"""
    if set_js:
        page.evaluate(set_js)
    if word is not None:
        page.evaluate(f'''() => {{ const el=document.querySelector("#word");
            el.value={json.dumps(word, ensure_ascii=False)}; }}''')
    print(f'[*] case: {case} word={word}', flush=True)
    page.evaluate('searchStart("PageNum=1")')
    page.wait_for_timeout(8000)
    # 读结果区文本
    txt = page.evaluate('''() => {
        const el = document.querySelector("#ulHtml");
        return el ? el.innerText.slice(0, 300) : '(no ulHtml)';
    }''')
    print(f'  results: {txt!r}', flush=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/125 Safari/537.36 JadeResearchBot/1.0')
        page = ctx.new_page()
        page.on('response', on_response)
        page.goto(URL, timeout=60000, wait_until='domcontentloaded')
        page.wait_for_timeout(6000)

        # 用例1: 关键词 玉 (无分类)
        run_case(page, 'kw=玉', word='玉')
        # 用例2: 关键词 玉器
        run_case(page, 'kw=玉器', word='玉器')
        # 用例3: 分类 质地=玉质(3) + 空关键词
        run_case(page, 'zhidi=3', set_js='''() => {
            $("#zhidi").val("3"); $("#pinlei").val(""); $("#niandai").val("");
        }''')
        # 用例4: 品类=玉器(406)
        run_case(page, 'pinlei=406', set_js='''() => {
            $("#pinlei").val("406"); $("#zhidi").val(""); $("#niandai").val("");
        }''')

        with open(OUT / 'cases.jsonl', 'w', encoding='utf-8') as f:
            for c in captured:
                f.write(json.dumps(c, ensure_ascii=False) + '\n')
        print(f'[*] 共捕获 {len(captured)} 个 SearchAll 响应', flush=True)
        browser.close()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
