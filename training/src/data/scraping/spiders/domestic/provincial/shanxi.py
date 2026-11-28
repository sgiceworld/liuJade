"""
古玉鉴真 — 山西博物院 (shanxi) 爬虫

2026-11-26 Playwright 抓包挖出典藏精选 JSON API (证据
scraped_data/_site_probe/domestic_20261126/shanxi_pw/):
- 列表: GET /sx/collection/collection_list?offset=0&count=50
  &dynasty=&material=&keyword=&categoryId=&quality=&hall=
  (FastAdmin 风格, data.total 全库 338 件; material2=玉 47 件)
- 材质码: material1铜 2玉 3石 4纸 5青铜 6陶 7瓷 8绫 9绫本
  10绢本 11鎏金 12银 13玻璃 14木 (展厅 hall9 玉韫华夏, 当前 0 件)
- 详情: /index.php/cms/a/{id}.html 静态页:
  x-tit 内 h26/h18=品名, p=时代; .child data-url=大图 (可多张,
  文件名带尺寸后缀 _1336_748_88_0.jpg); .cont p=尺寸+描述
- 时代码 dynasty1-24 → 中文名 (见 DYNASTY_MAP), 复用 map_era_zh
- 旧域名 shanximuseum.com 已死, 真身 www.shanximuseum.com.cn
- 国内站强制直连; robots.txt 404 (无声明)
- item_id: shanxi_{id} (无碰撞)
- 过滤: material2 全收; 其余材质按题名玉系预筛 (玉壶春|琉璃|搪瓷 排除)
"""

import html as html_mod
import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

SX_BASE = 'https://www.shanximuseum.com.cn'
LIST_API = SX_BASE + '/sx/collection/collection_list'
DETAIL_TPL = SX_BASE + '/index.php/cms/a/{id}.html'
PAGE_SIZE = 50

# 题名玉系预筛 (material2 之外的材质)
JADE_TITLE_RE = re.compile(r'玉|翡翠|玛瑙|瑪瑙')
# 汉白玉=大理石 (石质), 玉壶春=瓷器, 琉璃/搪瓷=玻璃/珐琅
FAKE_TITLE_RE = re.compile(r'玉壶春|琉璃|搪瓷|汉白玉')

# 时代码 → 中文名 (2026-11-26 页面下拉实测)
DYNASTY_MAP = {
    'dynasty1': '新石器时代', 'dynasty2': '夏', 'dynasty3': '商',
    'dynasty4': '西周', 'dynasty5': '东周', 'dynasty6': '春秋',
    'dynasty7': '战国', 'dynasty8': '汉', 'dynasty9': '北魏',
    'dynasty10': '东魏', 'dynasty11': '北齐', 'dynasty12': '隋代',
    'dynasty13': '唐', 'dynasty14': '五代', 'dynasty15': '北宋',
    'dynasty16': '辽', 'dynasty17': '金', 'dynasty18': '蒙元时代',
    'dynasty19': '金—元', 'dynasty20': '元', 'dynasty21': '元—明',
    'dynasty22': '明', 'dynasty23': '清', 'dynasty24': '现代',
}

# 尺寸提取 (厘米/毫米/米/克, 常见量词)
DIM_RE = re.compile(
    r'(通高|通长|通宽|残高|残长|口径|底径|腹径|足径|最大径|高|宽|长|厚|深|重)'
    r'\s*([0-9]+(?:\.[0-9]+)?)\s*(厘米|毫米|米|克|千克|公斤)')

# 列表页站 chrome 图 (非藏品)
CHROME_IMGS = {'/assets/img/shanxi/icon/'}


