"""
古玉鉴真 — 重庆中国三峡博物馆 (chongqing) 爬虫

2026-11-26 侦察 (证据 scraped_data/_site_probe/domestic_20261126/):
- 静态站服务端分页 (2026-11-26 复核): 典藏栏目 4 个 —
  镇馆之宝 (20件)/三维藏品 (64件, 8页×8)/精品鉴赏 (空)/藏品公开 (空)
- 列表卡片: <a href="/web/article/{id}/web/content_{id}.html"
  target="_blank"><img ..._wh960x612.jpg><p class="img-name">品名</p>
  (target 属性在 href 与文本之间, 早期正则漏配的坑)
- 三维藏品详情页是 WebGL 360 查看器, 无文本元数据 →
  本爬虫仅收列表图+题名, 时代从题名首字提取 (明清/战国...)
- 玉系命中 4 件: 明青玉镂雕船形摆件/清青玉桃形笔洗/清凤首玉带钩/
  清青白玉圆雕葫芦摆件
- 国内站强制直连
- item_id: cq3gm_{article_id} (无碰撞)
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

CQ_BASE = 'https://www.3gmuseum.cn'
COLUMN = CQ_BASE + '/web/column/col5009285'  # 三维藏品

JADE_TITLE_RE = re.compile(r'玉|翡翠|玛瑙|瑪瑙')
FAKE_TITLE_RE = re.compile(r'玉壶春|琉璃|搪瓷|汉白玉')
ITEM_RE = re.compile(
    r'href="(https://www\.3gmuseum\.cn/web/article/(\d+)/web/content_\d+\.html)"'
    r'[^>]*>\s*<img[^>]+src="([^"]+)"[^>]*>\s*'
    r'<p class="img-name">([^<]+)</p>', re.S)


class ChongqingSpider(BaseJadeSpider):
    """重庆中国三峡博物馆玉器爬虫 (静态三维藏品列)。"""

    def __init__(self, config=None):
        super().__init__(
            name='chongqing',
            museum_name='Chongqing China Three Gorges Museum',
            museum_name_cn='重庆中国三峡博物馆',
            base_url=CQ_BASE,
            config=config,
        )
        # 国内站强制直连 (2026-11-23 教训: HTTPS_PROXY 残留致 ProxyError)
        self.session.trust_env = False
        self._records: Dict[str, Dict] = {}

    # ── 发现 ──

    def discover_items(self) -> List[Dict]:
        out: List[Dict] = []
        page = 1
        prev: set = set()
        while True:
            u = f'{COLUMN}.html' if page == 1 else f'{COLUMN}_{page}.html'
            try:
                resp = self.get(u)
                resp.encoding = resp.apparent_encoding or 'utf-8'
                text = resp.text
            except requests.RequestException:
                print(f"[chongqing] 第 {page} 页请求失败, 本轮收尾 (下轮补)")
                break
            items = ITEM_RE.findall(text)
            if not items:
                break
            titles = {t for _, _, _, t in items}
            if page > 1 and titles == prev:  # 越界重复内容防死循环
                break
            prev = titles
            for url, aid, img, title in items:
                if not JADE_TITLE_RE.search(title) or FAKE_TITLE_RE.search(title):
                    continue
                item_id = f'cq3gm_{aid}'
                if item_id in self._records:
                    continue
                rec = {'title': title, 'img': img, 'url': url}
                self._records[item_id] = rec
                out.append({
                    'item_id': item_id,
                    'title': title,
                    'era': '',
                    'detail_url': f'cq3gm://{aid}',
                })
            page += 1
            if page > 12:  # 硬上限防死循环
                break
        print(f"[chongqing] 三维藏品翻页 {page - 1} 页, 玉系命中 {len(out)} 件")
        return out

    # ── 详情 (列表即全字段; 详情页为 3D 查看器无文本) ──

    def parse_detail(self, detail_url: str) -> Dict:
        m = re.search(r'cq3gm://(\d+)', detail_url or '')
        item_id = f'cq3gm_{m.group(1)}' if m else ''
        rec = self._records.get(item_id) or {}
        title = (rec.get('title') or '').strip()
        img = (rec.get('img') or '').strip()
        if img.startswith('//'):
            img = 'https:' + img
        if not img:
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}

        era_raw = title
        era_result = map_era_zh(era_raw)
        extra = {
            'title': title,
            'material_raw': title,
            'dimensions_raw': '',
            'page_url': rec.get('url') or '',
            'accession_number': '',
            'culture': '中国',
            'era_raw': era_raw[:150],
            'license': '重庆中国三峡博物馆官网图片 (未声明授权条款, 学术研究使用)',
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
            'material': map_material_zh(title),
            'dimensions': '',
            'source': '重庆中国三峡博物馆',
            'image_urls': [img],
            'extra_metadata': extra,
        }
