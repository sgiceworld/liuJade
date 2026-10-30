"""
古玉鉴真 — 京都国立博物館 館蔵品データベース (KNMDB) 爬虫

- 全库浏览: /list.html?limit=50&pageNo=N (无关键词 = 全库 ~7500 件, 150 页)
  搜索亦可: list.html?sf={kw} (全文: 作品名/作者/材质均命中)
- 列表行 (<div class="item" id="{id}">) 含: 作者/台帳番号/国・地域/
  時代・世紀/分類 + 缩略图 /art_images/{p}/{img}_difile2-M.jpg
  → 列表级预筛 国・地域含"中国" (或为空), 省大量详情请求
- 详情: /{id}.html 静态页, 含 材質・技法/時代/世紀/西暦/法量/指定区分/
  作者名/作品名・文化財の名称/寄贈者 等完整字段
- 图片: 详情页内 /art_images/{p}/{img}_difile{n}-L.jpg 大图
  (槽位号 n 不定, 1/2/3 都有, 取 -L 变体; 实测 700KB+)
- 过滤: 国・地域含中国 + 分类非绘画/书法等大类 + 材質・技法 命中中文材质表
- 发现缓存: _discovered.json 缓存全库扫描结果 (7 天内不重扫,
  每日省 150 页请求; 删除该文件可强制重扫)
- 网络: 需走代理; 代理对本站间歇性抖动, 详情页失败自动重试一轮
- 教训 (2026-10-30): 详情页主体是 <th>/<td> 表结构, 列表页才是 dt/dd;
  早期 parse_detail 只解析 dt/dd → 所有详情空字段 → 700+ 件全被误判
  not Chinese jade (0 下载)。已改为 th/td 优先 + dt/dd 兜底
"""

import json
import re
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import requests

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

KNMDB_BASE = 'https://knmdb.kyohaku.go.jp'
LIST_TPL = KNMDB_BASE + '/list.html?limit=50&pageNo={page}'
LIST_SEARCH_TPL = KNMDB_BASE + '/list.html?sf={kw}&limit=50&pageNo={page}'
DETAIL_TPL = KNMDB_BASE + '/{item_id}.html'
PAGE_SIZE = 50


def _strip_tags(s: str) -> str:
    return re.sub(r'<[^>]+>', '', s or '').replace('&nbsp;', ' ').strip()


# 大类排除: 这些分类不可能含中国玉器 (2026-10-30 实测: sf=玉 命中 197 件,
# 多为画题/画家名含"玉", 如 玉洞桃花図/浦上玉堂; 分类级预筛砍掉 ~81% 噪声)
NON_JADE_CAT_RE = re.compile(
    r'^(絵画\(A\)|書跡\(B\)|建築\(D\)|陶磁\(G\)|漆工\(H\)|染織\(I\)|歴史\(M\))')


def _category_ok(fields: Dict[str, str]) -> bool:
    """列表级分类预筛: 排除不可能含玉的大类 (空分类保留, 详情级兜底)。"""
    cat = fields.get('分類', '')
    return not cat or not NON_JADE_CAT_RE.match(cat)


