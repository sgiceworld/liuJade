"""
古玉鉴真 — 山东博物馆 (shandong) 爬虫

- 大汉版通 (TRS WCM) 静态站 (2026-11-24 探测, 证据
  scraped_data/_site_probe/shandong*):
  - 分类: /col/col271708/index.html = 玉石器 (全站玉类仅此一栏,
    10 件精选: 玉串饰/翡翠透雕带钩/白玉梅花扁瓶/黄玉鹿首壶/
    松竹梅玛瑙洗/青玉龙/痕都斯坦玉盘/兽面纹玉锛等, 全为玉题名)
  - 分页: ?pageNum=N 无效 (服务端总返回同一 10 件清单), totalRecord:10
  - 条目: /art/2022/9/14/art_271708_{id}.html, 列表图
    /Uploads/Picture/.../s*.jpg (有 _742_742_ 缩略变体)
  - 详情: <title>山东博物馆 玉石器 {品名}</title>, 正文 <p> 首段即品名,
    详情图与列表图不同文件 (更大), 无结构化时代/尺寸字段
- 编码坑: 页面 UTF-8 但无 charset 头, requests 误判 ISO-8859-1 →
    手动 r.encoding='utf-8'
- 馆方分类玉石器直接信任 (全玉题名, 无过滤需求)
- item_id: sd_{artid} (无碰撞)
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

SD_BASE = 'https://www.sdmuseum.com'
CATEGORY_URL = SD_BASE + '/col/col271708/index.html'
NIAN_RE = re.compile(r'[（(]?(?:西元|公元)[^）)]*[）)]?')


class ShandongSpider(BaseJadeSpider):
    """山东博物馆玉器藏品爬虫 (静态分类 + 详情页)。"""

    def __init__(self, config=None):
        super().__init__(
            name='shandong',
            museum_name='Shandong Museum',
            museum_name_cn='山东博物馆',
            base_url=SD_BASE,
            config=config,
        )
        # 国内站强制直连 (2026-11-23 教训: HTTPS_PROXY 残留致 ProxyError)
        self.session.trust_env = False
        self._records: Dict[str, Dict] = {}

    # ── 发现 ──

    def discover_items(self) -> List[Dict]:
        items: List[Dict] = []
        try:
            resp = self.get(CATEGORY_URL)
            resp.encoding = 'utf-8'
            html = resp.text
        except requests.RequestException:
            print("[shandong] 分类页请求失败")
            return items
        for m in re.finditer(
                r'<a href="(' + re.escape(SD_BASE) +
                r'/art/[^"]+/art_271708_(\d+)\.html)"[^>]*>(.*?)</a>',
                html, re.S):
            url, aid, block = m.group(1), m.group(2), m.group(3)
            tm = re.search(r'title="([^"]+)"', block)
            title = html_mod.unescape(tm.group(1)).strip() if tm else ''
            im = re.search(r'<img[^>]+src="([^"]+)"', block)
            img = im.group(1) if im else ''
            if img and img.startswith('/'):
                img = urljoin(SD_BASE, img)
            item_id = f'sd_{aid}'
            if item_id in self._records:
                continue
            self._records[item_id] = {'title': title, 'list_img': img}
            items.append({
                'item_id': item_id,
                'title': title,
                'era': '',
                'detail_url': url,
            })
        print(f"[shandong] 玉石器: 共发现 {len(items)} 件")
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
        aid = re.search(r'art_271708_(\d+)\.html', detail_url or '')
        item_id = f'sd_{aid.group(1)}' if aid else ''
        rec = self._records.get(item_id) or {}
        list_title = rec.get('title') or ''

        try:
            resp = self.get(detail_url)
            resp.encoding = 'utf-8'
            text = resp.text
        except requests.RequestException:
            return {'item_id': item_id, 'title': list_title, 'image_urls': [],
                    'skip_reason': '网络错误'}

        m = re.search(r'<title>山东博物馆\s*玉石器\s*([^<]+?)</title>', text)
        title = html_mod.unescape(m.group(1)).strip() if m else list_title
        # 正文 <p>: 首段品名, 其后为描述
        paras = []
        for pm in re.finditer(r'<p[^>]*>(.*?)</p>', text, re.S):
            txt = re.sub(r'<[^>]+>', ' ', html_mod.unescape(pm.group(1)))
            txt = re.sub(r'\s+', ' ', txt).strip()
            if txt:
                paras.append(txt)
        description = ' '.join(paras[1:]) if len(paras) > 1 else ''
        # 详情图 (与列表图不同文件, 更大); 列表图回退
        cands: List[str] = []
        for im in re.findall(r'<img[^>]+src="([^"]+\.(?:jpg|jpeg|png))"',
                             text, re.I):
            u = urljoin(SD_BASE, im) if im.startswith('/') else im
            if u not in cands:
                cands.append(u)
        list_img = rec.get('list_img') or ''
        if list_img and list_img not in cands:
            cands.append(list_img)
        if not cands:
            self._record_skip(item_id, 'no image', title, '')
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}

        era_raw = NIAN_RE.sub('', ' '.join([title, description])).strip()
        era_result = map_era_zh(era_raw)
        era_code = era_result[0] if era_result else None
        era_name = era_result[1] if era_result else None
        material_raw = '玉石器 ' + title
        extra = {
            'title': title,
            'material_raw': material_raw,
            'dimensions_raw': '',
            'page_url': detail_url,
            'accession_number': '',
            'culture': '中国',
            'era_raw': era_raw[:100],
            'license': '山东博物馆官网图片 (未声明授权条款, 学术研究使用)',
        }
        if era_result:
            extra['era_mapped_code'] = era_code
            extra['era_mapped_name'] = era_name
            if is_approx_era_zh(era_raw):
                extra['era_approx'] = True
        else:
            extra['era_mapped_code'] = None
            extra['era_mapped_name'] = None

        return {
            'item_id': item_id,
            'title': title,
            'era': era_raw[:100],
            'description': description,
            'material': map_material_zh(material_raw),
            'dimensions': '',
            'source': '山东博物馆',
            'image_groups': [cands],
            'extra_metadata': extra,
        }
