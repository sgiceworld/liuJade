"""
古玉鉴真 — 上海博物馆 (shanghai) 爬虫

2026-11-28 侦察:
- 主站旧路径 /frontend/pg/m/... 404, 真身在 /mu/ 前缀:
  数字文物库 https://www.shanghaimuseum.net/mu/frontend/pg/lib1/index
- 列表: POST /mu/frontend/pg/collection/search-antique
  {"params":{"langCode":"CATALOG_CHINESE","libTypes":["LIB_TYPE_0013"],
  "libAges":[],"searchText":null,"libTypeSort":null,"libAgeSort":null,
  "libOnlyShowPic":"ONLY_SHOW_PIC"},"page":"1","limit":20}
  → 玉器 (LIB_TYPE_0013) 带图 1270 件 (全类 3660 件, 全库珍贵文物 14.7万)
- 列表即全字段: name/intraAgeCode(清)/intraAntiqueTypeCode(玉器)/
  code(藏品号)/picPath/picPath2/catalog(时代 HTML), 无需详情请求
- 图: /mu/upload/{ym}/{uuid}.jpg 640x640
- 无鉴权, 直连可用
- 国内站强制直连
- item_id: sh_{id} (无碰撞)
"""

import html as html_mod
import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

SH_BASE = 'https://www.shanghaimuseum.net'
SEARCH_API = SH_BASE + '/mu/frontend/pg/collection/search-antique'
JADE_TYPE = 'LIB_TYPE_0013'
PAGE_SIZE = 20

JADE_TITLE_RE = re.compile(r'玉|翡翠|玛瑙|水晶|琥珀|绿松石|瑪瑙')
FAKE_TITLE_RE = re.compile(r'玉壶春|汉白玉|玻璃|琉璃')
# 类别=玉器 但实为石/珊瑚/珍珠 (寿山石/青田石雕/珊瑚雕/石玦石琮等)
NON_JADE_NAME_RE = re.compile(r'寿山|青田|珊瑚|珍珠|石')


class ShanghaiSpider(BaseJadeSpider):
    """上海博物馆玉器爬虫 (search-antique API, 列表即全字段)。"""

    def __init__(self, config=None):
        super().__init__(
            name='shanghai',
            museum_name='Shanghai Museum',
            museum_name_cn='上海博物馆',
            base_url=SH_BASE,
            config=config,
        )
        # 国内站强制直连 (2026-11-23 教训: HTTPS_PROXY 残留致 ProxyError)
        self.session.trust_env = False
        self._records: Dict[str, Dict] = {}

    # ── 发现 ──

    def post(self, url: str, **kwargs) -> requests.Response:
        """POST 版 base.get(): 限速/robots/重试/计数同款
        (2026-11-27 sanxingdui 同款, 列表 API 只认 POST)。"""
        host = urlparse(url).netloc
        if host not in self.robots_cache and not self.check_robots(host):
            raise RuntimeError(f"{self.name}: robots.txt 禁止访问 {host}")
        self._respect_rate_limit(host)
        kwargs.setdefault('timeout', self.config.REQUEST_TIMEOUT)
        for attempt in (1, 2):
            try:
                response = self.session.post(url, **kwargs)
                self.request_count += 1
                key = f"{host}|{datetime.now().strftime('%Y-%m-%d')}"
                self.request_counts[key] = self.request_counts.get(key, 0) + 1
                response.raise_for_status()
                return response
            except (requests.ConnectionError,
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ReadTimeout) as e:
                if attempt == 2:
                    raise
                print(f"    ⚠ 连接错误重试 ({host}): {type(e).__name__}")
                self._respect_rate_limit(host)

    def discover_items(self) -> List[Dict]:
        out: List[Dict] = []
        page = 1
        total = None
        while True:
            try:
                resp = self.post(SEARCH_API, json={
                    'params': {'langCode': 'CATALOG_CHINESE',
                               'libTypes': [JADE_TYPE], 'libAges': [],
                               'searchText': None, 'libTypeSort': None,
                               'libAgeSort': None,
                               'libOnlyShowPic': 'ONLY_SHOW_PIC'},
                    'page': str(page), 'limit': PAGE_SIZE,
                })
                d = resp.json()
            except (requests.RequestException, ValueError):
                print(f"[shanghai] 第 {page} 页请求失败, 本轮收尾 (下轮补)")
                break
            if d.get('code') != 0:
                print(f"[shanghai] 第 {page} 页 code={d.get('code')}, 本轮收尾")
                break
            total = d.get('count')
            items = d.get('data') or []
            if not items:
                break
            for it in items:
                iid = it.get('id')
                name = (it.get('name') or '').strip()
                if not iid or not name:
                    continue
                # 名称玉系关键词 (滤假阳性); 否则类别=玉器 且无石/珊瑚等
                is_jade = bool(JADE_TITLE_RE.search(name)
                               and not FAKE_TITLE_RE.search(name))
                if not is_jade and not NON_JADE_NAME_RE.search(name):
                    is_jade = True
                if not is_jade:
                    continue
                item_id = f'sh_{iid}'
                if item_id in self._records:
                    continue
                self._records[item_id] = it
                out.append({
                    'item_id': item_id,
                    'title': name,
                    'era': (it.get('intraAgeCode') or '').strip(),
                    'detail_url': f'sh://{iid}',
                })
            page += 1
            if total is not None and page * PAGE_SIZE >= total + PAGE_SIZE:
                break
            if page > 120:  # 硬上限防死循环 (1270/20=64 页)
                print(f"[shanghai] 翻页超 120 页 ({total=}), 强制收尾")
                break
        print(f"[shanghai] 玉器带图 {total} 件遍历 {page - 1} 页, 命中 {len(out)} 件")
        return out

    # ── 详情 (列表即全字段, 无需请求) ──

    def parse_detail(self, detail_url: str) -> Dict:
        m = re.search(r'sh://(\d+)', detail_url or '')
        item_id = f'sh_{m.group(1)}' if m else ''
        rec = self._records.get(item_id) or {}
        title = (rec.get('name') or '').strip()
        era_text = (rec.get('intraAgeCode') or '').strip()
        type_text = (rec.get('intraAntiqueTypeCode') or '').strip()
        code = (rec.get('code') or '').strip()
        catalog = re.sub(r'<[^>]+>', ' ', rec.get('catalog') or '')
        catalog = re.sub(r'\s+', ' ', catalog).strip()
        desc = (rec.get('description') or '').strip()

        cands = []
        for k in ('picPath', 'picPath2'):
            u = rec.get(k)
            if u:
                full = urljoin(SH_BASE + '/mu/', u)
                if full not in cands:
                    cands.append(full)
        if not cands:
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}

        era_raw = ' '.join(x for x in (era_text, catalog) if x)
        era_result = map_era_zh(era_raw)
        material_raw = ' '.join(x for x in (title, type_text, desc[:200]) if x)
        extra = {
            'title': title,
            'material_raw': material_raw,
            'dimensions_raw': '',
            'page_url': f'{SH_BASE}/mu/frontend/pg/lib1/antique-detail?id={rec.get("id")}',
            'accession_number': code,
            'culture': '中国',
            'era_raw': era_raw[:150],
            'category': type_text,
            'license': '上海博物馆官网图片 (未声明授权条款, 学术研究使用)',
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
            'dimensions': '',
            'source': '上海博物馆',
            'image_groups': [cands],
            'extra_metadata': extra,
        }
