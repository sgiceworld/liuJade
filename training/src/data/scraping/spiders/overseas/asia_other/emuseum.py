"""
古玉鉴真 — e国宝 (e-Museum) 爬虫: 静态列表 + IIIF manifest 直连

- 列表: /result?langId=zh&class={c}&pageCnt={n}&webView=0
  12 个分野 (1絵画 2書跡 3彫刻 4建築 5金工 6刀剣 7陶磁 8漆工 9染織
  10考古 11歴史資料 12法隆寺献納宝物), 每页 60 件, pageCnt 分页
- 藏品数据: 无需详情页, IIIF manifest 直接构造:
  /iiifapi/{content_base_id}000/manifest.json (id×1000, 实测成立)
- manifest 含: label(名称), metadata(指定区分/分野/指定名称/作者/制作/
  品質形状/法量/時代・世紀/所蔵者/各館作品番号), 多语言值 (ja/zh/en)
- 图片: IIIF Image API, canvas 资源即 URL, 14K 超高清 TIFF 源
  取 3000px 宽 JPEG: {service}/full/3000,/0/default.jpg
- 过滤: 制作/作者 含"中国" 且 品質形状/分野 命中中文材质表
- 网络: 需走代理 (国内直连不通); 常规限速即可, 无 WAF 问题
"""

import re
import time
from typing import Dict, List

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

EM_BASE = 'https://emuseum.nich.go.jp'
LIST_TPL = (EM_BASE + '/result?langId=zh&class={cls}&pageCnt={page}'
            '&webView=0')
MANIFEST_TPL = EM_BASE + '/iiifapi/{mid}000/manifest.json'
IIIF_SIZE = 'full/3000,/0/default.jpg'

# 分野编号 (首页实测, 2026-10-28): 1絵画 2書跡 3彫刻 4建築 5金工 6刀剣
# 7陶磁 8漆工 9染織 10考古 11歴史資料 12法隆寺献納宝物
# 玉器主要落 金工/考古, 排在前面让限额运行时先扫到; 全量仍由详情过滤
CLASSES = [5, 10, 8, 12, 7, 3, 6, 4, 9, 11, 1, 2]


def _pick_lang(values, prefer=('zh', 'ja', 'en')) -> str:
    """多语言 metadata 值 → 单文本 (按 zh > ja > en 优先级)。"""
    if isinstance(values, str):
        return values
    if isinstance(values, dict):
        return str(values.get('@value') or values.get('value') or '')
    for lang in prefer:
        for v in values or []:
            if isinstance(v, dict) and v.get('@language') == lang:
                return str(v.get('@value') or '')
    for v in values or []:
        if isinstance(v, dict) and v.get('@value'):
            return str(v['@value'])
    return ''


class EmuseumSpider(BaseJadeSpider):
    """e国宝 (国立文化財機構) 玉器爬虫: 列表 + IIIF manifest, 无详情页。"""

    def __init__(self, config=None):
        super().__init__(
            name='emuseum',
            museum_name='e-Museum (National Institutes for Cultural Heritage)',
            museum_name_cn='e国宝',
            base_url=EM_BASE,
            config=config,
        )

    # ── 发现 ──

    def discover_items(self) -> List[Dict]:
        items = []
        for cls in CLASSES:
            page = 1
            seen_page_ids = set()
            while True:
                try:
                    html = self.get(LIST_TPL.format(cls=cls, page=page)).text
                except Exception:
                    # 代理瞬断: 重试一次该页, 仍失败则提前收尾 (下轮续跑)
                    print(f"[emuseum] class={cls} page={page} 网络错误, "
                          f"8s 后重试该页")
                    time.sleep(8)
                    try:
                        html = self.get(
                            LIST_TPL.format(cls=cls, page=page)).text
                    except Exception:
                        print(f"[emuseum] class={cls} page={page} "
                              f"再次失败, 本轮收尾 (已发现 {len(items)} 件)")
                        break
                pairs = re.findall(
                    r'/detail\?[^"\']*content_base_id=(\d+)',
                    html)
                ids = []
                for mid in pairs:
                    if mid not in seen_page_ids:
                        seen_page_ids.add(mid)
                        ids.append(mid)
                print(f"[emuseum] class={cls} page={page}: {len(ids)} 件")
                for mid in ids:
                    items.append({
                        'item_id': mid,
                        'detail_url': MANIFEST_TPL.format(mid=mid),
                    })
                # 本页无新 id (或不足一页) → 该类翻完
                if len(ids) < 60:
                    break
                page += 1
        # 去重 (不同分野可能收录同一件)
        seen = set()
        uniq = []
        for it in items:
            if it['item_id'] not in seen:
                seen.add(it['item_id'])
                uniq.append(it)
        return uniq

    # ── 详情解析 (manifest 直连) ──

    def parse_detail(self, detail_url: str) -> Dict:
        mid = re.search(r'(\d+)000/manifest', detail_url or '')
        item_id = mid.group(1) if mid else ''
        try:
            data = self.get(detail_url).json()
        except Exception:
            return {'item_id': item_id, 'title': '', 'era': '',
                    'image_urls': [], 'skip_reason': '网络错误'}

        label = _pick_lang(data.get('label')) or ''
        title = re.sub(r'<[^>]+>', '', label).strip() or label
        meta = {}
        for entry in data.get('metadata') or []:
            key = _pick_lang(entry.get('label'))
            val = _pick_lang(entry.get('value'))
            if key:
                meta[key] = val

        place = ' '.join(x for x in (meta.get('制作', ''),
                                     meta.get('作者', '')) if x)
        material = ' '.join(x for x in (meta.get('品質形状', ''),
                                        meta.get('分野', '')) if x)
        era_raw = ' '.join(x for x in (meta.get('時代・世紀', ''), title)
                           if x)

        # 过滤: 制作/作者 含中国 + 材质命中中文材质表
        if '中国' not in place or not map_material_zh(material):
            return {'item_id': item_id, 'title': title, 'era': '',
                    'image_urls': [], 'skip_reason': 'not Chinese jade'}

        # IIIF canvas → 3000px JPEG (每组为不同照片, 全部下载)
        groups: List[List[str]] = []
        for canvas in self._canvases(data):
            cid = canvas.get('@id') or canvas.get('id') or ''
            m = re.match(r'(.*?/iiif/\?IIIF=/\S+?)(?:/full/.*)?$', cid)
            if m:
                groups.append([m.group(1) + '/' + IIIF_SIZE])
        if not groups:
            return {'item_id': item_id, 'title': title, 'era': '',
                    'image_urls': [], 'skip_reason': 'no image'}

        era_result = map_era_zh(era_raw)
        extra = {
            'title': title,
            'material_raw': material,
            'dimensions_raw': meta.get('法量', ''),
            'page_url': detail_url,
            'accession_number': meta.get('各館作品番号', ''),
            'culture': place,
            'era_raw': era_raw,
            'designation': meta.get('指定区分', ''),   # 国宝/重要文化財
            'owner': meta.get('所蔵者', ''),
            'license': 'e国宝 公開画像 (研究用途)',
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
            'dimensions': meta.get('法量', ''),
            'source': 'e国宝',
            'image_groups': groups,
            'extra_metadata': extra,
        }

    @staticmethod
    def _canvases(data: dict):
        """递归收集 manifest 的 canvas 列表。"""
        found = []

        def walk(o):
            if isinstance(o, dict):
                if o.get('@type') in ('sc:Canvas', 'Canvas'):
                    found.append(o)
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(data)
        return found
