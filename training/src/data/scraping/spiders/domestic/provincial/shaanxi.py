"""
古玉鉴真 — 陕西历史博物馆 (shaanxi) 爬虫

- 静态站 + 服务端分页 (2026-11-24 探测, 证据
  scraped_data/_site_probe/shaanxi_coll/):
  - 列表: GET /searchs/collections.html?pagesize=12&tpl_file=collection
    &p=N&zhenguan=0 (须带 Referer collection.html + X-Requested-With,
    否则空响应); pagesize=999 被截断 (上限 999), 翻页才达全量
    (~670 页 ≈ 8000 件, p=800 空)
  - 条目: <div class="item"><a href="/collections/detail/{id}.html">
    <div class="pic"><img src=...png></div><div class="h">品名</div></a>
  - 详情: <title>品名_陕西历史博物馆_关键词</title>,
    <meta name="description"> = 正文 (时代在文中),
    主图 = 详情页 /Uploads/Picture/*.jpg 去掉站 chrome
    (logo s6185032db4faf.png / QR s63eae4ff6f316+s63ec8c8fc4e56) 后余图
- 玉器成簇分布 (p=500 一页 4 件春秋玉器), 题名玉系预筛省详情请求;
  假阳性 (玉壶春瓶/琉璃渣斗/搪瓷盘) 详情级 NON_JADE 过滤
- item_id: sxhm_{id} (无碰撞)
- 编码: UTF-8 无 charset 头, 须手动 r.encoding='utf-8'
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

SXHM_BASE = 'https://www.sxhm.com'
LIST_API = SXHM_BASE + '/searchs/collections.html'
DETAIL_TPL = SXHM_BASE + '/collections/detail/{id}.html'
PAGE_SIZE = 12

# 题名玉系预筛 (陕西标题多带 玉; 裸 璧/琮/璜 罕见, 不收以防假阳性)
JADE_TITLE_RE = re.compile(r'玉|翡翠|玛瑙|瑪瑙')
# 题名级假阳性排除 (2026-11-24 实测 999 新件: 玉壶春瓶/琉璃渣斗/搪瓷盘)
FAKE_TITLE_RE = re.compile(r'玉壶春|琉璃|搪瓷')
# 详情页站 chrome 图 (每页都有的 logo/二维码)
CHROME_IMGS = {
    '/Uploads/Picture/2021/11/05/s6185032db4faf.png',
    '/Uploads/Picture/2023/02/14/s63eae4ff6f316.png',
    '/Uploads/Picture/2023/02/15/s63ec8c8fc4e56.png',
}
NIAN_RE = re.compile(r'[（(]?(?:西元|公元)[^）)]*[）)]?')


class ShaanxiSpider(BaseJadeSpider):
    """陕西历史博物馆玉器藏品爬虫 (静态分页列表 + 详情页)。"""

    def __init__(self, config=None):
        super().__init__(
            name='shaanxi',
            museum_name='Shaanxi History Museum',
            museum_name_cn='陕西历史博物馆',
            base_url=SXHM_BASE,
            config=config,
        )
        # 国内站强制直连 (2026-11-23 教训: HTTPS_PROXY 残留致 ProxyError)
        self.session.trust_env = False
        self.session.headers.update({
            'Referer': SXHM_BASE + '/collection.html',
            'X-Requested-With': 'XMLHttpRequest',
        })
        self._records: Dict[str, Dict] = {}

    # ── 发现 ──

    def _list_page(self, page: int) -> Optional[str]:
        try:
            resp = self.get(LIST_API, params={
                'pagesize': PAGE_SIZE, 'tpl_file': 'collection',
                'p': page, 'zhenguan': 0,
            })
            resp.encoding = 'utf-8'
            return resp.text
        except requests.RequestException:
            return None

    @staticmethod
    def _parse_list(html: str) -> List[Dict]:
        items = []
        for m in re.finditer(
                r'<div class="item"><a href="/collections/detail/(\d+)\.html"'
                r'[^>]*>(.*?)</a>\s*</div>', html, re.S):
            rid, block = m.group(1), m.group(2)
            tm = re.search(r'<div class="h">([^<]+)</div>', block)
            title = html_mod.unescape(tm.group(1)).strip() if tm else ''
            im = re.search(r'<img[^>]+src="([^"]+)"', block)
            img = im.group(1) if im else ''
            if img and img.startswith('/'):
                img = urljoin(SXHM_BASE, img)
            items.append({'rid': rid, 'title': title, 'list_img': img})
        return items

    def discover_items(self) -> List[Dict]:
        out: List[Dict] = []
        page = 1
        prev_rids: set = set()
        while True:
            html = self._list_page(page)
            if html is None:
                print(f"[shaanxi] 第 {page} 页请求失败, 本轮收尾 (下轮补)")
                break
            items = self._parse_list(html)
            if not items:
                break
            rids = {it['rid'] for it in items}
            if page > 1 and rids == prev_rids:  # 越界重复内容防死循环
                break
            prev_rids = rids
            for it in items:
                if not JADE_TITLE_RE.search(it['title']):
                    continue
                item_id = f'sxhm_{it["rid"]}'
                if item_id in self._records:
                    continue
                self._records[item_id] = it
                out.append({
                    'item_id': item_id,
                    'title': it['title'],
                    'era': '',
                    'detail_url': DETAIL_TPL.format(id=it['rid']),
                })
            page += 1
        print(f"[shaanxi] 全库翻页至第 {page - 1} 页, 题名命中玉系 {len(out)} 件")
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
        rid = re.search(r'/detail/(\d+)\.html', detail_url or '')
        item_id = f'sxhm_{rid.group(1)}' if rid else ''
        rec = self._records.get(item_id) or {}
        list_title = rec.get('title') or ''

        try:
            resp = self.get(detail_url)
            resp.encoding = 'utf-8'
            text = resp.text
        except requests.RequestException:
            return {'item_id': item_id, 'title': list_title, 'image_urls': [],
                    'skip_reason': '网络错误'}

        m = re.search(r'<title>([^<]+?)_陕西历史博物馆', text)
        title = html_mod.unescape(m.group(1)).strip() if m else list_title
        dm = re.search(r'<meta name="description" content="([^"]+)"', text)
        description = html_mod.unescape(dm.group(1)).strip() if dm else ''

        # 假阳性过滤: 题名级显性非玉 (2026-11-24 实测: 玉壶春瓶/琉璃渣斗/
        # 搪瓷盘)。列表预筛已限题名含玉|翡翠|玛瑙, 此处只剔显性假词,
        # 不扫描述 (玉件描述可能提 出土于窑址/陶罐 等词, 宽泛扫会误杀)
        if FAKE_TITLE_RE.search(title):
            self._record_skip(item_id, 'not jade (题名)', title, '')
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'not jade'}

        # 主图: 详情页 Uploads 图去掉站 chrome; 列表图兜底
        cands: List[str] = []
        for im in re.findall(r'<img[^>]+src="(/Uploads/Picture/[^"]+\.(?:jpg|jpeg|png))"',
                             text, re.I):
            if im in CHROME_IMGS:
                continue
            u = urljoin(SXHM_BASE, im)
            if u not in cands:
                cands.append(u)
        list_img = rec.get('list_img') or ''
        if list_img and list_img not in cands:
            cands.append(list_img)
        if not cands:
            self._record_skip(item_id, 'no image', title, '')
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}

        era_raw = NIAN_RE.sub('', ' '.join([title, description[:300]])).strip()
        era_result = map_era_zh(era_raw)
        material_raw = ' '.join(x for x in [title, description[:200]] if x)
        extra = {
            'title': title,
            'material_raw': material_raw,
            'dimensions_raw': '',
            'page_url': detail_url,
            'accession_number': '',
            'culture': '中国',
            'era_raw': era_raw[:150],
            'license': '陕西历史博物馆官网图片 (未声明授权条款, 学术研究使用)',
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
            'description': description,
            'material': map_material_zh(material_raw),
            'dimensions': '',
            'source': '陕西历史博物馆',
            'image_groups': [cands],
            'extra_metadata': extra,
        }
