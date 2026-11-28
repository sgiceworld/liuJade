"""
古玉鉴真 — 良渚博物院 (liangzhu) 爬虫

2026-11-28 侦察:
- www.lzmuseum.cn (2026-09-28 曾 HTTPError, 今日恢复 200)
- 典藏精品 → 玉器 /YuQi/index.html + index_1..3 共 30 件
  (陶器/石器/其它 类目在线列表为空)
- 详情 /YuQi/{id}.html 静态页: .detail_t 题名, .detail_p 发布者,
  .detail_text 图+说明段落 (良渚文化双孔玉钺(1986年反山遗址发掘:
  M14:221)...)
- 图 /files/images/{中文文件名}.jpg 780x780 (须 URL 编码)
- 复制品 (现代仿) 不收
- 国内站强制直连
- item_id: liangzhu_{id} (无碰撞)
"""

import html as html_mod
import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote, urljoin

import requests

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

LZ_BASE = 'https://www.lzmuseum.cn'
LIST_TPL = LZ_BASE + '/YuQi/index{page}.html'

# 复制品/仿品 (现代) 不收
FAKE_TITLE_RE = re.compile(r'复制品|仿制|赝品')

# 尺寸提取
DIM_RE = re.compile(
    r'(通高|通长|通宽|残高|残长|口径|底径|腹径|足径|圈足径|最大径|高|宽|长|厚|深|重)'
    r'\s*[,，]?\s*([0-9]+(?:\.[0-9]+)?)\s*(厘米|毫米|米|克|千克|公斤)')


class LiangzhuSpider(BaseJadeSpider):
    """良渚博物院玉器爬虫 (静态典藏精品列)。"""

    def __init__(self, config=None):
        super().__init__(
            name='liangzhu',
            museum_name='Liangzhu Museum',
            museum_name_cn='良渚博物院',
            base_url=LZ_BASE,
            config=config,
        )
        # 国内站强制直连 (2026-11-23 教训: HTTPS_PROXY 残留致 ProxyError)
        self.session.trust_env = False
        self._records: Dict[str, Dict] = {}

    # ── 发现 ──

    def discover_items(self) -> List[Dict]:
        out: List[Dict] = []
        for p in ('', '_1', '_2', '_3', '_4'):
            url = LIST_TPL.format(page=p)
            try:
                resp = self.get(url)
                resp.encoding = resp.apparent_encoding or 'utf-8'
                text = resp.text
            except requests.RequestException:
                print(f"[liangzhu] index{p} 请求失败, 本轮收尾 (下轮补)")
                break
            found = set(re.findall(r'href="(/YuQi/\d+\.html)"', text))
            if not found:
                break
            for u in found:
                iid = re.search(r'(\d+)\.html', u).group(1)
                item_id = f'liangzhu_{iid}'
                if item_id in self._records:
                    continue
                self._records[item_id] = {'id': iid, 'url': urljoin(LZ_BASE, u)}
                out.append({
                    'item_id': item_id,
                    'title': '',
                    'era': '',
                    'detail_url': urljoin(LZ_BASE, u),
                })
            if len(found) < 10:  # 末页
                break
        print(f"[liangzhu] 玉器列 {len(out)} 件")
        return out

    # ── 详情 ──

    def parse_detail(self, detail_url: str) -> Dict:
        m = re.search(r'/YuQi/(\d+)\.html', detail_url or '')
        item_id = f'liangzhu_{m.group(1)}' if m else ''

        try:
            resp = self.get(detail_url)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            text = resp.text
        except requests.RequestException:
            return {'item_id': item_id, 'title': '', 'image_urls': [],
                    'skip_reason': '网络错误'}

        tm = re.search(r'<div class="detail_t">\s*([^<]+?)\s*<div', text)
        title = html_mod.unescape(tm.group(1)).strip() if tm else ''
        if not title:
            ttm = re.search(r'<title>([^<]+)</title>', text)
            title = ttm.group(1).replace('-良渚博物院', '').strip() if ttm else ''
        if FAKE_TITLE_RE.search(title):
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': '复制品'}

        # 正文 (图 + 说明)
        dm = re.search(r'<div class="detail_text">(.*?)</div>\s*<div class="close">',
                       text, re.S)
        body = dm.group(1) if dm else ''
        imgs = []
        for u in re.findall(r'<img[^>]+src="([^"]+)"', body):
            if '/images/' in u or '/files/' in u or '/upload/' in u:
                # 中文文件名 → URL 编码 (requests 不自动编码)
                full = urljoin(LZ_BASE, quote(u, safe='/:._-'))
                if full not in imgs:
                    imgs.append(full)
        if not imgs:
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}

        plain = re.sub(r'<[^>]+>', '\n', body)
        lines = [html_mod.unescape(x).strip() for x in plain.split('\n')
                 if x.strip()]
        # 图注 (含出土地) 与描述段
        caption = lines[0] if lines else ''
        desc = ' '.join(lines[1:])

        dims = []
        for dm_ in DIM_RE.finditer(desc):
            dims.append(f"{dm_.group(1)}{dm_.group(2)}{dm_.group(3)}")
        dimensions = json.dumps({'尺寸': ' '.join(dims)}, ensure_ascii=False) if dims else ''

        era_raw = ' '.join(x for x in (caption, title) if x)
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
            'license': '良渚博物院官网图片 (未声明授权条款, 学术研究使用)',
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
            'source': '良渚博物院',
            'image_groups': [imgs],
            'extra_metadata': extra,
        }
