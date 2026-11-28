"""
古玉鉴真 — 辽宁省博物馆 (liaoning) 爬虫

2026-11-26 从 Vue SPA 的 webpack chunk 反查 + 实测挖出数字文物课堂
API (证据 scraped_data/_site_probe/domestic_20261126/liaoning_pw/):
- 全库 31653 件 (page.allRow), 分类 dict: category 25 类
  (3=玉器, 7=石器...), yearType 52 档
- 列表: GET /singleMuseum/szwwkt/list?year=&category=&name=
  &currentPage=1&size=200 (size=200 实测可用; 玉器 category=3
  allRow=1572, 图片覆盖 200/200)
- 字段: collectId/collectName/collectYear (清(1616~1911) 格式)/
  collectType/collectLevel/collectTexture/detailSize/
  pictureIds/imgUrl (getImg?fileId=..&type=S → 2272×1704 原图)
- 补充轴: name=玛瑙 (232 件, 部分被归 生活用品类, 分类轴漏收)
- 详情: collection/getCollectionById?id=collectId (baseCollectInfo
  含描述; 本爬虫首批不取描述, 省 1572+ 请求保日配额)
- 馆藏精品页另有静态 /test/collect.json (15 件, 含红山玉猪龙,
  与玉器轴去重后已覆盖)
- 国内站强制直连
- item_id: liaoning_{collectId} (无碰撞)
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

LIAO_BASE = 'https://www.lnmuseum.com.cn/singleMuseum'
LIST_API = LIAO_BASE + '/szwwkt/list'
JADE_CATEGORY = '3'  # 玉器 (szwwkt/dict category code)

# 附加关键词轴 (分类轴漏收的玉系材质, 按名称补收)
EXTRA_AXES = ['玛瑙', '翡翠', '水晶', '琥珀', '绿松石']

# 尺寸提取
DIM_RE = re.compile(
    r'(通高|通长|通宽|口径|底径|腹径|高|宽|长|厚|深|重)'
    r'\s*([0-9]+(?:\.[0-9]+)?)\s*(厘米|CM|毫米|米|克|千克|公斤)', re.I)


class LiaoningSpider(BaseJadeSpider):
    """辽宁省博物馆玉器爬虫 (szwwkt 数字文物课堂 API)。"""

    def __init__(self, config=None):
        super().__init__(
            name='liaoning',
            museum_name='Liaoning Provincial Museum',
            museum_name_cn='辽宁省博物馆',
            base_url='https://www.lnmuseum.com.cn',
            config=config,
        )
        # 国内站强制直连 (2026-11-23 教训: HTTPS_PROXY 残留致 ProxyError)
        self.session.trust_env = False
        self._records: Dict[str, Dict] = {}

    # ── 发现 ──

    def _list_axis(self, params: Dict, axis: str) -> List[Dict]:
        out: List[Dict] = []
        page = 1
        total = None
        axis_seen = 0  # 本轴累计件数 (跨轴 records 全局去重, 不能用作分页终止)
        while True:
            try:
                resp = self.get(LIST_API, params={
                    **params, 'currentPage': page, 'size': 200,
                })
                d = resp.json()
            except (requests.RequestException, ValueError):
                print(f"[liaoning] {axis} 第 {page} 页请求失败, 本轮收尾 (下轮补)")
                break
            page_info = d.get('page') or {}
            total = page_info.get('allRow')
            items = d.get('result') or []
            if not items:
                break
            axis_seen += len(items)
            for it in items:
                cid = it.get('collectId') or ''
                if not cid:
                    continue
                item_id = f'liaoning_{cid}'
                if item_id in self._records:
                    continue
                self._records[item_id] = it
                out.append({
                    'item_id': item_id,
                    'title': (it.get('collectName') or '').strip(),
                    'era': (it.get('collectYear') or '').strip(),
                    'detail_url': f'liaoning://{cid}',
                })
            page += 1
            if total is not None and axis_seen >= total:
                break
            if page > 60:  # 硬上限防死循环 (2026-11-18 henan 教训)
                print(f"[liaoning] {axis} 翻页超 60 页, 强制收尾")
                break
        return out

    def discover_items(self) -> List[Dict]:
        out = self._list_axis({'year': '', 'category': JADE_CATEGORY, 'name': ''},
                              '玉器分类')
        for kw in EXTRA_AXES:
            out += self._list_axis({'year': '', 'category': '', 'name': kw},
                                   f'name={kw}')
        print(f"[liaoning] 发现 {len(out)} 件 (玉器轴 + {len(EXTRA_AXES)} 关键词轴去重)")
        return out

    # ── 详情 (列表即全字段; 描述留待后续补收) ──

    def _record_skip(self, item_id: str, reason: str, title: str, era: str):
        with open(self.output_dir / 'skip_log.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'item_id': item_id, 'reason': reason, 'title': title,
                'era': era, 'logged_at': datetime.now().isoformat(),
            }, ensure_ascii=False) + '\n')
            f.flush()

    def parse_detail(self, detail_url: str) -> Dict:
        m = re.search(r'liaoning://(\S+)', detail_url or '')
        item_id = f'liaoning_{m.group(1)}' if m else ''
        rec = self._records.get(item_id) or {}
        title = (rec.get('collectName') or '').strip()
        year = (rec.get('collectYear') or '').strip()
        texture = (rec.get('collectTexture') or '').strip()
        size_raw = (rec.get('detailSize') or '').strip()

        img = rec.get('imgUrl') or ''
        if not img and rec.get('pictureIds'):
            img = ('/singleMuseum/attach/getImg?fileId=' +
                   str(rec['pictureIds']).split(',')[0] + '&type=S')
        if img and img.startswith('/'):
            img = urljoin(LIAO_BASE + '/', img)
        if not img:
            self._record_skip(item_id, 'no image', title, year)
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}

        dims = [f"{m.group(1)}{m.group(2)}{m.group(3)}"
                for m in DIM_RE.finditer(size_raw)]
        dimensions = json.dumps({'尺寸': ' '.join(dims)}, ensure_ascii=False) if dims else ''

        era_raw = year
        era_result = map_era_zh(era_raw)
        material_raw = ' '.join(x for x in (title, texture) if x)
        extra = {
            'title': title,
            'material_raw': material_raw,
            'dimensions_raw': dimensions,
            'page_url': '',
            'accession_number': str(rec.get('collectId') or ''),
            'culture': '中国',
            'era_raw': era_raw[:150],
            'texture': texture,
            'level': rec.get('collectLevel') or '',
            'license': '辽宁省博物馆官网图片 (未声明授权条款, 学术研究使用)',
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
            'era': era_raw[:150],
            'description': '',
            'material': map_material_zh(material_raw),
            'dimensions': dimensions,
            'source': '辽宁省博物馆',
            'image_urls': [img],
            'extra_metadata': extra,
        }
