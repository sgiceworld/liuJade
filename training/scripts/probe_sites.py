#!/usr/bin/env python3
"""
古玉鉴真 — 国内博物馆站点探测

判定「静态可爬」的标准 (requests-only 轮):
  详情页初始 HTML 直接包含 >=300px 的藏品图 URL (无需 JS 渲染)。

流程: 读 sites.json → 取站点首页/列表页 → 找详情链接 → 取首条详情页
      → 检查 <img> 是否为真实藏品图 → robots.txt 状态 → 输出报告

用法:
    cd training
    python scripts/probe_sites.py              # 探测全部国内站
    python scripts/probe_sites.py --site henan # 只探测一个
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / 'training' / 'src'))
sys.path.insert(0, str(REPO_ROOT / 'inference' / 'src'))

SITES_FILE = REPO_ROOT / 'training' / 'src' / 'data' / 'scraping' / 'sites.json'
UA = ("JadeResearchBot/1.0 (Academic Research; Ancient Jade Authentication "
      "Project)")

# 装饰性图片特征 (判定藏品图时排除)
DECOR_PATTERNS = re.compile(
    r'logo|icon|banner|nav|footer|qrcode|weixin|wechat|sprite|avatar|'
    r'loading|bg\.|background', re.I)
# 疑似藏品图路径特征
ARTIFACT_PATTERNS = re.compile(
    r'collection|upload|img|files|webfile|pic|picture|wenwu|cangpin|'
    r'goods|images', re.I)


def fetch(url: str, timeout: int = 20) -> requests.Response:
    resp = requests.get(url, headers={'User-Agent': UA}, timeout=timeout,
                        allow_redirects=True)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == 'iso-8859-1':
        resp.encoding = resp.apparent_encoding  # GBK/UTF-8 混杂站
    return resp


def check_robots(domain: str) -> str:
    """返回 robots.txt 状态描述。"""
    url = f"https://{domain}/robots.txt"
    try:
        r = requests.get(url, headers={'User-Agent': UA}, timeout=12)
        return f"{r.status_code}"
    except requests.RequestException:
        return 'unreachable'


def analyze_detail(html: str, detail_url: str) -> dict:
    """判定详情页是否静态可爬: 初始 HTML 含真实藏品图。

    对候选图逐个 HEAD 验证: Content-Length >= 30KB 视为真实藏品图
    (装饰图/图标通常 < 30KB)。前 3 张候选内找到即通过。
    """
    img_urls = []
    for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.I):
        src = m.group(1)
        if src.startswith('data:'):
            continue
        abs_url = urljoin(detail_url, src.lstrip('/'))
        if DECOR_PATTERNS.search(src):
            continue
        img_urls.append(abs_url)
    if not img_urls:
        # 无 src 的 img (懒加载 data-src 等) → JS 动态
        lazy = re.findall(r'data-(?:src|original)=["\']([^"\']+)["\']', html, re.I)
        if lazy:
            img_urls = [urljoin(detail_url, u) for u in lazy]

    verified = None
    for u in img_urls[:3]:
        try:
            r = requests.head(u, headers={'User-Agent': UA}, timeout=12,
                              allow_redirects=True)
            if r.status_code == 200 and int(r.headers.get('Content-Length', 0)) >= 30_000:
                verified = u
                break
        except requests.RequestException:
            continue

    return {
        'static_ok': verified is not None,
        'image_count': len(img_urls),
        'sample_image': verified,
        'verified_size': verified is not None,
    }


def probe_site(site: dict, verbose: bool = True) -> dict:
    """探测单个站点, 返回报告 dict。"""
    sid = site['id']
    result = {
        'id': sid, 'name_cn': site.get('name_cn', sid),
        'entry_url': site.get('entry_url'), 'ok': False, 'reason': '',
        'encoding': None, 'robots': None, 'detail_sample': None,
        'list_link_count': 0,
    }
    entry = site.get('entry_url')
    if not entry or entry.endswith('/'):
        entry = (entry or site.get('base_url', ''))
    try:
        r = fetch(entry)
        result['encoding'] = r.encoding
        domain = urlparse(r.url).netloc
        result['robots'] = check_robots(domain)
        html = r.text

        # 找详情链接候选 (含 id=/detail=/view= 等模式)
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.I)
        detail_hrefs = [h for h in hrefs if re.search(
            r'(id=|detail|view|content|collection|zp|cp|ww)', h, re.I)]
        result['list_link_count'] = len(detail_hrefs)
        if not detail_hrefs:
            result['reason'] = '列表页无详情链接 (可能 JS/XHR 动态加载)'
            return result

        detail_url = urljoin(entry, detail_hrefs[0])
        result['detail_sample'] = detail_url
        r2 = fetch(detail_url)
        analysis = analyze_detail(r2.text, detail_url)
        result.update(analysis)
        if analysis['static_ok']:
            result['ok'] = True
            result['reason'] = '详情页初始 HTML 含藏品图, 静态可爬'
        else:
            result['reason'] = '详情页无静态藏品图 (JS 渲染)'
    except requests.RequestException as e:
        result['reason'] = f'网络错误: {type(e).__name__}'
    except Exception as e:
        result['reason'] = f'解析错误: {e}'

    if verbose:
        mark = '✓' if result['ok'] else '✗'
        print(f"  {mark} {sid:12s} {result['name_cn']:10s} "
              f"[{result['reason']}] enc={result['encoding']} "
              f"robots={result['robots']}")
    return result


def main():
    ap = argparse.ArgumentParser(description='国内博物馆站点静态可爬性探测')
    ap.add_argument('--site', type=str, default=None, help='只探测指定站点 ID')
    ap.add_argument('--region', type=str, default='domestic',
                    help='探测区域 (domestic/overseas/all)')
    args = ap.parse_args()

    with open(SITES_FILE, encoding='utf-8') as f:
        sites = json.load(f)['sites']

    targets = sites
    if args.site:
        targets = [s for s in sites if s['id'] == args.site]
        if not targets:
            raise SystemExit(f"未知站点: {args.site}")
    elif args.region != 'all':
        targets = [s for s in sites if s['region'] == args.region]
    targets = [s for s in targets if s.get('type') != 'api']  # API 站无需探测

    print(f"探测 {len(targets)} 个站点 (每个 2 个请求 + 3-8s 延时)...\n")
    results = []
    for site in targets:
        results.append(probe_site(site))
        time.sleep(5)

    ok = [r for r in results if r['ok']]
    print(f"\n── 探测结果 ──")
    print(f"静态可爬: {len(ok)} / {len(results)}")
    for r in ok:
        print(f"  ✓ {r['id']}: {r['detail_sample']}")
        print(f"    样例图: {r['sample_image']}")

    out_file = REPO_ROOT / 'scraped_data' / '_probe_report.json'
    out_file.parent.mkdir(parents=True, exist_ok=True)
    # 单站探测时合并进既有报告, 不覆盖全量结果
    if out_file.exists():
        try:
            with open(out_file, encoding='utf-8') as f:
                existing = json.load(f)
            merged = {r['id']: r for r in existing}
            for r in results:
                merged[r['id']] = r
            results = list(merged.values())
        except (json.JSONDecodeError, KeyError):
            pass
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {out_file}")


if __name__ == '__main__':
    main()
