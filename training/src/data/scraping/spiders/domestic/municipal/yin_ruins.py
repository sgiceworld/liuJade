"""
古玉鉴真 — 殷墟博物馆 (yin_ruins) 爬虫

2026-11-26 抓包挖出馆方 gwebapi (证据
scraped_data/_site_probe/domestic_20261126/yin_ruins_pw/):
- 旧域 ayyx.com → 新域 www.yinxubwg.cn, API 在 guc.yinxubwg.cn
- 配置: GET /gwebapi/exhibit/config?p=w → cate_info
  (1青铜器 2陶器 3甲骨器 4玉石器) + year_info 22 档
- 列表: GET /gwebapi/exhibit/list?p=w&cate_ids=4&page=1&limit=100
  (全库仅 35 件, 玉石器 3 件: 玉戚/玉熊/玉凤, 全商代)
- 列表即含全部字段 (exhibit_name/year_name/place/intro 尺寸/
  list_img/line_img), 无需详情请求
- 国内站强制直连
- item_id: yinxu_{exhibit_id} (无碰撞)
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional

import requests

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

API_BASE = 'https://guc.yinxubwg.cn/gwebapi'
JADE_CATE_ID = '4'  # 玉石器

# 尺寸提取
DIM_RE = re.compile(
    r'(通高|通长|通宽|口径|底径|腹径|高|宽|长|厚|深|重)'
    r'\s*([0-9]+(?:\.[0-9]+)?)\s*(厘米|CM|毫米|米|克|千克|公斤)', re.I)


class YinRuinsSpider(BaseJadeSpider):
    """殷墟博物馆玉石器爬虫 (gwebapi 列表即全字段)。"""

    def __init__(self, config=None):
        super().__init__(
            name='yin_ruins',
            museum_name='Yin Xu Museum',
            museum_name_cn='殷墟博物馆',
            base_url='https://www.yinxubwg.cn',
            config=config,
        )
        # 国内站强制直连 (2026-11-23 教训: HTTPS_PROXY 残留致 ProxyError)
        self.session.trust_env = False
        self._records: Dict[str, Dict] = {}

    # ── 发现 ──

    def discover_items(self) -> List[Dict]:
        out: List[Dict] = []
        try:
            resp = self.get(f'{API_BASE}/exhibit/list', params={
                'p': 'w', 'exhibition_ids': '', 'year_ids': '',
                'cate_ids': JADE_CATE_ID, 'is_three': 0,
                'exhibit_name': '', 'page': 1, 'limit': 100,
            })
            data = resp.json()['data']
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"[yin_ruins] 列表请求失败: {e}, 本轮收尾 (下轮补)")
            return out
        for it in data.get('list') or []:
            eid = it.get('exhibit_id')
            name = (it.get('exhibit_name') or '').strip()
            if not eid or not name:
                continue
            item_id = f'yinxu_{eid}'
            self._records[item_id] = it
            out.append({
                'item_id': item_id,
                'title': name,
                'era': it.get('year_name') or '',
                # 列表即全字段; 合成 URL 携带 id 供 parse_detail 定位
                'detail_url': f'yinxu://{eid}',
                'image_urls': [it.get('line_img'), it.get('list_img')],
            })
        print(f"[yin_ruins] 玉石器 (cate_ids=4) 命中 {len(out)} 件")
        return out

    # ── 详情 (列表即全字段, 无需请求) ──

    def parse_detail(self, detail_url: str) -> Dict:
        m = re.search(r'yinxu://(\d+)', detail_url or '')
        item_id = f'yinxu_{m.group(1)}' if m else ''
        rec = self._records.get(item_id) or {}
        title = (rec.get('exhibit_name') or '').strip()
        era_name = (rec.get('year_name') or '').strip()
        place = (rec.get('place') or '').strip()
        intro = (rec.get('intro') or '').strip()

        dims = []
        for m in DIM_RE.finditer(intro):
            dims.append(f"{m.group(1)}{m.group(2)}{m.group(3)}")
        dimensions = json.dumps({'尺寸': ' '.join(dims)}, ensure_ascii=False) if dims else ''

        era_raw = ' '.join(x for x in (era_name, intro[:120]) if x)
        era_result = map_era_zh(era_raw)
        material_raw = ' '.join(x for x in (title, intro[:200]) if x)
        extra = {
            'title': title,
            'material_raw': material_raw,
            'dimensions_raw': dimensions,
            'page_url': '',
            'accession_number': '',
            'culture': '中国',
            'era_raw': era_raw[:150],
            'exhibition': rec.get('exhibition_name') or '',
            'unearthed_place': place,
            'license': '殷墟博物馆官网图片 (未声明授权条款, 学术研究使用)',
        }
        if era_result:
            extra['era_mapped_code'] = era_result[0]
            extra['era_mapped_name'] = era_result[1]
            if is_approx_era_zh(era_raw):
                extra['era_approx'] = True
        else:
            extra['era_mapped_code'] = None
            extra['era_mapped_name'] = None

        desc = ' '.join(x for x in (place, intro) if x)
        imgs = [u for u in (rec.get('line_img'), rec.get('list_img')) if u]
        return {
            'item_id': item_id,
            'title': title,
            'era': era_raw[:150],
            'description': desc,
            'material': map_material_zh(material_raw),
            'dimensions': dimensions,
            'source': '殷墟博物馆',
            'image_urls': imgs,
            'extra_metadata': extra,
        }
