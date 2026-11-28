"""
古玉鉴真 — 甘肃省博物馆 (gansu) 爬虫

2026-11-27 侦察 (证据 scraped_data/_site_probe/domestic_20261126/gansu_pw/):
- 数字甘博 Vue SPA (sccp-cms 公共服务 API, 无鉴权):
  典藏根目录 catalogCode=00000000,1702864504053 全库 928 件
- 列表: GET /sccp/api/sccp-cms/public/news/page?catalogCode=..
  &page=0&size=50&title=&deptCode= → content[] 每件含 title/
  subTitle(时代)/shortTitle(等级)/author(类目)/titleImage/
  description(含尺寸)/source
- 类目树 findByPcode: 玉石器仅标 2 件 (馆方标注不全), 故全库
  扫描按题名玉系过滤 (玉|玛瑙|翡翠|水晶|琥珀|绿松石)
- 路由守卫坑: /collectionList 直接 URL 会被打回 /home, 须从导航
  菜单点入 (Playwright 侦察期); 但 API 直连无此限制
- 图 URL 三种形态: 新式 /sccp-file/{appid}/image/{date}/{id}.jpg
  (3004x2392); 老式 /sccp-file//upload/{ym}/{d}/{ts}.jpg (1600x1600);
  thumb_ 前缀缩略图 → 去前缀得原图 (1000x666); tn_dc 图 390x322
- 假阳性排除: 玉壶春/汉白玉/金耳坠/金带饰 (金器为主体)/炭精 (煤精)
- 国内站强制直连; robots.txt 未查 (API 站无声明)
- item_id: gs_{id} (无碰撞)
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

GD_BASE = 'https://www.gansumuseum.com'
LIST_API = GD_BASE + '/sccp/api/sccp-cms/public/news/page'
ROOT_CATALOG = '00000000,1702864504053'  # 典藏根目录
PAGE_SIZE = 50

JADE_TITLE_RE = re.compile(r'玉|玛瑙|翡翠|水晶|琥珀|绿松石|瑪瑙')
# 玉壶春=瓷, 汉白玉=大理石, 金耳坠/金带饰/金镶玉=金器为主体, 炭精=煤精
FAKE_TITLE_RE = re.compile(r'玉壶春|汉白玉|金耳坠|金带饰|金镶玉|炭精')

# 尺寸提取 (厘米/毫米/米/克)
DIM_RE = re.compile(
    r'(通高|通长|通宽|残高|残长|口径|底径|腹径|足径|圈足径|最大径|高|宽|长|厚|深|重)'
    r'\s*[,，]?\s*([0-9]+(?:\.[0-9]+)?)\s*(厘米|毫米|米|克|千克|公斤)')


class GansuSpider(BaseJadeSpider):
    """甘肃省博物馆玉器爬虫 (sccp-cms 公开 API, 列表即全字段)。"""

    def __init__(self, config=None):
        super().__init__(
            name='gansu',
            museum_name='Gansu Provincial Museum',
            museum_name_cn='甘肃省博物馆',
            base_url=GD_BASE,
            config=config,
        )
        # 国内站强制直连 (2026-11-23 教训: HTTPS_PROXY 残留致 ProxyError)
        self.session.trust_env = False
        self._records: Dict[str, Dict] = {}

    # ── 发现 ──

    def discover_items(self) -> List[Dict]:
        out: List[Dict] = []
        page = 0
        total_pages = None
        while True:
            try:
                resp = self.get(LIST_API, params={
                    'catalogCode': ROOT_CATALOG, 'page': page,
                    'size': PAGE_SIZE, 'title': '', 'deptCode': '',
                })
                d = resp.json()
            except (requests.RequestException, ValueError):
                print(f"[gansu] 第 {page} 页请求失败, 本轮收尾 (下轮补)")
                break
            data = d.get('data')
            if not data:
                print(f"[gansu] 第 {page} 页 data 为空, 本轮收尾 (下轮补)")
                break
            total_pages = data.get('totalPages')
            items = data.get('content') or []
            if not items:
                break
            for it in items:
                iid = it.get('id')
                title = (it.get('title') or '').strip()
                author = (it.get('author') or '').strip()
                if not iid or not title:
                    continue
                is_jade = bool(JADE_TITLE_RE.search(title)
                               and not FAKE_TITLE_RE.search(title))
                if not is_jade and '玉' in author and not FAKE_TITLE_RE.search(title):
                    is_jade = True
                if not is_jade:
                    continue
                item_id = f'gs_{iid}'
                if item_id in self._records:
                    continue
                self._records[item_id] = it
                out.append({
                    'item_id': item_id,
                    'title': title,
                    'era': (it.get('subTitle') or '').strip(),
                    'detail_url': f'gs://{iid}',
                })
            page += 1
            if total_pages is not None and page >= total_pages:
                break
            if page > 40:  # 硬上限防死循环 (928/50=19 页)
                print(f"[gansu] 翻页超 40 页 ({total_pages=}), 强制收尾")
                break
        print(f"[gansu] 典藏全库 {total_pages} 页遍历 {page} 页, 玉系命中 {len(out)} 件")
        return out

    # ── 详情 (列表即全字段, 无需请求) ──

    @staticmethod
    def _fix_img(u: str) -> Optional[str]:
        """三种图 URL 形态归一; thumb_ 前缀去之得原图。"""
        if not u:
            return None
        u = u.strip()
        if u.startswith('http'):
            return u
        if u.startswith('//'):
            return 'https:' + u
        if '/upload/' in u:
            base, name = u.rsplit('/', 1)
            if name.startswith('thumb_'):
                return f'{GD_BASE}/sccp-file/{base}/{name[6:]}'
            return f'{GD_BASE}/sccp-file/{u}'
        # 新式 {appid}/image/... 或 /bwg/... 相对路径
        return f'{GD_BASE}/sccp-file/{u.lstrip("/")}'

    def parse_detail(self, detail_url: str) -> Dict:
        m = re.search(r'gs://(\S+)', detail_url or '')
        item_id = f'gs_{m.group(1)}' if m else ''
        rec = self._records.get(item_id) or {}
        title = (rec.get('title') or '').strip()
        era_text = (rec.get('subTitle') or '').strip()
        level = (rec.get('shortTitle') or '').strip()
        author = (rec.get('author') or '').strip()
        desc = (rec.get('description') or '').strip()
        source = (rec.get('source') or '').strip()

        img = self._fix_img(rec.get('titleImage') or '')
        if not img:
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}

        dims = []
        for dm in DIM_RE.finditer(desc):
            dims.append(f"{dm.group(1)}{dm.group(2)}{dm.group(3)}")
        dimensions = json.dumps({'尺寸': ' '.join(dims)}, ensure_ascii=False) if dims else ''

        # 时代: subTitle 或题名前缀 (明•/汉•)
        era_raw = era_text
        if not era_raw:
            pm = re.match(r'^([一-鿿]{1,4})[•·]', title)
            if pm:
                era_raw = pm.group(1)
        era_result = map_era_zh(era_raw)
        material_raw = ' '.join(x for x in (title, author, desc[:200]) if x)
        extra = {
            'title': title,
            'material_raw': material_raw,
            'dimensions_raw': dimensions,
            'page_url': f'{GD_BASE}/collectionDetail?nav=3-0&id={rec.get("id")}',
            'accession_number': '',
            'culture': '中国',
            'era_raw': era_raw[:150],
            'category': author,
            'level': level,
            'license': '甘肃省博物馆官网图片 (未声明授权条款, 学术研究使用)',
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
            'description': desc,
            'material': map_material_zh(material_raw),
            'dimensions': dimensions,
            'source': '甘肃省博物馆',
            'image_urls': [img],
            'extra_metadata': extra,
        }
