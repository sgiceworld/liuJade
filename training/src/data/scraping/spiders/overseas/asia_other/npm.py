"""
古玉鉴真 — 台北故宫博物院爬虫 (digitalarchive.npm.gov.tw 静态 HTML + IIIF)

探测证据 (2026-11-03, 见 scraped_data/_untested_probe/):
- 搜索: GET /Collection/Search?RegisterType=玉器&PageInfo.PageIndex=N
  &PageInfo.PageSize=300 (PageSize=300 实测有效, 玉器分类 46 页 ≈ 13.5k 件;
  15/30/100 也接受)。POST 同端点被 WAF 拦 (555 Unauthorized), 只能走 GET。
  每页同时渲染 list-item + card 两种模式 (同 cid 双份, 按 cid 去重):
  list-item 的 title 属性带无障碍壳 "移至 品名 另開新視窗",
  card 含 card-title (更干净, 以 card 为准)。
- 详情: /Collection/Detail/{cid}?dep=U, tr/td 字段表
  (文物統一編號/品名/分類/時代/尺寸/說明), 分類=玉器。
- 图片: IIIF manifest /Integrate/GetJson?cid={cid}&dept=U (Presentation 2.0),
  resource @id 形如 .../full/,300/0/default.jpg; 尺寸段替换为
  /full/1600,/ 取大图。iiifod 是 Cantaloupe 服务: 2048px+ 返回 403,
  1600px 实测 200 (~300KB); 标识符内 / 必须保留 %2F 编码 (manifest 已编码)。
- 授权: 低階圖像 (100萬像素) CC0; 中階 (600萬像素) CC BY 4.0 带署名要求;
  IIIF 浏览图按此授权记录 notes。
- 网络: 国内直连不通, 须走 Clash 代理 (HTTPS_PROXY=http://127.0.0.1:7890)。
- item_id 加 npm_ 前缀: 馆方 cid 纯数字 (48k+), 与 cleveland/met 数字 ID
  (42k-99k) 区间重叠, 直接做主键会撞 jade.db 现有记录 (handoff 教训:
  新站点接入前先查 ID 区间)。
- 限速: 基类 3-8s; 500 请求/天/域名 (digitalarchive + iiifod 分别计)。
  单件成本 3 请求 (详情 + manifest + 图), 每日 ~160 件, 全库 ≈ 80 天,
  每日小批量续跑 (checkpoint 断点续传)。
"""

import json
import re
from datetime import datetime
from typing import Dict, List

import requests

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh

# iiifod (Cantaloupe) 证书缺 Subject Key Identifier 扩展, OpenSSL 严格校验
# 拒绝 (curl/Schannel 容忍)。用 truststore 走 Windows 系统证书库
# (证书校验保持开启, 仅换信任源), 见 scraped_data/_untested_probe/ 探测记录
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

NPM_BASE = 'https://digitalarchive.npm.gov.tw'
SEARCH_TPL = (NPM_BASE + '/Collection/Search?RegisterType={cat}'
              '&PageInfo.PageIndex={page}&PageInfo.PageSize={size}'
              '&PageInfo.PageMode=Card')
DETAIL_TPL = NPM_BASE + '/Collection/Detail/{cid}?dep=U'
MANIFEST_TPL = NPM_BASE + '/Integrate/GetJson?cid={cid}&dept=U'
CATEGORY = '玉器'
PAGE_SIZE = 300
IMG_WIDTH = 1600

# list 模式: title 属性带无障碍文本 "移至 品名 另開新視窗" (需剥壳);
# 統一編號短号在 list 行 checkbox value ("品名,,品名,統一編號"), 全号以详情页为准
LIST_ITEM_RE = re.compile(
    r'href="/Collection/Detail/(\d+)\?dep=U"[^>]*class="list-item"'
    r'[^>]*title="([^"]*)"')
# card 模式: card-title 为品名 (list/card 同页双份渲染, 按 cid 合并去重)
CARD_ITEM_RE = re.compile(
    r'href="/Collection/Detail/(\d+)\?dep=U"[^>]*class="card"[^>]*>'
    r'.*?<div class="card-title">([^<]+)</div>', re.S)