class KnmdbSpider(BaseJadeSpider):
    """京都国立博物館館蔵品データベース爬虫 (静态列表+详情, 全库扫描)。"""

    def __init__(self, config=None, search_kw: str = None):
        super().__init__(
            name='knmdb',
            museum_name='Kyoto National Museum',
            museum_name_cn='京都国立博物館',
            base_url=KNMDB_BASE,
            config=config,
        )
        # 搜索模式: 全文关键词 (玉/翡翠/瑪瑙 等) 直达玉器条目,
        # 绕过全库顺序扫描 (2026-10-29 起: 前 700 件全为书画陶瓷)
        self.search_kw = search_kw

    # ── 发现 ──

    CACHE_DAYS = 7  # 发现结果缓存有效期 (天)

    def _scan_pages(self, url_fmt) -> List[Dict]:
        """翻页扫描列表页 + 列表级预筛 (国・地域含中国或空)。

        url_fmt: page -> URL 的函数。返回 (items, complete)。
        """
        items = []
        page = 1
        complete = True
        while True:
            url = url_fmt(page)
            try:
                html = self.get(url).text
            except requests.exceptions.RequestException:
                # 代理瞬断: 重试一次该页, 仍失败则提前收尾 (下轮续跑)
                print(f"[knmdb] page={page} 网络错误, 8s 后重试该页")
                time.sleep(8)
                try:
                    html = self.get(url).text
                except requests.exceptions.RequestException:
                    print(f"[knmdb] page={page} 再次失败, 本轮收尾 "
                          f"(已发现 {len(items)} 件)")
                    complete = False
                    break
            # 注意 \Z: 页尾最后一行无后续 item/pager 时也必须匹配 (勿漏末件)
            rows = re.findall(
                r'<div class="item" id="(\d+)">(.*?)(?=<div class="item" id='
                r'|<div class="pager|\Z)', html, re.S)
            print(f"[knmdb] page={page}: {len(rows)} 件")
            for mid, block in rows:
                # 列表级预筛: 国・地域含中国 (或空) 才进入详情
                fields = {}
                for k, v in re.findall(
                        r'<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>',
                        block, re.S):
                    key = _strip_tags(k)
                    if key:
                        fields[key] = _strip_tags(v)
                country = fields.get('国・地域', '')
                if country and '中国' not in country:
                    continue
                if not _category_ok(fields):
                    continue
                items.append({
                    'item_id': mid,
                    'detail_url': DETAIL_TPL.format(item_id=mid),
                    'list_meta': fields,
                })
            # 分页器最大页码 (pageNo 链接); 无分页器 (结果少) 即结束
            last_pages = [int(x) for x in re.findall(r'pageNo=(\d+)', html)]
            if not last_pages or page >= max(last_pages):
                break
            page += 1
        return items, complete

    def discover_items(self) -> List[Dict]:
        # 搜索模式: 关键词直达, 不读写全库缓存
        if self.search_kw:
            items, _ = self._scan_pages(
                lambda p: LIST_SEARCH_TPL.format(kw=self.search_kw, page=p))
            print(f"[knmdb] 搜索 '{self.search_kw}': 共 {len(items)} 件候选")
            return items
        # 全库扫描: 缓存命中则免重扫 150 页
        cache_file = self.output_dir / '_discovered.json'
        if cache_file.exists():
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if (datetime.now() - mtime).days < self.CACHE_DAYS:
                with open(cache_file, encoding='utf-8') as f:
                    cached = json.load(f)
                cached = [it for it in cached
                          if _category_ok(it.get('list_meta', {}))]
                print(f"[knmdb] 发现缓存命中: {len(cached)} 件 "
                      f"(删除 {cache_file} 可强制重扫)")
                return cached
        items, complete = self._scan_pages(
            lambda p: LIST_TPL.format(page=p))
        # 写发现缓存 (仅全量扫描完成时; 部分扫描不缓存, 续跑重扫)
        if complete:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(items, f, ensure_ascii=False)
        return items

    # ── 详情解析 ──

    def _record_skip(self, item_id: str, reason: str, title: str,
                     material: str, country: str, classification: str):
        """跳过诊断日志: 逐件留档被拒项的材质/国别 (负结果复核证据,
        2026-10-30 起; 见 skip_log.jsonl)。"""
        with open(self.output_dir / 'skip_log.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'item_id': item_id,
                'reason': reason,
                'title': title,
                'material': material,
                'country': country,
                'classification': classification,
                'logged_at': datetime.now().isoformat(),
            }, ensure_ascii=False) + '\n')
            f.flush()

    def parse_detail(self, detail_url: str) -> Dict:
        item_id = re.search(r'/(\d+)\.html', detail_url or '')
        item_id = item_id.group(1) if item_id else ''
        try:
            html = self.get(detail_url).text
        except requests.exceptions.RequestException:
            return {'item_id': item_id, 'title': '', 'era': '',
                    'image_urls': [], 'skip_reason': '网络错误'}
        # 注意: 配额 RuntimeError 等非网络异常不在此吞掉, 向上传播由
        # run() 的 except RuntimeError 正常收尾 (2026-10-29 教训)

        # 全字段: 详情页主体为 <th>/<td> 表结构 (列表页才是 dt/dd;
        # 只解析 dt/dd 会得空字段 → 全被误判 not Chinese jade)
        fields: Dict[str, str] = {}
        for k, v in re.findall(r'<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>',
                               html, re.S):
            key = _strip_tags(k)
            if key:
                fields[key] = _strip_tags(v)
        # 台帳番号 等在页面顶部的 dt/dd 小表里, 兜底补收
        for k, v in re.findall(r'<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>',
                               html, re.S):
            key = _strip_tags(k)
            if key and key not in fields:
                fields[key] = _strip_tags(v)
        title = fields.get('作品名・文化財の名称', '')
        country = fields.get('国・地域', '')
        material = fields.get('材質・技法', '')
        era_raw = ' '.join(x for x in (fields.get('時代', ''),
                                       fields.get('世紀', ''),
                                       fields.get('西暦', ''), title) if x)

        # 过滤: 国・地域含中国 + 材质命中中文材质表
        if not map_material_zh(material) or ('中国' not in country and country):
            self._record_skip(item_id, 'not Chinese jade', title, material,
                              country, fields.get('作品分類', ''))
            return {'item_id': item_id, 'title': title, 'era': '',
                    'image_urls': [], 'skip_reason': 'not Chinese jade'}

        # 大图 (difile 槽位号不定 1/2/3..., 取 -L 变体; 连作含多图)
        img_urls = sorted(set(re.findall(
            r'["\'](/art_images/[^"\']+_difile\d+-L\.jpg)["\']', html)))
        if not img_urls:
            self._record_skip(item_id, 'no image', title, material,
                              country, fields.get('作品分類', ''))
            return {'item_id': item_id, 'title': title, 'era': '',
                    'image_urls': [], 'skip_reason': 'no image'}
        groups = [[KNMDB_BASE + u] for u in img_urls]

        era_result = map_era_zh(era_raw)
        extra = {
            'title': title,
            'material_raw': material,
            'dimensions_raw': fields.get('法量', ''),
            'page_url': detail_url,
            'accession_number': fields.get('台帳番号', ''),
            'culture': country,
            'era_raw': era_raw,
            'classification': fields.get('作品分類', ''),
            'designation': fields.get('指定区分', ''),
            'artist': fields.get('作者名', ''),
            'donor': fields.get('寄贈者', ''),
            'license': 'KNMDB 館蔵品データベース公開画像 (研究用途)',
        }
        if era_result:
            extra['era_mapped_code'] = era_result[0]
            extra['era_mapped_name'] = era_result[1]
            if is_approx_era_zh(era_raw):
                extra['era_approx'] = True
        else:
            extra['era_mapped_code'] = None
            extra['era_mapped_name'] = None

        return {
            'item_id': item_id,
            'title': title,
            'era': era_raw,
            'description': '',
            'material': material,
            'dimensions': fields.get('法量', ''),
            'source': '京都国立博物館',
            'image_groups': groups,
            'extra_metadata': extra,
        }
