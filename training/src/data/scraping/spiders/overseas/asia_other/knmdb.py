"""
古玉鉴真 — 京都国立博物館 館蔵品データベース (KNMDB) 爬虫

- 全库浏览: /list.html?limit=50&pageNo=N (无关键词 = 全库 ~7500 件, 150 页)
  搜索亦可: list.html?sf={kw} (全文: 作品名/作者/材质均命中)
- 列表行 (<div class="item" id="{id}">) 含: 作者/台帳番号/国・地域/
  時代・世紀/分類 + 缩略图 /art_images/{p}/{img}_difile2-M.jpg
  → 列表级预筛 国・地域含"中国" (或为空), 省大量详情请求
- 详情: /{id}.html 静态页, 含 材質・技法/時代/世紀/西暦/法量/指定区分/
  作者名/作品名・文化財の名称/寄贈者 等完整字段
- 图片: 详情页内 /art_images/{p}/{img}_difile2-L.jpg 大图 (实测 700KB+)
- 过滤: 国・地域含中国 + 材質・技法 命中中文材质表
- 网络: 需走代理; 无 WAF 问题, 常规限速
"""

import re
import time
from typing import Dict, List

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

KNMDB_BASE = 'https://knmdb.kyohaku.go.jp'
LIST_TPL = KNMDB_BASE + '/list.html?limit=50&pageNo={page}'
DETAIL_TPL = KNMDB_BASE + '/{item_id}.html'
PAGE_SIZE = 50


def _strip_tags(s: str) -> str:
    return re.sub(r'<[^>]+>', '', s or '').replace('&nbsp;', ' ').strip()


class KnmdbSpider(BaseJadeSpider):
    """京都国立博物館館蔵品データベース爬虫 (静态列表+详情, 全库扫描)。"""

    def __init__(self, config=None):
        super().__init__(
            name='knmdb',
            museum_name='Kyoto National Museum',
            museum_name_cn='京都国立博物館',
            base_url=KNMDB_BASE,
            config=config,
        )

    # ── 发现 ──

    def discover_items(self) -> List[Dict]:
        items = []
        page = 1
        while True:
            url = LIST_TPL.format(page=page)
            try:
                html = self.get(url).text
            except Exception:
                # 代理瞬断: 重试一次该页, 仍失败则提前收尾 (下轮续跑)
                print(f"[knmdb] page={page} 网络错误, 8s 后重试该页")
                time.sleep(8)
                try:
                    html = self.get(url).text
                except Exception:
                    print(f"[knmdb] page={page} 再次失败, 本轮收尾 "
                          f"(已发现 {len(items)} 件)")
                    break
            rows = re.findall(
                r'<div class="item" id="(\d+)">(.*?)(?=<div class="item" id='
                r'|<div class="pager)', html, re.S)
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
                items.append({
                    'item_id': mid,
                    'detail_url': DETAIL_TPL.format(item_id=mid),
                    'list_meta': fields,
                })
            # 分页器最大页码 (pageNo 链接)
            last_pages = [int(x) for x in re.findall(r'pageNo=(\d+)', html)]
            if not last_pages or page >= max(last_pages):
                break
            page += 1
        return items

    # ── 详情解析 ──

    def parse_detail(self, detail_url: str) -> Dict:
        item_id = re.search(r'/(\d+)\.html', detail_url or '')
        item_id = item_id.group(1) if item_id else ''
        try:
            html = self.get(detail_url).text
        except Exception:
            return {'item_id': item_id, 'title': '', 'era': '',
                    'image_urls': [], 'skip_reason': '网络错误'}

        # 全字段 (dt/dd 结构)
        fields: Dict[str, str] = {}
        for k, v in re.findall(r'<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>',
                               html, re.S):
            key = _strip_tags(k)
            if key:
                fields[key] = _strip_tags(v)
        title = fields.get('作品名・文化財の名称', '')
        country = fields.get('国・地域', '')
        material = fields.get('材質・技法', '')
        era_raw = ' '.join(x for x in (fields.get('時代', ''),
                                       fields.get('世紀', ''),
                                       fields.get('西暦', ''), title) if x)

        # 过滤: 国・地域含中国 + 材质命中中文材质表
        if not map_material_zh(material) or ('中国' not in country and country):
            return {'item_id': item_id, 'title': title, 'era': '',
                    'image_urls': [], 'skip_reason': 'not Chinese jade'}

        # 大图 (同号 M/L/S 变体, 取 L; 连作含多图)
        img_urls = sorted(set(re.findall(
            r'["\'](/art_images/[^"\']+_difile2-L\.jpg)["\']', html)))
        if not img_urls:
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
