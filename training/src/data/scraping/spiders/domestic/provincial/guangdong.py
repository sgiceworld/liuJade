"""
古玉鉴真 — 广东省博物馆 (guangdong) 爬虫

2026-11-27 侦察 (证据 scraped_data/_site_probe/domestic_20261126/guangdong_pw/):
- 旧域 gdmuseum.com 301 → www.gdmuseum.org.cn (robots.txt 404 无声明)
- 藏品库 col49/list 全库 3764 件, 静态服务端分页 16 件/页,
  /cn/col49/list_{N}?keyword= 关键词搜索 (名称/年代/类型三字段)
- 列表卡片即含 名称/年代/类型 + 缩略图
- 详情 /cn/col49/{id} 静态页: .qui-tt 品名; dl.cp_list 内
  span[name=infoName/infoAge/infoType/infoTexture/infoSizes/infoAuthor]
  全字段; 大图在 imgHuilanMediaArray.push({'src':...}) 可多张,
  attachment/ 前缀需补斜杠
- 搜索轴 (2026-11-27 实测): 玉石器 49 / 玉 85 / 玛瑙 6 / 珊瑚 9 /
  水晶 1 / 琥珀 1; 翡翠/绿松石/青金石 0
- 藏品总目 col73 为 18 万行纯文本表 (无图无链接), 不收
- 玉轴假阳性: 玉壶春(瓷)/玉兰花(瓷)/何瑗玉 何昆玉(人名印/画),
  按 FAKE_TITLE_RE + 类型排除 (书法、绘画/玺印符牌/瓷器/陶瓷/陶器/
  金银器/铜器/钱币); 玉雕"金鸡报喜" 类型=岩石和矿物 需保留
- 国内站强制直连
- item_id: gd_{id} (无碰撞)
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

GD_BASE = 'https://www.gdmuseum.org.cn'
LIST_TPL = GD_BASE + '/cn/col49/list'       # 第 1 页
LIST_PAGE_TPL = GD_BASE + '/cn/col49/list_{page}'  # 第 N 页 (N>=2)
PAGE_SIZE = 16  # 2026-11-27 实测

# 搜索轴: (关键词, 是否按类型过滤)
# 2026-11-27 实测: 珊瑚 9 命中 8 件为珊瑚红瓷器釉色 + 1 件阿拉伯墓碑
# (珊瑚不在 12 材质枚举内) → 整轴放弃; 玛瑙/水晶/琥珀件均已含于玉石器轴
AXES = [
    ('玉石器', False),   # 类型轴, 全收
    ('玉', True),        # 名称轴, 需过滤假阳性
    ('玛瑙', False),
]

# 玉轴假阳性: 玉壶春=瓷器, 玉兰花=瓷画, 汉白玉=大理石,
# 玉堂佳器=瓷款, 潘玉书=石湾窑人名, 嵌玉/镶玉=木器/锡器饰玉, 玉纹=端砚纹饰
FAKE_TITLE_RE = re.compile(
    r'玉壶春|玉兰花|汉白玉|玉堂佳器|潘玉书|嵌玉|镶玉|仿古玉纹')
# 玉轴按类型排除 (人名玉/画名玉 落在这几类)
EXCLUDED_TYPES_RE = re.compile(r'书法|绘画|玺印|瓷器|陶瓷|陶器|金银|铜器|钱币|宣传品')

# 尺寸提取 (厘米/毫米/米/克, 常见量词)
DIM_RE = re.compile(
    r'(通高|通长|通宽|残高|残长|口径|底径|腹径|足径|最大径|高|宽|长|厚|深|重)'
    r'\s*([0-9]+(?:\.[0-9]+)?)\s*(厘米|毫米|米|克|千克|公斤)')


class GuangdongSpider(BaseJadeSpider):
    """广东省博物馆藏品库玉器爬虫 (静态列表 + 静态详情)。"""

    def __init__(self, config=None):
        super().__init__(
            name='guangdong',
            museum_name='Guangdong Museum',
            museum_name_cn='广东省博物馆',
            base_url=GD_BASE,
            config=config,
        )
        # 国内站强制直连 (2026-11-23 教训: HTTPS_PROXY 残留致 ProxyError)
        self.session.trust_env = False
        self._records: Dict[str, Dict] = {}

    # ── 发现 ──

    def _list_axis(self, keyword: str, filter_types: bool) -> List[Dict]:
        """翻页抓取一个关键词轴, 返回候选列表 (跨轴去重由 discover 做)。"""
        out: List[Dict] = []
        page = 1
        while True:
            url = LIST_TPL if page == 1 else LIST_PAGE_TPL.format(page=page)
            try:
                resp = self.get(url, params={'keyword': keyword})
                resp.encoding = resp.apparent_encoding or 'utf-8'
                text = resp.text
            except requests.RequestException:
                print(f"[guangdong] {keyword} 第 {page} 页请求失败, 本轮收尾 (下轮补)")
                break
            found = False
            for m in re.finditer(
                    r'<a href="/cn/col49/(\d+)" class="qui-hover">(.*?)</a>',
                    text, re.S):
                blk = m.group(1), m.group(2)
                gid = blk[0]
                block = blk[1]
                im = re.search(r'<img src="([^"]+)"', block)
                nm = re.search(r'名称：</span><span>([^<]*)</span>', block)
                em = re.search(r'年代：</span><span>([^<]*)</span>', block)
                tm = re.search(r'类型：</span><span>([^<]*)</span>', block)
                if not nm:
                    continue
                title = html_mod.unescape(nm.group(1)).strip()
                era = html_mod.unescape(em.group(1)).strip() if em else ''
                typ = html_mod.unescape(tm.group(1)).strip() if tm else ''
                if filter_types:
                    if FAKE_TITLE_RE.search(title):
                        continue
                    if typ and EXCLUDED_TYPES_RE.search(typ):
                        continue
                if not title:
                    continue
                found = True
                item_id = f'gd_{gid}'
                if item_id in self._records:
                    continue
                self._records[item_id] = {
                    'id': gid, 'title': title, 'era': era, 'type': typ,
                    'img': im.group(1) if im else '',
                }
                out.append({
                    'item_id': item_id,
                    'title': title,
                    'era': era,
                    'detail_url': f'{GD_BASE}/cn/col49/{gid}',
                })
            if not found:
                break
            page += 1
            if page > 30:  # 硬上限防死循环
                print(f"[guangdong] {keyword} 翻页超 30 页, 强制收尾")
                break
        return out

    def discover_items(self) -> List[Dict]:
        out: List[Dict] = []
        for kw, filt in AXES:
            before = len(self._records)
            items = self._list_axis(kw, filt)
            print(f"[guangdong] 轴 {kw}: 新命中 {len(self._records) - before} 件"
                  f" (去重后累计 {len(self._records)})")
            out.extend(items)
        return out

    # ── 详情 ──

    def parse_detail(self, detail_url: str) -> Dict:
        m = re.search(r'/cn/col49/(\d+)', detail_url or '')
        item_id = f'gd_{m.group(1)}' if m else ''
        rec = self._records.get(item_id) or {}
        list_title = (rec.get('title') or '').strip()

        try:
            resp = self.get(detail_url)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            text = resp.text
        except requests.RequestException:
            return {'item_id': item_id, 'title': list_title, 'image_urls': [],
                    'skip_reason': '网络错误'}

        tm = re.search(r'<div class="qui-tt">([^<]+)</div>', text)
        title = html_mod.unescape(tm.group(1)).strip() if tm else list_title

        def field(name: str) -> str:
            fm = re.search(rf'<span name="{name}">([^<]*)</span>', text)
            return html_mod.unescape(fm.group(1)).strip() if fm else ''

        era_text = field('infoAge')
        type_text = field('infoType')
        texture = field('infoTexture')
        size_text = field('infoSizes')
        author = field('infoAuthor')

        # 大图: imgHuilanMediaArray 可多张 → dd img → 下载链接 → 列表缩略图
        cands: List[str] = []
        for u in re.findall(r"imgHuilanMediaArray\.push\(\{'src':\"([^\"]+)\"", text):
            full = ('/' + u) if u.startswith('attachment/') else urljoin(GD_BASE, u)
            if full not in cands:
                cands.append(full)
        im = re.search(r'<dd>\s*<img src="([^"]+)"', text)
        if im:
            full = urljoin(GD_BASE, im.group(1))
            if full not in cands:
                cands.append(full)
        dm = re.search(r'<a href="(/upload/[^"]+\.(?:jpg|jpeg|png))" target="_blank">下载</a>', text)
        if dm:
            full = urljoin(GD_BASE, dm.group(1))
            if full not in cands:
                cands.append(full)
        if not cands and rec.get('img'):
            full = urljoin(GD_BASE, rec['img'])
            cands.append(full)
        if not cands:
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}

        # 尺寸
        dims = []
        for dm in DIM_RE.finditer(size_text):
            dims.append(f"{dm.group(1)}{dm.group(2)}{dm.group(3)}")
        dimensions = json.dumps({'尺寸': ' '.join(dims)}, ensure_ascii=False) if dims else ''

        era_raw = ' '.join(x for x in (rec.get('era') or '', era_text) if x)
        era_result = map_era_zh(era_raw)
        material_raw = ' '.join(x for x in (title, texture, type_text) if x)
        extra = {
            'title': title,
            'material_raw': material_raw,
            'dimensions_raw': dimensions,
            'page_url': detail_url,
            'accession_number': '',
            'culture': '中国',
            'era_raw': era_raw[:150],
            'type': type_text,
            'texture': texture,
            'author': author,
            'license': '广东省博物馆官网图片 (未声明授权条款, 学术研究使用)',
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
            'material': map_material_zh(material_raw),
            'dimensions': dimensions,
            'source': '广东省博物馆',
            'image_groups': [cands],
            'extra_metadata': extra,
        }
