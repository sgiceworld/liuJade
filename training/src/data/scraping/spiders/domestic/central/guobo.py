"""
古玉鉴真 — 中国国家博物馆 (guobo) 爬虫

- 搜索 API: GET https://www.chnmuseum.cn/SearchAll (TRS 搜索平台),
  2026-11-18 从 /qwjs/cpjs/ 页 JS (searchStart) 挖出。关键词轴
  SearchWord={kw} (SearchScope=DOCTITLE 标题匹配), PageSize=21 分页,
  翻到 '[]' 空列表即到底。
- WAF: 直连必须带完整浏览器头 (尤其 X-Requested-With: XMLHttpRequest
  + Referer), 否则返回 JS 挑战页 (noscript), 已实测。
- classification 字段解码 (2026-11-18 实测): '槽0;槽1;槽2;槽3;槽4;...'
  槽2=质地 (3玉质 2石质 6瓷质 8铁质 18纸质...), 槽3=品类 (24生活用品
  29文献 42兵器...), 槽4=年代 (125元 126明 127清 128近代...)。
  列表级过滤: 质地=3 直接收; 质地=其他非玉 终态拒收留档; 质地空
  (dOCHTMLCON=在另外数据表中) 走详情页复核。
- 关键词轴: 玉 (覆盖绝大多数玉器题名) + 翡翠 + 玛瑙 (无玉字玉材),
  2026-11-18 实测 玉 首屏 21 件中含玉壶春瓶 (瓷质, classification 已滤)。
- 详情页: dOCPUBURL 静态 HTML — meta ArticleTitle/ColumnType,
  clum_titles 品名, clum_tips ul li 时代+尺寸 (JS document.write 包装),
  clum_txt 描述段落; 图 = 搜索结果的 slt (绝对 URL, 与详情页同文件)。
- item_id: guobo_{contentid} (URL tYYYYMMDD_{id}.shtml 中的 id)。
- 网络: 国内直连; 3-8s 延时; 对连发敏感 (2026-11-18 连发两次即
  ReadTimeout, 单发无碍) — 已在基类延时内。
"""

import html as html_mod
import json
import re
from datetime import datetime
from typing import Dict, List, Optional

import requests

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

GUOBO_BASE = 'https://www.chnmuseum.cn'
SEARCH_API = GUOBO_BASE + '/SearchAll'
PAGE_SIZE = 21

# 关键词轴: 玉 / 翡翠 / 玛瑙 (题名匹配)
KEYWORD_AXES = ['玉', '翡翠', '玛瑙']

# 质地 classification 槽位值 (槽2)
MAT_JSON_ID = 3          # 玉质
NON_JADE_MAT_IDS = {'2', '4', '5', '6', '7', '8', '9', '10', '11', '12',
                    '13', '14', '15', '16', '17', '18', '19', '20', '21'}
# 详情页复核: 玉质描述词 (材质 + 器形)
JADE_DESC_RE = re.compile(
    r'玉质|白玉|青玉|碧玉|青白玉|黄玉|墨玉|翡翠|玛瑙|瑪瑙|和田|岫玉|独山|'
    r'软玉|硬玉|玉器|玉佩|玉璧|玉琮|玉圭|玉璜|玉玦|玉环|玉璏|玉带|玉印|玉玺|'
    r'玉龙|玉人|玉鸟|玉蝉|玉鱼|玉戈|玉刀|玉戚|玉璋|玉梳|玉勒|玉管|玉珠|玉坠|'
    r'玉饰|玉雕|镂雕.*玉|玉镂雕')
# 非玉排除 (详情复核时标题即显非玉)
NON_JADE_TITLE_RE = re.compile(
    r'玉壶春|青花|釉里红|斗彩|粉彩|五彩|磁州窑|景德镇|窑[^，。]*$|瓷|'
    r'铜|铁|金|银|锡|铅|木|竹|漆|玻璃|书画|证书|委任状|委任令|命令|决议|'
    r'手稿|文稿|信件|信函|电报|布告|宣言|纲领|条约|章程|地图|照片|胶片|'
    r'报纸|刊物|图书|课本|笔记本|日记|邮票|钱币|军刀|旗帜|匾额|雕塑|石雕')

# npm 教训: 时代字段带「公元/西元」纪年注记时「元」会被金元模式误配,
# 映射前剥掉纪年注记 (guobo 形如 元（公元1206—1368年）)
NIAN_RE = re.compile(r'[（(]?(?:西元|公元)[^）)]*[）)]?')


