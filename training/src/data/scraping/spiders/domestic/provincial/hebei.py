"""
古玉鉴真 — 河北博物院 (hebei) 爬虫

2026-11-28 侦察:
- 主站 www.hebeimuseum.org.cn 藏品列表 (list-35) 的 tbody 靠前端填充
  但加载器不在任何静态资源 (表单 .sou 点击仅 window.open 带参导航,
  服务端不渲染行) → 主站列表实为死页面
- 真身在 apiwenwu.hebeimuseum.org.cn (文物数据库, 首页入口):
  检索 GET /news/lists.html?total=30&sd=0&fl=3&ord=0&title=&page=N
  (fl: 1金属 2陶瓷 3玉器 4漆器 5骨角 6书画 7石器 8近现代文物;
  sd 时代码; title 名称关键词)
- 玉器轴 fl=3 共 30 件 6/页 (含 2 件淡绿玻璃器需滤); 关键词轴
  玛瑙 4 / 翡翠 1 (与玉器轴重, 去重后无新增)
- 详情 /news/show/id/{id}.html 静态页: 【题名】/尺寸行/描述段,
  图 /upload/img/{md5}.jpg (3888x2592 原图)
- 国内站强制直连
- item_id: hb_{id} (无碰撞)
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

HB_BASE = 'https://apiwenwu.hebeimuseum.org.cn'
LIST_URL = HB_BASE + '/news/lists.html'
JADE_FL = '3'  # 玉器

# 玉器轴里的玻璃器 (馆方混分); 关键词轴的青铜器 (铜承弓器/铜辕饰 主体为铜)
FAKE_TITLE_RE = re.compile(r'玻璃|琉璃|铜|鎏金')

# 补充关键词轴 (其他分类里的玉系材质)
EXTRA_AXES = ['玛瑙', '翡翠']

# 尺寸提取 (厘米/毫米/米/克)
DIM_RE = re.compile(
    r'(通高|通长|通宽|残高|残长|口径|底径|腹径|足径|圈足径|最大径|高|宽|长|厚|深|重)'
    r'\s*([0-9]+(?:\.[0-9]+)?)\s*(厘米|毫米|米|克|千克|公斤)')


class HebeiSpider(BaseJadeSpider):
    """河北博物院玉器爬虫 (apiwenwu 文物数据库静态站)。"""

    def __init__(self, config=None):
        super().__init__(
            name='hebei',
            museum_name='Hebei Museum',
            museum_name_cn='河北博物院',
            base_url=HB_BASE,
            config=config,
        )
        # 国内站强制直连 (2026-11-23 教训: HTTPS_PROXY 残留致 ProxyError)
        self.session.trust_env = False
        self._records: Dict[str, Dict] = {}

    # ── 发现 ──

    def _list_axis(self, params: Dict, axis: str) -> List[Dict]:
        out: List[Dict] = []
        page = 1
        while True:
            try:
                resp = self.get(LIST_URL, params={**params, 'page': page})
                resp.encoding = resp.apparent_encoding or 'utf-8'
                text = resp.text
            except requests.RequestException:
                print(f"[hebei] {axis} 第 {page} 页请求失败, 本轮收尾 (下轮补)")
                break
            items = re.findall(
                r'<a[^>]+href="/news/show/id/(\d+)\.html"[^>]*>([^<]{0,50})</a>',
                text)
            if not items:
                break
            for iid, title in items:
                title = html_mod.unescape(title).strip()
                if not iid or not title:
                    continue
                if FAKE_TITLE_RE.search(title):
                    continue
                item_id = f'hb_{iid}'
                if item_id in self._records:
                    continue
                self._records[item_id] = {'id': iid, 'title': title}
                out.append({
                    'item_id': item_id,
                    'title': title,
                    'era': '',
                    'detail_url': f'{HB_BASE}/news/show/id/{iid}.html',
                })
            page += 1
            if page > 10:  # 硬上限防死循环 (30/6=5 页)
                print(f"[hebei] {axis} 翻页超 10 页, 强制收尾")
                break
        return out

    def discover_items(self) -> List[Dict]:
        out = self._list_axis(
            {'total': 30, 'sd': 0, 'fl': JADE_FL, 'ord': 0, 'title': ''},
            '玉器轴')
        for kw in EXTRA_AXES:
            items = self._list_axis(
                {'total': 0, 'sd': 0, 'fl': '', 'ord': 0, 'title': kw},
                f'title={kw}')
            print(f"[hebei] 关键词轴 {kw}: 新命中 {len(items)} 件")
            out.extend(items)
        print(f"[hebei] 玉器轴 30 件遍历, 共命中 {len(out)} 件")
        return out

    # ── 详情 ──

    def parse_detail(self, detail_url: str) -> Dict:
        m = re.search(r'/news/show/id/(\d+)\.html', detail_url or '')
        item_id = f'hb_{m.group(1)}' if m else ''
        rec = self._records.get(item_id) or {}
        list_title = (rec.get('title') or '').strip()

        try:
            resp = self.get(detail_url)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            text = resp.text
        except requests.RequestException:
            return {'item_id': item_id, 'title': list_title, 'image_urls': [],
                    'skip_reason': '网络错误'}

        # 题名
        tm = re.search(r'【([^】]+)】', text)
        title = html_mod.unescape(tm.group(1)).strip() if tm else list_title

        # 图片 (upload 图, 可能有 1+ 张)
        cands: List[str] = []
        for u in re.findall(r'<img[^>]+src="(/upload/[^"]+)"', text):
            full = urljoin(HB_BASE, u)
            if full not in cands:
                cands.append(full)
        if not cands:
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}

        # 正文: 去掉标签后, 第一段为尺寸, 其余为描述
        body = re.sub(r'<script.*?</script>', '', text, flags=re.S)
        seg = body
        i = seg.find('【')
        j = seg.find('友情链接')
        main = seg[i:j if j > i else i + 3000] if i >= 0 else ''
        main = re.sub(r'<[^>]+>', '\n', main)
        lines = [html_mod.unescape(x).strip()
                 for x in main.split('\n') if x.strip()]
        # 跳过题名行和导航行
        lines = [x for x in lines if not x.startswith(('【', '首页', 'Toggle'))]
        desc = ''
        dims = []
        for ln in lines:
            if DIM_RE.search(ln) and len(ln) < 120:
                for dm in DIM_RE.finditer(ln):
                    dims.append(f"{dm.group(1)}{dm.group(2)}{dm.group(3)}")
            else:
                desc += ln + ' '
        desc = desc.strip()
        dimensions = json.dumps({'尺寸': ' '.join(dims)}, ensure_ascii=False) if dims else ''

        era_raw = title
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
            'license': '河北博物院文物数据库图片 (未声明授权条款, 学术研究使用)',
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
            'source': '河北博物院',
            'image_groups': [cands],
            'extra_metadata': extra,
        }
