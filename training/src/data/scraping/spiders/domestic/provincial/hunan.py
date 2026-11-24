"""
古玉鉴真 — 湖南博物院 (hunan) 爬虫

- 新版藏品数据库 (试运行) de.hnmuseum.com/collection/ (2026-11-19 探测,
  证据 scraped_data/_site_probe/hunan_db/), 纯 REST API 无需浏览器:
  - 分类: GET /zgww/collectionIndex/list → 玉石类 id=1002227492125147136
    (全库 62721 件, 玉石类 3877 件)
  - 列表: GET /zgww/collectionIndex/publishList?current=N&size=200
    &type={分类id}&threeType=否 → records (id/collection_name/
    collection_years/collection_size/collection_texture/thumb_path _small)
  - 详情: GET /zgww/collectionIndex/publishDetailsById?id={id} →
    resourcePublish 全字段 + imgUrl[] (file_browse: _big/_small/modify/.JPG
    多视图, _big 为大图)
- 图片组: 详情 imgUrl 按 _big > modify > .JPG > _small 排序, thumb 兜底
- item_id: hn_{id} (雪花 id, 无碰撞)
- 玉石类为馆方分类, 直接信任 (参照 capital_museum 玉器类目);
  玛瑙/玉髓 等可能散在「其他」类目, 后续可加 search 关键词轴补
- 规模: 3877 件 × (1 详情 + 1 图) + 20 列表 ≈ 7800 请求 ≈ 6 天配额,
  每日续跑 (checkpoint 断点续传)
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote

import requests

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

HUNAN_DB = 'https://de.hnmuseum.com'
LIST_API = HUNAN_DB + '/zgww/collectionIndex/publishList'
DETAIL_API = HUNAN_DB + '/zgww/collectionIndex/publishDetailsById'
RES_PREFIX = HUNAN_DB + '/bwg_resource/'
PAGE_SIZE = 200

JADE_TYPE_ID = '1002227492125147136'  # 玉石类 (2026-11-19 实测)

NIAN_RE = re.compile(r'[（(]?(?:西元|公元)[^）)]*[）)]?')

# 玉石类为馆方宽口径分类 (玉+石+玻璃混排, 2026-11-19 实测 50 件抽样
# 约 40% 非玉): 琉璃/料器/玻璃 及石印/石砚/石镜/石雕 显性非玉排除
# (参照 knmdb 青铜嵌石教训; 玛瑙/水晶/琥珀/绿松石 等项目枚举内材质保留)
NON_JADE_TITLE_RE = re.compile(
    r'琉璃|料璧|料珠|料簪|料钗|料剑|料发|料管|料环|料器|玻璃|瓷珠|'
    r'砚|端石|石印|石镜|石猪|石鼓|石方|铭文石|石睡|石雕|石刻|石俑|扁石')

# 图片变体优先级 (组内依次回退, 首张成功即停)
_IMG_RANK = [
    ('_big', 0), ('modify', 1), ('.JPG', 2), ('_small', 3),
]


def _img_key(url: str) -> int:
    for pat, rank in _IMG_RANK:
        if pat in url:
            return rank
    return 9


class HunanSpider(BaseJadeSpider):
    """湖南博物院玉器藏品爬虫 (新版藏品数据库 REST API)。"""

    def __init__(self, config=None):
        super().__init__(
            name='hunan',
            museum_name='Hunan Museum',
            museum_name_cn='湖南博物院',
            base_url=HUNAN_DB,
            config=config,
        )
        # 国内站强制直连: 忽略 shell 代理环境变量 (2026-11-23 教训:
        # HTTPS_PROXY 残留使国内站走 Clash, ProxyError 断批)
        self.session.trust_env = False
        self._records: Dict[str, Dict] = {}

    # ── 发现 ──

    def _list_page(self, page: int) -> Optional[List[Dict]]:
        try:
            resp = self.get(LIST_API, params={
                'current': page, 'size': PAGE_SIZE, 'search': '', 'year': '',
                'type': JADE_TYPE_ID, 'image': '', 'threeType': '否',
            })
            data = resp.json()
        except requests.RequestException:
            return None
        except ValueError:
            return None
        if not (data or {}).get('status'):
            return None
        return (data.get('data') or {}).get('records')

    def discover_items(self) -> List[Dict]:
        items: List[Dict] = []
        page = 1
        total_pages: Optional[int] = None
        prev_ids: set = set()
        while True:
            recs = self._list_page(page)
            if recs is None:
                print(f"[hunan] 第 {page} 页请求失败, 本轮收尾 (下轮补)")
                break
            if not recs:
                break
            ids = {r.get('id') for r in recs}
            if page > 1 and ids == prev_ids:  # 越界页重复内容防死循环
                break
            prev_ids = ids
            if page == 1:
                # 首页带 total (由 _list_page 丢掉, 这里再取一次不划算;
                # 空页 break + 重复检测已足够)
                pass
            for r in recs:
                rid = r.get('id') or ''
                if not rid:
                    continue
                item_id = f'hn_{rid}'
                self._records[item_id] = r
                items.append({
                    'item_id': item_id,
                    'title': r.get('collection_name') or '',
                    'era': r.get('collection_years') or '',
                    'detail_url': f'{DETAIL_API}?id={rid}',
                })
            if total_pages is None:
                print(f"[hunan] 玉石类: 首页 {len(recs)} 件")
            page += 1
        print(f"[hunan] 玉石类: 共发现 {len(items)} 件")
        return items

    # ── 详情 ──

    def _record_skip(self, item_id: str, reason: str, title: str, era: str):
        with open(self.output_dir / 'skip_log.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'item_id': item_id, 'reason': reason, 'title': title,
                'era': era, 'logged_at': datetime.now().isoformat(),
            }, ensure_ascii=False) + '\n')
            f.flush()

    def parse_detail(self, detail_url: str) -> Dict:
        rid = re.search(r'id=(\d+)', detail_url or '')
        item_id = f'hn_{rid.group(1)}' if rid else ''
        rec = self._records.get(item_id) or {}
        list_title = rec.get('collection_name') or ''

        try:
            resp = self.get(detail_url)
            data = resp.json()
        except requests.RequestException:
            return {'item_id': item_id, 'title': list_title, 'image_urls': [],
                    'skip_reason': '网络错误'}
        except ValueError:
            return {'item_id': item_id, 'title': list_title, 'image_urls': [],
                    'skip_reason': 'API error'}
        payload = (data or {}).get('data') or {}
        pub = payload.get('resourcePublish') or {}
        title = pub.get('collection_name') or list_title
        era_raw = NIAN_RE.sub('', pub.get('collection_years') or '').strip()
        dimensions = pub.get('collection_size') or ''

        # 琉璃/料器/石质显性非玉 → 终态拒收 (2026-11-19 实测混入 ~40%)
        if NON_JADE_TITLE_RE.search(title):
            self._record_skip(item_id, 'not jade (琉璃料器/石质)', title,
                              era_raw)
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'not jade'}

        # 图片: _big > modify > .JPG > _small; thumb 兜底
        cands: List[str] = []
        for im in payload.get('imgUrl') or []:
            u = (im or {}).get('file_browse') or ''
            if u and u not in cands:
                cands.append(u)
        cands.sort(key=_img_key)
        thumb = pub.get('thumb_path') or ''
        if thumb:
            thumb_url = (RES_PREFIX + thumb) if not thumb.startswith('http') \
                else thumb
            if thumb_url not in cands:
                cands.append(thumb_url)
        if not cands:
            self._record_skip(item_id, 'no image', title, era_raw)
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}

        era_result, era_approx = map_era_zh(era_raw), False
        if era_result:
            era_approx = is_approx_era_zh(era_raw)
        material_raw = ' '.join(x for x in
                                [pub.get('collection_texture') or '',
                                 title] if x)
        extra = {
            'title': title,
            'material_raw': material_raw,
            'dimensions_raw': dimensions,
            'page_url': detail_url,
            'accession_number': pub.get('collection_num') or '',
            'culture': '中国',
            'era_raw': era_raw,
            'license': '湖南博物院藏品数据库 (试运行) 图片, 未声明授权条款, 学术研究使用',
        }
        if era_result:
            extra['era_mapped_code'] = era_result[0]
            extra['era_mapped_name'] = era_result[1]
            if era_approx:
                extra['era_approx'] = True
        else:
            extra['era_mapped_code'] = None
            extra['era_mapped_name'] = None

        return {
            'item_id': item_id,
            'title': title,
            'era': era_raw,
            'description': '',
            'material': map_material_zh(material_raw),
            'dimensions': dimensions,
            'source': '湖南博物院',
            'image_groups': [cands],
            'extra_metadata': extra,
        }