class GuoboSpider(BaseJadeSpider):
    """中国国家博物馆玉器藏品爬虫 (SearchAll 关键词轴 + 详情页复核)。"""

    def __init__(self, config=None):
        super().__init__(
            name='guobo',
            museum_name='National Museum of China',
            museum_name_cn='中国国家博物馆',
            base_url=GUOBO_BASE,
            config=config,
        )
        # WAF 要求完整浏览器头, 否则 SearchAll 返回 JS 挑战页
        self.session.headers.update({
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': GUOBO_BASE + '/qwjs/cpjs/',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })
        self._records: Dict[str, Dict] = {}

    # ── 发现 ──

    def _search_page(self, kw: str, page: int) -> Optional[List[Dict]]:
        params = {
            'chnlslimit': '75', 'SearchScope': 'DOCTITLE', 'TimeScope': '',
            'SortOrder': '+RELEVANCE', 'SearchWord': kw,
            'PageSize': str(PAGE_SIZE), 'PageNum': str(page),
            'chnls': '75', 'classification': '', 'cutsize': '200',
            'notchnls': '2219,72',
        }
        try:
            resp = self.get(SEARCH_API, params=params)
            data = resp.json()
        except requests.RequestException:
            return None
        except ValueError:
            return None
        return data if isinstance(data, list) else None

    def discover_items(self) -> List[Dict]:
        items: List[Dict] = []
        seen: set = set()
        for kw in KEYWORD_AXES:
            page = 1
            kw_total = 0
            while True:
                recs = self._search_page(kw, page)
                if recs is None:
                    print(f"[guobo] 关键词 {kw} 第 {page} 页请求失败, "
                          f"本轮收尾该轴 (下轮补)")
                    break
                if not recs:
                    break
                for r in recs:
                    m = re.search(r't(\d{8})_(\d+)\.shtml', r.get('dOCPUBURL', ''))
                    cid = m.group(2) if m else None
                    if not cid:
                        continue
                    item_id = f'guobo_{cid}'
                    if item_id in seen:
                        continue
                    seen.add(item_id)
                    self._records[item_id] = r
                    items.append({
                        'item_id': item_id,
                        'title': r.get('dOCTITLE') or '',
                        'era': r.get('nd') or '',
                        'detail_url': r.get('dOCPUBURL') or '',
                        'image_urls': [r.get('slt')] if r.get('slt') else [],
                    })
                kw_total += len(recs)
                page += 1
            print(f"[guobo] 关键词轴 {kw}: 共 {kw_total} 件")
        return items

    # ── 详情 ──

    def _record_skip(self, item_id: str, reason: str, title: str,
                     era: str, cls: str):
        with open(self.output_dir / 'skip_log.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'item_id': item_id, 'reason': reason, 'title': title,
                'era': era, 'classification': cls,
                'logged_at': datetime.now().isoformat(),
            }, ensure_ascii=False) + '\n')
            f.flush()

    @staticmethod
    def _cls_slot(classification: str, idx: int) -> str:
        """classification 'a;b;c;...' 取第 idx 槽 (缺省 '-')。"""
        parts = (classification or '').split(';')
        v = parts[idx] if idx < len(parts) else '-'
        return v if v not in ('', '-') else ''

    def _parse_detail_page(self, detail_url: str) -> Optional[Dict]:
        """详情页静态解析: 品名/时代/尺寸/描述/大图 (JS document.write 包装)。

        大图: 展示 <img src=...> 是缩略图, 放大用的 data-src 才是原图
        (2026-11-18 实测: slt 缩略 ~10KB/200px 被 300px 质量过滤拒收 22 件)。
        """
        try:
            resp = self.get(detail_url)
            text = resp.text
        except requests.RequestException:
            return None
        base = detail_url.rsplit('/', 1)[0] + '/'
        out: Dict = {'title': '', 'era': '', 'dimensions': '', 'description': '',
                     'big_image': '', 'page_image': ''}
        m = re.search(r'<meta\s+name="ArticleTitle"\s+content="([^"]*)"', text)
        if m:
            out['title'] = html_mod.unescape(m.group(1)).strip()
        if not out['title']:
            m = re.search(r'<div class="clum_titles">([^<]+)</div>', text)
            if m:
                out['title'] = html_mod.unescape(m.group(1)).strip()
        # 时代/尺寸: var content='...' 依次出现 (第一个=时代, 第二个=尺寸)
        contents = re.findall(r"var content='([^']*)'", text)
        if contents:
            out['era'] = html_mod.unescape(contents[0]).strip()
        if len(contents) > 1:
            out['dimensions'] = re.sub(
                r'<[^>]+>', ' ',
                html_mod.unescape(contents[1])).strip()
        # 描述: clum_txt 内 <p>
        m = re.search(r'<div class="clum_txt">(.*?)</div>\s*</div>', text, re.S)
        if m:
            paras = re.findall(r'<p[^>]*>(.*?)</p>', m.group(1), re.S)
            out['description'] = ' '.join(
                re.sub(r'<[^>]+>', ' ', html_mod.unescape(p)).strip()
                for p in paras).strip()
        # 图片: data-src 原图 / img src 展示缩略 (相对路径补全)
        m = re.search(r'data-src=[\'"]\./([^\'"]+\.(?:jpg|jpeg|png))', text)
        if m:
            out['big_image'] = base + m.group(1)
        m = re.search(r"<img\s+src=['\"]\./([^'\"]+\.(?:jpg|jpeg|png))", text)
        if m:
            out['page_image'] = base + m.group(1)
        return out

    def parse_detail(self, detail_url: str) -> Dict:
        rec = None
        item_id = ''
        for iid, r in self._records.items():
            if r.get('dOCPUBURL') == detail_url:
                rec = r
                item_id = iid
                break
        title = (rec or {}).get('dOCTITLE') or ''
        cls = (rec or {}).get('classification') or ''
        mat = self._cls_slot(cls, 2)

        # 列表级: 质地=非玉 → 终态拒收 (瓷玉壶春瓶等)
        if mat in NON_JADE_MAT_IDS:
            self._record_skip(item_id, f'not jade (质地={mat})', title,
                              (rec or {}).get('nd') or '', cls)
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'not jade'}

        # 详情页: 质地=3 件直接收; 质地空件须复核玉质。
        # 所有保留件都取详情页 (时代/尺寸/描述 + data-src 原图, 2026-11-18
        # 修复: slt 缩略 ~200px 被 300px 质量过滤拒收)
        detail = self._parse_detail_page(detail_url)
        if detail is None:
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': '网络错误'}
        full_title = detail.get('title') or title
        full_text = full_title + ' ' + (detail.get('description') or '')
        if mat != str(MAT_JSON_ID):
            # 质地空 → 玉质复核 (玉玺/霞帔坠 等数据在另一表)
            if NON_JADE_TITLE_RE.search(full_title) and \
                    not JADE_DESC_RE.search(full_text):
                self._record_skip(item_id, 'not jade (详情复核)', full_title,
                                  detail.get('era') or '', cls)
                return {'item_id': item_id, 'title': full_title,
                        'image_urls': [], 'skip_reason': 'not jade'}
            if not JADE_DESC_RE.search(full_text):
                self._record_skip(item_id, 'not jade (详情无玉质描述)',
                                  full_title, detail.get('era') or '', cls)
                return {'item_id': item_id, 'title': full_title,
                        'image_urls': [], 'skip_reason': 'not jade'}
        title = full_title

        # 图片组: [详情页 data-src 原图, 展示缩略, 搜索 slt]
        cands: List[str] = []
        for u in (detail.get('big_image'), detail.get('page_image'),
                  (rec or {}).get('slt')):
            if u and u not in cands:
                cands.append(u)
        if not cands:
            self._record_skip(item_id, 'no image', title, '', cls)
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}

        era_raw = detail.get('era') or (rec or {}).get('nd') or ''
        era_raw = NIAN_RE.sub('', era_raw).strip()
        era_result, era_approx = map_era_zh(era_raw), False
        if era_result:
            era_approx = is_approx_era_zh(era_raw)

        material_raw = ' '.join(x for x in [title, detail.get('description')] if x)
        extra = {
            'title': title,
            'material_raw': material_raw[:400],
            'dimensions_raw': detail.get('dimensions', '') or '',
            'page_url': detail_url or '',
            'accession_number': '',
            'culture': '中国',
            'era_raw': era_raw,
            'license': '中国国家博物馆官网图片 (未声明授权条款, 学术研究使用)',
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
            'description': detail.get('description', '') or '',
            'material': map_material_zh(material_raw),
            'dimensions': detail.get('dimensions', '') or '',
            'source': '中国国家博物馆',
            'image_groups': [cands],
            'extra_metadata': extra,
        }
