"""
古玉鉴真 — 三星堆博物馆 (sanxingdui) 爬虫

2026-11-27 JS 反查破解签名 (证据
scraped_data/_site_probe/domestic_20261126/sanxingdui_pw/):
- API: POST https://www.sxd.cn/san_official/v1/exhibit/search
  {"pn":1,"rn":20,"language":0} → 全库 1100 件, rn 服务端上限 20
- 签名头 (index-eb63dfa3.js 反查): ts=epoch秒, nonce=16 位随机
  (字母表 ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678),
  sign=MD5(app+ts+secret+nonce) hex, app=sangw,
  secret=lTqu4m3YZljxBFO9 (clientApp/clientSecret 明文在 JS)
- 列表即全字段: album(COS 原图 3430x1930)/category/description/
  dynasty(中国历史学年代,商(...))/exhibit_num/level/size/
  unearthed_desc, 无需详情请求
- 过滤: 名称含 玉/玛瑙/翡翠/水晶/琥珀/绿松石 且非玉壶春/汉白玉;
  或类别=玉石器、宝石 且名称不含 石/象牙/骨/贝/金/铜/陶/瓷/铁/木
  (馆方把石盒/石璧等石器也标玉石器, 需剔除)
- robots.txt 200 但返回 SPA HTML (无规则) → 视为允许
- 国内站强制直连
- item_id: sxd_{exhibit_id} (无碰撞)
"""

import hashlib
import json
import random
import re
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

API = 'https://www.sxd.cn/san_official/v1/exhibit/search'
PAGE_SIZE = 20  # 服务端上限 (rn=100 实测截断为 20)

APP = 'sangw'
SECRET = 'lTqu4m3YZljxBFO9'
NONCE_ALPH = 'ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678'

JADE_TITLE_RE = re.compile(r'玉|玛瑙|翡翠|水晶|琥珀|绿松石|瑪瑙')
FAKE_TITLE_RE = re.compile(r'玉壶春|汉白玉')
# 类别=玉石器、宝石 但实为石/牙/骨/金/铜/陶/瓷 类
NON_JADE_NAME_RE = re.compile(r'石|象牙|骨|贝|金|铜|陶|瓷|铁|木')

# 尺寸提取 (厘米/毫米/米/克, 常见量词; 馆方用逗号分隔)
DIM_RE = re.compile(
    r'(通高|通长|通宽|残高|残长|口径|底径|腹径|足径|圈足径|最大径|高|宽|长|厚|深|重)'
    r'\s*[,，]?\s*([0-9]+(?:\.[0-9]+)?)\s*(厘米|毫米|米|克|千克|公斤)')