class ShanxiSpider(BaseJadeSpider):
    """山西博物院典藏精选玉器爬虫 (JSON 列表 + 静态详情)。"""

    def __init__(self, config=None):
        super().__init__(
            name='shanxi',
            museum_name='Shanxi Museum',
            museum_name_cn='山西博物院',
            base_url=SX_BASE,
            config=config,
        )
        # 国内站强制直连 (2026-11-23 教训: HTTPS_PROXY 残留致 ProxyError)
        self.session.trust_env = False
        self._records: Dict[str, Dict] = {}

    # ── 发现 ──

    def _list_page(self, offset: int) -> Optional[Dict]:
        try:
            resp = self.get(LIST_API, params={
                'offset': offset, 'count': PAGE_SIZE,
                'dynasty': '', 'material': '', 'keyword': '',
                'categoryId': '', 'quality': '', 'hall': '',
            })
            return resp.json()
        except (requests.RequestException, ValueError):
            return None

    def discover_items(self) -> List[Dict]:
        out: List[Dict] = []
        offset = 0
        total = None
        pages = 0
        while True:
            data = self._list_page(offset)
            if data is None or data.get('code') != 1:
                print(f"[shanxi] offset={offset} 请求失败, 本轮收尾 (下轮补)")
                break
            d = data['data']
            total = d.get('total')
            lst = d.get('list') or []
            if not lst:
                break
            for it in lst:
                title = (it.get('title') or '').strip()
                if not title:
                    continue
                mat = it.get('material') or ''
                # material2=玉 全收; 其余按题名玉系预筛 + 假阳性排除
                is_jade = mat == 'material2'
                if not is_jade and JADE_TITLE_RE.search(title):
                    is_jade = not FAKE_TITLE_RE.search(title)
                if not is_jade:
                    continue
                item_id = f"shanxi_{it['id']}"
                if item_id in self._records:
                    continue
                self._records[item_id] = it
                out.append({
                    'item_id': item_id,
                    'title': title,
                    'era': DYNASTY_MAP.get(it.get('dynasty') or '', ''),
                    'detail_url': DETAIL_TPL.format(id=it['id']),
                })
            offset += len(lst)
            pages += 1
            if total is not None and offset >= total:
                break
            if pages > 20:  # 硬上限防死循环 (2026-11-18 henan 教训)
                print(f"[shanxi] 翻页超 20 页 ({total=}), 强制收尾")
                break
        print(f"[shanxi] 列表 {offset}/{total} 件遍历, 玉系命中 {len(out)} 件")
        return out

    # ── 详情 ──

    def _record_skip(self, item_id: str, reason: str, title: str, era: str):
        with open(self.output_dir / 'skip_log.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'item_id': item_id, 'reason': reason, 'title': title,
                'era': era, 'logged_at': datetime.now().isoformat(),
            }, ensure_ascii=False) + '\n')
            f.flush()

    def parse_detail(self, detail_url: str) -> Dict:
        rid = re.search(r'/cms/a/(\d+)\.html', detail_url or '')
        item_id = f"shanxi_{rid.group(1)}" if rid else ''
        rec = self._records.get(item_id) or {}
        list_title = (rec.get('title') or '').strip()
        dynasty_name = DYNASTY_MAP.get(rec.get('dynasty') or '', '')

        try:
            resp = self.get(detail_url)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            text = resp.text
        except requests.RequestException:
            return {'item_id': item_id, 'title': list_title, 'image_urls': [],
                    'skip_reason': '网络错误'}

        # 品名 (x-tit 内 h26/h18)
        tm = re.search(r'<div class="h(?:26|18)">([^<]+)</div>', text)
        title = html_mod.unescape(tm.group(1)).strip() if tm else list_title

        # 时代 (品名下方的 p)
        em = re.search(r'<div class="p">([^<]*)</div>', text)
        era_text = html_mod.unescape(em.group(1)).strip() if em else ''

        # 大图 (data-url, 可多张) + zoomView 兜底
        cands: List[str] = []
        for u in re.findall(r'data-url="([^"]+)"', text):
            if any(c in u for c in CHROME_IMGS):
                continue
            full = urljoin(SX_BASE, u)
            if full not in cands:
                cands.append(full)
        for m in re.findall(r'class="zoomView"[^>]*>.*?href="([^"]+\.(?:jpg|jpeg|png))"',
                            text, re.S):
            full = urljoin(SX_BASE, m)
            if full not in cands:
                cands.append(full)
        # 列表字段兜底
        for key in ('big_image', 'image'):
            v = rec.get(key) or ''
            if v:
                full = urljoin(SX_BASE, v)
                if full not in cands:
                    cands.append(full)
        if not cands:
            self._record_skip(item_id, 'no image', title, era_text)
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}

        # 描述 (.cont 内 p)
        cm = re.search(r'<div class="cont">(.*?)</div>\s*</div>', text, re.S)
        desc = ''
        if cm:
            desc = html_mod.unescape(re.sub(r'<[^>]+>', ' ', cm.group(1)))
            desc = re.sub(r'\s+', ' ', desc).strip()

        # 尺寸 (从描述首句提取)
        dims = []
        for m in DIM_RE.finditer(desc):
            dims.append(f"{m.group(1)}{m.group(2)}{m.group(3)}")
        dimensions = json.dumps({'尺寸': ' '.join(dims)}, ensure_ascii=False) if dims else ''

        era_raw = ' '.join(x for x in (dynasty_name, era_text, desc[:120]) if x)
        era_result = map_era_zh(era_raw)
        material_raw = ' '.join(x for x in (title, desc[:200]) if x)
        extra = {
            'title': title,
            'material_raw': material_raw,
            'dimensions_raw': dimensions,
            'page_url': detail_url,
            'accession_number': '',
            'culture': '中国',
            'era_raw': era_raw[:150],
            'license': '山西博物院官网图片 (未声明授权条款, 学术研究使用)',
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
            'source': '山西博物院',
            'image_groups': [cands],
            'extra_metadata': extra,
        }
