"""
古玉鉴真 — 河南博物院 (henan) 爬虫

- 静态站, 服务端分页, 无需浏览器 (2026-11-18 探测, 证据
  scraped_data/_site_probe/henan/):
  - 列表: /ch/collection/{tab}/index.html?pageIndex=N#list, 5 个 tab:
    appraise 文物品鉴 30页×25 / centralPlains 中原藏珍 49页×22 /
    digital 数字文物 6页×28 / boutique 藏品精粹 1页×40 /
    treasure 镇院之宝 1页×25 (合计 ~2000 件, 全 tab 混排各材质)
  - 条目: <a href="//www.chnmus.net/content/redirect?id={id}"> +
    标题 (common-component-box-title) + data-bg 列表小图
  - 详情: redirect → /ch/collection/appraise/details.html?id={id},
    appraise-details-content 内 <p> 块 (img 大图 + 正文, 正文首段即
    品名+时代+材质+尺寸, 如「窦泰墓志，北齐，石灰岩质，高98厘米…」)
- 过滤: 列表级题名玉系关键词 (玉/翡翠/玛瑙/璧/琮/璜/圭/璋/玦/珑/珏)
  才进详情; 详情级正文玉质词复核 (JADE_DESC_RE), 非玉终态留档
  (窦泰墓志 石灰岩质 类即列表级筛掉, 不烧详情请求)
- 图片: 详情页 <img src="/sitesources/hnsbwy/upload/..."> 为主
  (与列表 data-bg 不同文件, 实测详情图更大), 列表图作回退
- item_id: henan_{redirect id} (512156972217186832 型, 无碰撞风险)
- 网络: 国内直连; 基类 3-8s 延时
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

HENAN_BASE = 'https://www.chnmus.net'
LIST_TPL = HENAN_BASE + '/ch/collection/{tab}/index.html'
DETAIL_TPL = HENAN_BASE + '/ch/collection/appraise/details.html?id={id}'

# (tab, 页数) — 2026-11-18 实测; 页数在运行时从分页器重新探测,
# 此表仅作顺序与上限参考 (0 = 无分页, 单页)
TABS = [
    ('appraise', 30),       # 文物品鉴
    ('centralPlains', 49),  # 中原藏珍
    ('digital', 6),         # 数字文物
    ('boutique', 0),        # 藏品精粹 (单页 40)
    ('treasure', 0),        # 镇院之宝 (单页 25)
]

# 列表级题名玉系关键词 (器形词仅取玉器专属字形, 佩/环 过宽不取)
JADE_TITLE_RE = re.compile(
    r'玉|翡翠|玛瑙|瑪瑙|璧|琮|璜|圭|璋|玦|珑|瑗|珩|珏|瓘|璏')

# 详情级玉质复核词 (材质 + 玉器器形)
JADE_DESC_RE = re.compile(
    r'玉质|白玉|青玉|碧玉|青白玉|黄玉|墨玉|翡翠|玛瑙|瑪瑙|和田|岫玉|独山|'
    r'软玉|硬玉|玉器|玉佩|玉璧|玉琮|玉圭|玉璜|玉玦|玉环|玉璏|玉带|玉印|玉玺|'
    r'玉龙|玉人|玉鸟|玉蝉|玉鱼|玉戈|玉刀|玉戚|玉璋|玉梳|玉勒|玉管|玉珠|玉坠|'
    r'玉饰|玉雕|玉钺|玉斧|玉铲|玉凿|玉璧|玉瑗|玉珩|玉块|玉料|玉片|玉板|'
    r'镂雕.*玉|玉镂雕|玉质优良|玉石')
# 石质排除 (详情标题/正文/类型字段显性非玉)
NON_JADE_RE = re.compile(
    r'石灰岩质|大理石|花岗岩|砂岩|石质|石器|石刻|墓志|陶质|陶器|瓷质|瓷器|'
    r'青花|釉|窑|铜质|铜器|青铜|铁质|铁器|金器|银器|木质|骨制|象牙|玉壶春')

NIAN_RE = re.compile(r'[（(]?(?:西元|公元)[^）)]*[）)]?')


class HenanSpider(BaseJadeSpider):
    """河南博物院玉器藏品爬虫 (静态列表 + 详情页)。"""

    def __init__(self, config=None):
        super().__init__(
            name='henan',
            museum_name='Henan Museum',
            museum_name_cn='河南博物院',
            base_url=HENAN_BASE,
            config=config,
        )
        self._records: Dict[str, Dict] = {}

    # ── 发现 ──

    def _list_page(self, tab: str, page: int) -> Optional[str]:
        url = LIST_TPL.format(tab=tab)
        params = {'pageIndex': str(page)} if page > 1 else None
        try:
            resp = self.get(url, params=params)
            return resp.text
        except requests.RequestException:
            return None

    @staticmethod
    def _parse_list(html: str) -> List[Dict]:
        """三种列表 markup (2026-11-19 实测):
        - appraise/centralPlains: data-bg + box-title
        - boutique: data-bg + cp-title
        - digital: 直接 <img src> + exhibits-name 内 <span>
        """
        items: List[Dict] = []
        for m in re.finditer(
                r'<a href="(//www\.chnmus\.net/content/redirect\?id=(\d+))"'
                r'[^>]*>(.*?)</a>', html, re.S):
            href, rid, block = m.group(1), m.group(2), m.group(3)
            tm = (re.search(r'box-title">\s*([^<]{1,60})\s*<', block)
                  or re.search(r'cp-title">\s*([^<]{1,60})\s*<', block)
                  or re.search(r'exhibits-name">\s*<span>([^<]{1,60})</span>',
                               block))
            title = html_mod.unescape(tm.group(1)).strip() if tm else ''
            im = re.search(r'data-bg="([^"]+)"', block)
            if not im:
                im = re.search(r'<img[^>]+src="([^"]+)"', block)
            img = im.group(1) if im else ''
            if img and img.startswith('//'):
                img = 'https:' + img
            items.append({'rid': rid, 'title': title,
                          'list_url': 'https:' + href, 'list_img': img})
        return items

    def discover_items(self) -> List[Dict]:
        out: List[Dict] = []
        seen: set = set()
        for tab, _ in TABS:
            tab_total = 0
            page = 1
            max_pages = 1
            prev_rids: set = set()
            while page <= max_pages:
                html = self._list_page(tab, page)
                if html is None:
                    print(f"[henan] tab {tab} 第 {page} 页请求失败, "
                          f"本轮收尾该 tab (下轮补)")
                    break
                items = self._parse_list(html)
                rids = {it['rid'] for it in items}
                # 越界 pageIndex 返回重复内容 (2026-11-18 教训: 死循环
                # 烧光整日 1500 配额) → 与上页相同即收尾
                if not items or (page > 1 and rids == prev_rids):
                    break
                prev_rids = rids
                # 分页探测: 首屏读最大 pageIndex, 作硬上限
                if page == 1:
                    pages = [int(p) for p in
                             re.findall(r'pageIndex=(\d+)#list', html)]
                    max_pages = max(pages) if pages else 1
                    if max_pages > 1:
                        print(f"[henan] tab {tab}: {max_pages} 页")
                for it in items:
                    if not JADE_TITLE_RE.search(it['title']):
                        continue  # 列表级题名预筛, 非玉不烧详情请求
                    item_id = f'henan_{it["rid"]}'
                    if item_id in seen:
                        continue
                    seen.add(item_id)
                    it['_tab'] = tab
                    self._records[item_id] = it
                    out.append({
                        'item_id': item_id,
                        'title': it['title'],
                        'era': '',
                        'detail_url': it['list_url'],
                    })
                    tab_total += 1
                page += 1
            print(f"[henan] tab {tab}: 题名命中玉系 {tab_total} 件")
        return out

    # ── 详情 ──

    def _record_skip(self, item_id: str, reason: str, title: str, era: str):
        with open(self.output_dir / 'skip_log.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'item_id': item_id, 'reason': reason, 'title': title,
                'era': era, 'logged_at': datetime.now().isoformat(),
            }, ensure_ascii=False) + '\n')
            f.flush()

    def _parse_detail(self, detail_url: str) -> Optional[Dict]:
        """详情页解析 (appraise/centralPlains 文物品鉴模板; boutique 用
        _parse_treasure_detail, digital 不取详情走 3D 平台)。"""
        try:
            resp = self.get(detail_url)  # requests 自动跟随 redirect
            text = resp.text
            final_url = resp.url
        except requests.RequestException:
            return None
        out: Dict = {'title': '', 'era': '', 'description': '', 'images': [],
                     'page_url': final_url}
        m = re.search(r'<title>\s*([^<\n-]+?)(?:\s*-\s*河南博物院)?\s*</title>',
                      text)
        if m:
            out['title'] = html_mod.unescape(m.group(1)).strip()
        # 图片: 正文大图 (sitesources upload)
        for im in re.findall(r'<img[^>]+src="(/sitesources/[^"]+\.(?:jpg|jpeg|png))"',
                             text):
            u = urljoin(HENAN_BASE, im)
            if u not in out['images']:
                out['images'].append(u)
        # 正文: appraise-details-content 内 <p> 文本
        m = re.search(r'<div class="appraise-details-content">(.*?)</div>\s*</div>\s*</div>',
                      text, re.S)
        seg = m.group(1) if m else text
        paras = []
        for pm in re.finditer(r'<p[^>]*>(.*?)</p>', seg, re.S):
            txt = re.sub(r'<[^>]+>', ' ', html_mod.unescape(pm.group(1)))
            txt = re.sub(r'\s+', ' ', txt).strip()
            if txt:
                paras.append(txt)
        out['description'] = ' '.join(paras)
        # 时代: 正文首段「品名，时代，材质…」的第二段 (逗号/，分隔)
        if paras:
            parts = [x.strip() for x in re.split(r'[，,]', paras[0])]
            for part in parts[1:4]:
                if map_era_zh(NIAN_RE.sub('', part)):
                    out['era'] = part
                    break
        return out

    def _parse_treasure_detail(self, detail_url: str) -> Optional[Dict]:
        """boutique 详情模板: treasure-content-attribute 结构化字段
        (类型: 瓷器 / 年代: 宋) + collection_img 多视图画廊。"""
        try:
            resp = self.get(detail_url)
            text = resp.text
            final_url = resp.url
        except requests.RequestException:
            return None
        out: Dict = {'title': '', 'era': '', 'description': '', 'images': [],
                     'page_url': final_url, 'attributes': {}}
        m = re.search(r'<title>\s*([^<\n-]+?)(?:\s*-\s*河南博物院)?\s*</title>',
                      text)
        if m:
            out['title'] = html_mod.unescape(m.group(1)).strip()
        # 画廊图 (多视图, collection_img 编号文件)
        for im in re.findall(r'<img[^>]+src="(//www\.chnmus\.net/webfile/'
                             r'collection_img/[^"]+)"', text):
            if im not in out['images']:
                out['images'].append('https:' + im)
        # 结构化字段: 类型/年代/尺寸/质地...
        attrs = {}
        for am in re.finditer(
                r'treasure-content-attribute-item">\s*([^:：<]+)\s*[:：]\s*'
                r'([^<]+)<', text):
            attrs[am.group(1).strip()] = am.group(2).strip()
        out['attributes'] = attrs
        out['era'] = attrs.get('年代', '')
        out['description'] = ' '.join(f'{k}: {v}' for k, v in attrs.items())
        return out

    def parse_detail(self, detail_url: str) -> Dict:
        rid = re.search(r'id=(\d+)', detail_url or '')
        item_id = f'henan_{rid.group(1)}' if rid else ''
        rec = self._records.get(item_id) or {}
        list_title = rec.get('title') or ''
        tab = rec.get('_tab') or ''

        # ── digital (数字文物): 详情指向外部 3D 平台 (4dscene), 不取详情;
        #    题名含明确玉材质词 (青玉/白玉/玉龙...) 即收, 否则终态留档
        if tab == 'digital':
            if NON_JADE_RE.search(list_title):
                self._record_skip(item_id, 'not jade (题名材质)', list_title, '')
                return {'item_id': item_id, 'title': list_title,
                        'image_urls': [], 'skip_reason': 'not jade'}
            img = rec.get('list_img') or ''
            if not img:
                self._record_skip(item_id, 'no image', list_title, '')
                return {'item_id': item_id, 'title': list_title,
                        'image_urls': [], 'skip_reason': 'no image'}
            era_result, era_approx = map_era_zh(list_title), False
            extra = {
                'title': list_title,
                'material_raw': list_title,
                'dimensions_raw': '',
                'page_url': detail_url,
                'accession_number': '',
                'culture': '中国',
                'era_raw': '',
                'license': '河南博物院官网图片 (未声明授权条款, 学术研究使用)',
            }
            if era_result:
                extra['era_mapped_code'] = era_result[0]
                extra['era_mapped_name'] = era_result[1]
            else:
                extra['era_mapped_code'] = None
                extra['era_mapped_name'] = None
            return {
                'item_id': item_id,
                'title': list_title,
                'era': '',
                'description': '',
                'material': map_material_zh(list_title),
                'dimensions': '',
                'source': '河南博物院',
                'image_groups': [[img]],
                'extra_metadata': extra,
            }

        # ── boutique: treasure 结构化模板; 其余: 文物品鉴散文模板
        if tab == 'boutique':
            detail = self._parse_treasure_detail(detail_url)
        else:
            detail = self._parse_detail(detail_url)
        if detail is None:
            return {'item_id': item_id, 'title': list_title, 'image_urls': [],
                    'skip_reason': '网络错误'}

        title = detail.get('title') or list_title
        desc = detail.get('description') or ''
        full_text = title + ' ' + desc

        # 详情复核: 石质/其他材质显性排除 → 终态; 无玉质词 → 终态
        if NON_JADE_RE.search(full_text) and not JADE_DESC_RE.search(full_text):
            self._record_skip(item_id, 'not jade (详情材质)', title,
                              detail.get('era') or '')
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'not jade'}
        if not JADE_DESC_RE.search(full_text):
            self._record_skip(item_id, 'not jade (详情无玉质描述)', title,
                              detail.get('era') or '')
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'not jade'}

        # 图片组: 详情大图 → 列表图回退
        cands = list(detail.get('images') or [])
        list_img = rec.get('list_img') or ''
        if list_img and list_img not in cands:
            cands.append(list_img)
        if not cands:
            self._record_skip(item_id, 'no image', title,
                              detail.get('era') or '')
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}

        era_raw = NIAN_RE.sub('', detail.get('era') or '').strip()
        era_result, era_approx = map_era_zh(era_raw), False
        if era_result:
            era_approx = is_approx_era_zh(era_raw)

        material_raw = ' '.join(x for x in [title, desc[:300]] if x)
        extra = {
            'title': title,
            'material_raw': material_raw,
            'dimensions_raw': '',
            'page_url': detail.get('page_url') or detail_url,
            'accession_number': '',
            'culture': '中国',
            'era_raw': era_raw,
            'license': '河南博物院官网图片 (未声明授权条款, 学术研究使用)',
        }
        if era_result:
            extra['era_mapped_code'] = era_result[0]
            extra['era_mapped_name'] = era_result[1]
            if era_approx:
                extra['era_approx'] = True
        else:
            extra['era_mapped_code'] = None
            extra['era_mapped_name'] = None

        return {
            'item_id': item_id,
            'title': title,
            'era': era_raw,
            'description': desc,
            'material': map_material_zh(material_raw),
            'dimensions': '',
            'source': '河南博物院',
            'image_groups': [cands],
            'extra_metadata': extra,
        }