class SanxingduiSpider(BaseJadeSpider):
    """三星堆博物馆玉石器爬虫 (签名 API, 列表即全字段)。"""

    def __init__(self, config=None):
        super().__init__(
            name='sanxingdui',
            museum_name='Sanxingdui Museum',
            museum_name_cn='三星堆博物馆',
            base_url='https://www.sxd.cn',
            config=config,
        )
        # 国内站强制直连 (2026-11-23 教训: HTTPS_PROXY 残留致 ProxyError)
        self.session.trust_env = False
        self._records: Dict[str, Dict] = {}

    # ── 签名 ──

    def _sign_headers(self) -> Dict[str, str]:
        ts = str(int(time.time()))
        nonce = ''.join(random.choices(NONCE_ALPH, k=16))
        sign = hashlib.md5(f'{APP}{ts}{SECRET}{nonce}'.encode()).hexdigest()
        return {'ts': ts, 'nonce': nonce, 'sign': sign, 'app': APP}

    def _sign(self):
        self.session.headers.update(self._sign_headers())

    def get(self, url: str, **kwargs) -> requests.Response:
        """每次请求前注入签名头 (API 校验 ts 时效)。"""
        self._sign()
        return super().get(url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        """POST 版 base.get(): 限速/robots/重试/计数同款。
        (2026-11-27 教训: 本 API 只认 POST, GET 带 body 会被忽略
        pn 参数, 永远返回第一页 → 翻页死循环)"""
        from urllib.parse import urlparse
        host = urlparse(url).netloc
        if host not in self.robots_cache and not self.check_robots(host):
            raise RuntimeError(f"{self.name}: robots.txt 禁止访问 {host}")
        self._respect_rate_limit(host)
        self._sign()
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

    # ── 发现 ──

    def discover_items(self) -> List[Dict]:
        out: List[Dict] = []
        page = 1
        total = None
        while True:
            try:
                resp = self.post(API, json={'pn': page, 'rn': PAGE_SIZE,
                                            'language': 0})
                d = resp.json()
            except (requests.RequestException, ValueError):
                print(f"[sanxingdui] 第 {page} 页请求失败, 本轮收尾 (下轮补)")
                break
            if d.get('code') != 0:
                print(f"[sanxingdui] 第 {page} 页 code={d.get('code')} "
                      f"msg={d.get('msg')}, 本轮收尾")
                break
            data = d.get('data') or {}
            total = data.get('total')
            items = data.get('list') or []
            if not items:
                break
            for it in items:
                eid = it.get('exhibit_id')
                name = (it.get('name') or '').strip()
                cat = (it.get('category') or '').strip()
                if not eid or not name:
                    continue
                # 玉系判定: 名称玉系关键词 (滤假阳性) 或类别玉石器 (滤石/牙/金等)
                is_jade = bool(JADE_TITLE_RE.search(name)
                               and not FAKE_TITLE_RE.search(name))
                if not is_jade and '玉' in cat and not NON_JADE_NAME_RE.search(name):
                    is_jade = True
                if not is_jade:
                    continue
                item_id = f'sxd_{eid}'
                if item_id in self._records:
                    continue
                self._records[item_id] = it
                out.append({
                    'item_id': item_id,
                    'title': name,
                    'era': (it.get('dynasty') or '').replace('中国历史学年代,', ''),
                    'detail_url': f'sxd://{eid}',
                })
            page += 1
            if page > 80:  # 硬上限防死循环 (1100/20=55 页)
                print(f"[sanxingdui] 翻页超 80 页 ({total=}), 强制收尾")
                break
        print(f"[sanxingdui] 全库 {total} 件遍历 {page - 1} 页, 玉系命中 {len(out)} 件")
        return out

    # ── 详情 (列表即全字段, 无需请求) ──

    def parse_detail(self, detail_url: str) -> Dict:
        m = re.search(r'sxd://(\d+)', detail_url or '')
        item_id = f'sxd_{m.group(1)}' if m else ''
        rec = self._records.get(item_id) or {}
        title = (rec.get('name') or '').strip()
        era_text = (rec.get('dynasty') or '').replace('中国历史学年代,', '')
        desc = (rec.get('description') or '').strip()
        size_text = (rec.get('size') or '').strip()
        unearthed = (rec.get('unearthed_desc') or '').strip()
        cat = (rec.get('category') or '').strip()

        dims = []
        for dm in DIM_RE.finditer(size_text):
            dims.append(f"{dm.group(1)}{dm.group(2)}{dm.group(3)}")
        dimensions = json.dumps({'尺寸': ' '.join(dims)}, ensure_ascii=False) if dims else ''

        era_raw = era_text
        era_result = map_era_zh(era_raw)
        material_raw = ' '.join(x for x in (title, cat, desc[:200]) if x)
        extra = {
            'title': title,
            'material_raw': material_raw,
            'dimensions_raw': dimensions,
            'page_url': f'https://www.sxd.cn/relics/detail?id={rec.get("exhibit_id")}',
            'accession_number': rec.get('exhibit_num') or '',
            'culture': '中国',
            'era_raw': era_raw[:150],
            'category': cat,
            'level': rec.get('level') or '',
            'unearthed_place': unearthed,
            'license': '三星堆博物馆官网图片 (未声明授权条款, 学术研究使用)',
        }
        if era_result:
            extra['era_mapped_code'] = era_result[0]
            extra['era_mapped_name'] = era_result[1]
            if is_approx_era_zh(era_raw):
                extra['era_approx'] = True
        else:
            extra['era_mapped_code'] = None
            extra['era_mapped_name'] = None

        albums = [u for u in (rec.get('album') or []) if u]
        return {
            'item_id': item_id,
            'title': title,
            'era': era_raw[:150],
            'description': desc,
            'material': map_material_zh(material_raw),
            'dimensions': dimensions,
            'source': '三星堆博物馆',
            'image_groups': [albums] if albums else [],
            'extra_metadata': extra,
        }
