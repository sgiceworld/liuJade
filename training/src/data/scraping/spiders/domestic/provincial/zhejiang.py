"""
古玉鉴真 — 浙江省博物馆 (zhejiang) 爬虫

2026-11-28 侦察:
- zjmuex.com = 浙江省博物馆公共服务综合平台 (Vue SPA),
  汇集省内各馆藏品
- API: GET /expo-admin/zhebo/cmsofficialwebsite/pageExhibit
  ?page=1&limit=200&exhibitName={kw}&deptId=&provinceId=&cityId=
  &exhibitAgeId= (无鉴权, limit=200 实测可用)
- 名称轴: 玉 477 / 玛瑙 8 / 翡翠 1 / 水晶 5 / 琥珀 3 / 绿松石 1
- 列表即全字段: exhibitName/ageDetail(清代/良渚文化/商周)/
  size/description/totalNumber(馆藏号)/orgName(馆名)/thumb
- 图: https://www.zjmuex.com/{thumb} 1920x1440 原图
  (appThumb 为 THUMB 目录 1000px 缩略图, 不用)
- 国内站强制直连
- item_id: zj_{exhibitId} (无碰撞)
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

ZJ_BASE = 'https://www.zjmuex.com'
LIST_API = ZJ_BASE + '/expo-admin/zhebo/cmsofficialwebsite/pageExhibit'
PAGE_SIZE = 200

AXES = ['玉', '玛瑙', '翡翠', '水晶', '琥珀', '绿松石']
FAKE_TITLE_RE = re.compile(r'玉壶春|汉白玉')
# generalType: CMS1711=玉器 (全收); 其余类型按题名强玉系判定
# (2026-11-28 实测: CMS1714=书画 46 件假阳性, CMS1710 混瓷器,
#  另有拓片/墓志/服装/匾/琴/尺牍等)
STRONG_MATERIAL_RE = re.compile(
    r'青玉|白玉|碧玉|黄玉|墨玉|糖玉|和田玉|独山玉|岫玉|鸡血玉|'
    r'玛瑙|翡翠|水晶|琥珀|绿松石')
JADE_ARTIFACT_RE = re.compile(
    r'玉(?:坐像|剑|耳|雕|龙|虎|人|璧|琮|璜|圭|钺|镯|簪|佩|印|带|玦|环|珠|坠|'
    r'管|梳|鱼|马|牛|羊|犬|猪|鸟|兽|蝉|握|塞|窍|衣|卮|觥|瓶|炉|尊|碗|盘|洗|'
    r'盒|山|如意|扳指|鋬指|刚卯)')
EXCLUDE_RE = re.compile(
    r'瓷|拓片|拓本|墓志|镜|琴|匾|尺牍|服装|服裝|花篮|花锄|私印|经册|集经|'
    r'西厢|贾宝玉|林黛玉|玉玲珑|玉兰|金玉满堂|玉璧底')

# 尺寸提取
DIM_RE = re.compile(
    r'(通高|通长|通宽|残高|残长|口径|底径|腹径|足径|圈足径|最大径|高|宽|长|厚|深|重)'
    r'\s*[,，]?\s*([0-9]+(?:\.[0-9]+)?)\s*(厘米|毫米|米|克|千克|公斤)')


class ZhejiangSpider(BaseJadeSpider):
    """浙江省博物馆玉器爬虫 (公共服务平台 pageExhibit API)。"""

    def __init__(self, config=None):
        super().__init__(
            name='zhejiang',
            museum_name='Zhejiang Provincial Museum',
            museum_name_cn='浙江省博物馆',
            base_url=ZJ_BASE,
            config=config,
        )
        # 国内站强制直连 (2026-11-23 教训: HTTPS_PROXY 残留致 ProxyError)
        self.session.trust_env = False
        # API 按 Accept 头返回 XML/JSON (默认 Accept 拿 XML), 必须显式要 JSON
        self.session.headers['Accept'] = 'application/json'
        self._records: Dict[str, Dict] = {}

    # ── 发现 ──

    def _list_axis(self, kw: str) -> List[Dict]:
        out: List[Dict] = []
        page = 1
        total = None
        while True:
            try:
                resp = self.get(LIST_API, params={
                    'page': page, 'limit': PAGE_SIZE, 'exhibitName': kw,
                    'deptId': '', 'provinceId': '', 'cityId': '',
                    'exhibitAgeId': '',
                })
                d = resp.json()
            except (requests.RequestException, ValueError):
                print(f"[zhejiang] {kw} 第 {page} 页请求失败, 本轮收尾 (下轮补)")
                break
            if d.get('code') != 0:
                print(f"[zhejiang] {kw} 第 {page} 页 code={d.get('code')}, 本轮收尾")
                break
            data = d.get('data') or {}
            total = data.get('total')
            items = data.get('list') or []
            if not items:
                break
            for it in items:
                eid = it.get('exhibitId')
                name = (it.get('exhibitName') or '').strip()
                if not eid or not name:
                    continue
                if FAKE_TITLE_RE.search(name) or EXCLUDE_RE.search(name):
                    continue
                gt = it.get('generalType') or ''
                if gt != 'CMS1711' and gt != '':
                    # 非玉器类目: 需强玉系题名佐证
                    if not (STRONG_MATERIAL_RE.search(name)
                            or JADE_ARTIFACT_RE.search(name)):
                        continue
                item_id = f'zj_{eid}'
                if item_id in self._records:
                    continue
                self._records[item_id] = it
                out.append({
                    'item_id': item_id,
                    'title': name,
                    'era': (it.get('ageDetail') or '').strip(),
                    'detail_url': f'zj://{eid}',
                })
            page += 1
            if total is not None and page * PAGE_SIZE >= total + PAGE_SIZE:
                break
            if page > 10:  # 硬上限防死循环
                print(f"[zhejiang] {kw} 翻页超 10 页 ({total=}), 强制收尾")
                break
        return out

    def discover_items(self) -> List[Dict]:
        out: List[Dict] = []
        for kw in AXES:
            before = len(self._records)
            items = self._list_axis(kw)
            print(f"[zhejiang] 轴 {kw}: 新命中 {len(self._records) - before} 件"
                  f" (去重后累计 {len(self._records)})")
            out.extend(items)
        return out

    # ── 详情 (列表即全字段, 无需请求) ──

    def parse_detail(self, detail_url: str) -> Dict:
        m = re.search(r'zj://(\S+)', detail_url or '')
        item_id = f'zj_{m.group(1)}' if m else ''
        rec = self._records.get(item_id) or {}
        title = (rec.get('exhibitName') or '').strip()
        era_text = (rec.get('ageDetail') or '').strip()
        desc = (rec.get('description') or '').strip()
        size_text = (rec.get('size') or '').strip()
        org = (rec.get('orgName') or '').strip()
        acc = (rec.get('totalNumber') or '').strip()

        thumb = (rec.get('thumb') or '').strip()
        img = urljoin(ZJ_BASE + '/', thumb) if thumb else ''
        if not img:
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}

        dims = []
        for dm in DIM_RE.finditer(size_text):
            dims.append(f"{dm.group(1)}{dm.group(2)}{dm.group(3)}")
        dimensions = json.dumps({'尺寸': ' '.join(dims)}, ensure_ascii=False) if dims else ''

        era_raw = era_text or title
        era_result = map_era_zh(era_raw)
        material_raw = ' '.join(x for x in (title, desc[:200]) if x)
        extra = {
            'title': title,
            'material_raw': material_raw,
            'dimensions_raw': dimensions,
            'page_url': '',
            'accession_number': acc,
            'culture': '中国',
            'era_raw': era_raw[:150],
            'museum_dept': org,
            'license': '浙江省博物馆公共服务平台图片 (未声明授权条款, 学术研究使用)',
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
            'source': org or '浙江省博物馆',
            'image_urls': [img],
            'extra_metadata': extra,
        }