# 时代跨度 (明至清/宋或元 等) 跨类别, 不自动映射, 落待OCR确认
ERA_SPAN_RE = re.compile(r'[至或]|～|~')
# 时代字段的「西元」纪年 (如 西元1368-1644年 / 西元前770-前671年,
# 带或不带括号) 含「元」字, 会被金元模式误配, 必须先剥离
ERA_PAREN_RE = re.compile(r'[（(][^)）]*西元[^)）]*[)）]')
# 西元纪年段可重复: 西元前206至西元8年 / 西元前4500至前3000年
ERA_WEST_RE = re.compile(
    r'西元(?:前)?[0-9０-９]+(?:[-~–—至](?:西元)?(?:前)?[0-9０-９]+)*年?')


def _strip_tags(s: str) -> str:
    s = re.sub(r'<[^>]+>', '', s or '').replace('&nbsp;', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def map_npm_era(era: str, title: str):
    """NPM 时代 → (era_code, era_name) 或 None; 返回 (result, is_approx)。

    跨时代跨度两侧同代则映射 (大汶口或良渚 → 文化期), 异代不映射
    (落待OCR确认); 标题作兜底 (如 漢玉蟬 → 秦汉)。
    """
    t = ERA_PAREN_RE.sub('', era or '')
    t = ERA_WEST_RE.sub('', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if ERA_SPAN_RE.search(t):
        left, right = ERA_SPAN_RE.split(t, 1)
        l_map = map_era_zh(left.strip()) if left.strip() else None
        r_map = map_era_zh(right.strip()) if right.strip() else None
        if l_map and r_map and l_map[0] == r_map[0]:
            return l_map, False
        return None, False
    return map_era_zh(' '.join(x for x in [t, title] if x)), is_approx_era_zh(t)


class NpmSpider(BaseJadeSpider):
    """台北故宫博物院玉器藏品爬虫 (静态 HTML + IIIF manifest)。"""

    def __init__(self, config=None):
        super().__init__(
            name='npm',
            museum_name='National Palace Museum, Taipei',
            museum_name_cn='台北故宫博物院',
            base_url=NPM_BASE,
            config=config,
        )
        self.pages_cache_file = self.output_dir / 'discovered_pages.json'

    # ── 发现 ──

    def _load_pages_cache(self) -> Dict[int, List[dict]]:
        if self.pages_cache_file.exists():
            with open(self.pages_cache_file, encoding='utf-8') as f:
                raw = json.load(f)
                return {int(k): v for k, v in raw.items()}
        return {}

    def _save_pages_cache(self, cache: Dict[int, List[dict]]):
        with open(self.pages_cache_file, 'w', encoding='utf-8') as f:
            json.dump({str(k): v for k, v in sorted(cache.items())},
                      f, ensure_ascii=False, indent=1)
            f.flush()

    @staticmethod
    def _parse_search_page(html: str) -> List[dict]:
        """解析搜索页: list 模式拿 (cid, 品名), card 模式品名更干净, 以 card 为准。"""
        by_id: Dict[str, dict] = {}

        def _ensure(cid: str) -> dict:
            if cid not in by_id:
                by_id[cid] = {
                    'item_id': f"npm_{cid}",
                    'title': '',
                    'detail_url': DETAIL_TPL.format(cid=cid),
                }
            return by_id[cid]

        for m in LIST_ITEM_RE.finditer(html):
            cid, attr = m.group(1), m.group(2)
            # 无障碍文本壳: "移至 品名 另開新視窗"
            attr = re.sub(r'^移至\s*|\s*另開新視窗$', '', attr).strip()
            if attr:
                _ensure(cid)['title'] = attr
        for m in CARD_ITEM_RE.finditer(html):
            cid, title = m.group(1), m.group(2)
            _ensure(cid)['title'] = title  # card 标题无壳, 覆盖
        return list(by_id.values())

    def discover_items(self) -> List[Dict]:
        cache = self._load_pages_cache()
        # 首页探测总数 (serializedModel 内嵌 PageCount)
        html = self.get(SEARCH_TPL.format(
            cat=CATEGORY, page=1, size=PAGE_SIZE)).text
        m = re.search(r'"PageCount":(\d+)', html)
        total_pages = int(m.group(1)) if m else 1
        print(f"[npm] 玉器分类共 {total_pages} 页 (每页 {PAGE_SIZE} 件)")
        if 1 not in cache:
            cache[1] = self._parse_search_page(html)
            self._save_pages_cache(cache)

        # 逐页补齐缓存 (断点: 已缓存的页不再请求)
        for page in range(2, total_pages + 1):
            if page in cache:
                continue
            try:
                html = self.get(SEARCH_TPL.format(
                    cat=CATEGORY, page=page, size=PAGE_SIZE)).text
            except requests.RequestException:
                # 网络瞬断: 本轮只处理已缓存的页, 未缓存页下轮补
                print(f"[npm] 第 {page} 页请求失败, 本轮按已缓存页推进")
                break
            cache[page] = self._parse_search_page(html)
            self._save_pages_cache(cache)

        items: List[Dict] = []
        for page in sorted(cache):
            items.extend(cache[page])
        return items

    # ── 详情解析 ──

    def _record_skip(self, cid: str, reason: str, title: str,
                     category: str, era: str):
        """跳过诊断日志: 逐件留档被拒项 (负结果复核证据)。"""
        with open(self.output_dir / 'skip_log.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'item_id': f"npm_{cid}",
                'reason': reason,
                'title': title,
                'category': category,
                'era': era,
                'logged_at': datetime.now().isoformat(),
            }, ensure_ascii=False) + '\n')
            f.flush()

    def parse_detail(self, detail_url: str) -> Dict:
        cid = re.search(r'/Detail/(\d+)', detail_url or '')
        cid = cid.group(1) if cid else ''
        item_id = f"npm_{cid}"

        # 只收窄 requests 异常, RuntimeError (robots/配额) 正常传播 (handoff 教训)
        try:
            html = self.get(detail_url).text
        except requests.RequestException:
            return {'item_id': item_id, 'title': '', 'image_urls': [],
                    'skip_reason': '网络错误'}

        # tr/td 字段表
        fields: Dict[str, str] = {}
        for k, v in re.findall(r'<tr>\s*<td>([^<]+)</td>\s*<td>(.*?)</td>',
                               html, re.S):
            key = _strip_tags(k)
            if key:
                fields[key] = _strip_tags(v)
        title = ''
        m = re.search(r'<div class="details-title">([^<]+)</div>', html)
        if m:
            title = _strip_tags(m.group(1))

        category = fields.get('分類', '')
        era_raw = ' '.join(x for x in [fields.get('時代', ''), title] if x)

        # 过滤: 搜索已按 玉器 分类, 此处兜底 (分类字段含 石 类杂项则拒)
        if category and ('玉' not in category and '石' not in category):
            self._record_skip(cid, 'not jade category', title, category, era_raw)
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'not jade category'}

        # IIIF manifest → 图片
        try:
            manifest = self.get(MANIFEST_TPL.format(cid=cid)).json()
        except requests.RequestException:
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': '网络错误'}
        except ValueError:
            self._record_skip(cid, 'manifest parse error', title, category, era_raw)
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'manifest parse error'}

        candidates: List[str] = []
        for seq in (manifest.get('sequences') or []):
            for canvas in (seq.get('canvases') or []):
                for img in (canvas.get('images') or []):
                    url = (img.get('resource') or {}).get('@id') or ''
                    # /full/,300/ (高300) → /full/1600,/ (宽1600);
                    # 标识符内 %2F 编码已由 manifest 给出, 勿解码
                    if url:
                        candidates.append(
                            re.sub(r'/full/,\d+/', f'/full/{IMG_WIDTH},/', url))
        if not candidates:
            self._record_skip(cid, 'no image', title, category, era_raw)
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}

        # 单组回退链: 首选第一 canvas, 失败依次退备选 (不重复下载多视图)
        groups = [candidates]

        # 时代: 详情 時代 为主, manifest Time 兜底 (两者均为中文朝代名)
        if not fields.get('時代'):
            meta_times = [str(md.get('value') or '') for md in
                          (manifest.get('metadata') or [])
                          if md.get('label') == 'Time']
            if meta_times:
                fields['時代'] = meta_times[0]
                era_raw = ' '.join(x for x in [meta_times[0], title] if x)
        era_result, era_approx = map_npm_era(fields.get('時代', ''), title)
        extra = {
            'title': title or '',
            'material_raw': ' '.join(x for x in [category, title] if x),
            'dimensions_raw': fields.get('尺寸', ''),
            'page_url': detail_url,
            'accession_number': fields.get('文物統一編號', ''),
            'culture': '中国',
            'era_raw': era_raw,
            'license': '低階圖像 CC0 / 中階圖像 CC BY 4.0 (台北故宫開放資料, 需署名)',
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
            'description': fields.get('說明', ''),
            'material': category,
            'dimensions': fields.get('尺寸', ''),
            'source': '台北故宫博物院',
            'image_groups': groups,
            'extra_metadata': extra,
        }
