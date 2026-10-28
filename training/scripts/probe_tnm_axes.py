#!/usr/bin/env python3
"""TNM 搜索轴探测 (扩轴用, 每日 ≤30 请求, 8-15s 延时)。

探测:
1. 搜索表单页 → 枚举 bunrui 等下拉字段取值
2. search[keyword]=石・玉 / 软玉 / 翡翠 / 玛瑙 → 每轴第一页结果数
"""
import re
import sys
import time
import random

import requests

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

TNM = 'https://www.tnm.jp/modules/r_collection/index.php'
S = requests.Session()
S.headers.update({
    'User-Agent': 'JadeResearchBot/1.0 (Academic Research; Contact: jade-research@example.com)',
    'Accept-Language': 'zh-CN,en;q=0.9',
})

REQS = 0


def get(url, **kw):
    global REQS
    delay = random.uniform(8.0, 15.0)
    print(f"  (sleep {delay:.1f}s)")
    time.sleep(delay)
    kw.setdefault('timeout', 30)
    r = S.get(url, **kw)
    REQS += 1
    r.raise_for_status()
    return r


def main():
    # 1. 搜索表单字段
    r = get(f'{TNM}?controller=list&lang=zh_cn')
    html = r.text
    print(f'[form] len={len(html)}')
    for name, opts in re.findall(
            r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>(.*?)</select>',
            html, re.S):
        values = re.findall(r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>(.*?)</option>',
                            opts, re.S)
        print(f'  select {name!r}: {len(values)} options')
        for v, label in values[:15]:
            label = re.sub(r'<[^>]+>', '', label).strip()
            print(f'    value={v!r} label={label!r}')
    # 关键词输入框确认
    for m in re.findall(r'<input[^>]*name=["\']([^"\']+)["\'][^>]*>', html)[:20]:
        print(f'  input name={m!r}')

    # 2. 关键词轴探测
    for kw in ['石・玉', '软玉', '翡翠', '玛瑙']:
        url = f'{TNM}?controller=list&search[keyword]={kw}&lang=zh_cn&start=0'
        r = get(url)
        pairs = re.findall(
            r'controller=dtl&colid=([A-Z0-9]+)[^>]*>.*?'
            r'src=["\']([^"\']*r_collection/M_(\d+)\.jpg)["\']',
            r.text, re.S)
        starts = sorted({int(x) for x in re.findall(r'start=(\d+)', r.text)})
        total = re.search(r'(\d+)\s*件', r.text)
        print(f'[kw] {kw!r}: {len(pairs)} 件/页, start 链接={starts[:8]}, '
              f'"件数"标签={total.group(0) if total else None}')
        for colid, thumb, n in pairs[:5]:
            print(f'    {colid} {n}')

    print(f'\n[total requests] {REQS}')


if __name__ == '__main__':
    main()
