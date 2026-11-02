"""
古玉鉴真 — ColBase (国立文化財機構 統合検索) 爬虫

- API: colbaseapi/v2/collection_items (x-api-key: aaa, Nuxt SPA 前端同款,
  2026-11-02 从 JS bundle 挖出; 参数 schema 见 sites.json colbase 条目)
- 查询轴: hinshitu_keijo (材质形状, 子串匹配) × 8 关键词
  [玉, 翡翠, 瑪瑙, 玉髄, 水晶, 琥珀, トルコ石, ラピスラズリ] × with_image_file=1
  (玉 469 / 翡翠 37 / 瑪瑙 32 / 玉髄 3 / 水晶 62 / 琥珀 14 / トルコ石 3 / ラピス 1)
- 列表响应即完整记录 (与详情同字段) → parse_detail 零额外请求
- 中国过滤 (列表级, 逐件留档 skip_log.jsonl):
  bunrui 東洋* (東洋陶磁/東洋考古/東洋書跡) 或 出土地含中国 或
  時代/标题命中中国时代词; 排除日/韩时代词 (縄文/弥生/古墳/奈良/平安/
  鎌倉/室町/江戸/明治 + 新羅/高麗/李朝/朝鮮) 与 玉眼佛像 (材質含 玉眼)
- 图片: thumbnail_url 去掉 /thumbnail/ 得原图 (实测 3.5MB, 328px → 高清)
- 限速: 基类 3-8s 延时 + 500 请求/天/域名
"""

import json
import re
import urllib.parse
from datetime import datetime
from typing import Dict, List

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

COLBASE_BASE = 'https://colbase.nich.go.jp'
API = COLBASE_BASE + '/colbaseapi/v2/collection_items'
PAGE_SIZE = 100

# 材质关键词轴 (日文汉字形; hinshitu_keijo 子串匹配:
# 玉 命中 玉/玉製/硬玉/碧玉)
MATERIAL_KWS = ['玉', '翡翠', '瑪瑙', '玉髄', '水晶', '琥珀', 'トルコ石',
                'ラピスラズリ']

# 中国时代标记 (日文汉字形)
CN_ERA_RE = re.compile(
    r'新石器|龍山|龙山|良渚|紅山|红山|仰韶|馬家|大汶口|河姆渡|石家河|興隆窪|'
    r'裴李崗|凌家灘|石峽|齊家|殷墟|殷(?:代|朝|後|時)|商(?:代|朝|時)|二里[裏头]頭|'
    r'周(?:代|朝|時)|春秋|戦国|戰國|战国|秦|漢|汉|三国|三國|魏|晋|晉|南北朝|'
    r'六朝|隋|唐(?:代|朝|時|三彩)|宋(?:代|朝|時)|遼|辽|金(?:代|朝)|元(?:代|朝)|'
    r'明(?:代|朝|時)|清(?:代|朝|時)|民国|民國')
# 日本时代标记 (排除)
JP_ERA_RE = re.compile(
    r'縄文|绳文|弥生|彌生|古墳|飛鳥|奈良|平安|鎌倉|室町|桃山|江戸|江户|'
    r'明治|大正|昭和|琉球|沖縄|アイヌ')
# 朝鲜半岛时代标记 (排除)
KR_ERA_RE = re.compile(
    r'新羅|高麗|高句麗|百済|百濟|李朝|朝鮮|伽耶|楽浪')


def _is_chinese(item: Dict) -> bool:
    """列表级中国过滤: bunrui/出土地/时代/标题 联合判定。

    排除: 日韩时代词、玉眼佛像 (木雕 玉眼 属日本雕塑)、
    東洋民族 (民族资料)。
    """
    bunrui = item.get('bunrui') or ''
    shutudochi = item.get('shutudochi') or ''
    jidai = item.get('jidai_seiki') or ''
    title = item.get('title') or ''
    material = item.get('hinshitu_keijo') or ''

    # 玉眼佛像: 主材质为木, 玉眼只是镶嵌 → 非玉器
    if '玉眼' in material:
        return False
    if bunrui == '東洋民族':
        return False

    era_text = ' '.join(x for x in (jidai, title) if x)
    if JP_ERA_RE.search(era_text) or KR_ERA_RE.search(era_text):
        return False
    if shutudochi and '中国' in shutudochi:
        return True
    if bunrui.startswith('東洋'):
        return True
    # 无分类/日本大类 (考古/彫刻/陶磁/漆工/法隆寺宝物/民族資料):
    # 时代或标题有中国标记才算
    return bool(CN_ERA_RE.search(era_text))


class ColbaseSpider(BaseJadeSpider):
    """ColBase 統合検索爬虫 (材质关键词轴 + 列表级中国过滤)。"""

    def __init__(self, config=None):
        super().__init__(
            name='colbase',
            museum_name='ColBase (National Institutes for Cultural Heritage)',
            museum_name_cn='文化遺産オンライン ColBase',
            base_url=COLBASE_BASE,
            config=config,
        )
        self.session.headers.update({'x-api-key': 'aaa'})
        self._list_rows: Dict[str, dict] = {}  # key: organization_item_key → 列表行

    # ── 发现 ──

    def _fetch_axis(self, kw: str) -> List[dict]:
        """单个材质关键词轴: 翻页收集全部行 (limit=100)。"""
        rows = []
        page = 1
        while True:
            qs = urllib.parse.urlencode({
                'locale': 'ja', 'page': page, 'limit': PAGE_SIZE,
                'hinshitu_keijo': kw, 'with_image_file': 1,
            })
            data = self.get(f'{API}?{qs}').json()
            batch = data.get('results') or []
            rs = data.get('resultset') or {}
            rows.extend(batch)
            print(f"[colbase] 轴 '{kw}': page={page} +{len(batch)} "
                  f"(total {rs.get('count')})")
            if not batch or page * PAGE_SIZE >= (rs.get('count') or 0):
                break
            page += 1
        return rows

    def discover_items(self) -> List[Dict]:
        seen = set()
        items = []
        for kw in MATERIAL_KWS:
            for row in self._fetch_axis(kw):
                iid = str(row.get('organization_item_key') or row.get('id') or '')
                if not iid or iid in seen:
                    continue
                seen.add(iid)
                self._list_rows[iid] = row
                items.append({'item_id': iid, 'detail_url': iid,
                              'list_row': row})
        print(f"[colbase] 8 轴去重后共 {len(items)} 件候选")
        return items

    # ── 详情 (列表行即完整记录, 零额外请求) ──

    def _record_skip(self, item_id: str, reason: str, title: str,
                     material: str, bunrui: str, jidai: str, shutudochi: str):
        """跳过诊断日志: 逐件留档被拒项 (负结果复核证据, 同 knmdb)。"""
        with open(self.output_dir / 'skip_log.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'item_id': item_id,
                'reason': reason,
                'title': title,
                'material': material,
                'bunrui': bunrui,
                'jidai_seiki': jidai,
                'shutudochi': shutudochi,
                'logged_at': datetime.now().isoformat(),
            }, ensure_ascii=False) + '\n')
            f.flush()

    def parse_detail(self, detail_url: str) -> Dict:
        row = self._list_rows.get(detail_url, {})
        if not row:
            return {'item_id': detail_url, 'title': '', 'image_urls': [],
                    'skip_reason': 'API error'}
        title = row.get('title') or ''
        material = row.get('hinshitu_keijo') or ''
        bunrui = row.get('bunrui') or ''
        jidai = row.get('jidai_seiki') or ''
        shutudochi = row.get('shutudochi') or ''

        # 材质兜底: 关键词轴保证命中, 但复核映射 (排除误伤)
        if not map_material_zh(material):
            self._record_skip(detail_url, 'not Chinese jade', title,
                              material, bunrui, jidai, shutudochi)
            return {'item_id': detail_url, 'title': title, 'image_urls': [],
                    'skip_reason': 'not Chinese jade'}
        if not _is_chinese(row):
            self._record_skip(detail_url, 'not Chinese jade', title,
                              material, bunrui, jidai, shutudochi)
            return {'item_id': detail_url, 'title': title, 'image_urls': [],
                    'skip_reason': 'not Chinese jade'}

        # 大图: 缩略图 URL 去掉 /thumbnail/ 即原图
        thumb = row.get('thumbnail_url') or ''
        img_urls = [thumb.replace('/thumbnail/', '/')] if thumb else []
        if not img_urls:
            self._record_skip(detail_url, 'no image', title,
                              material, bunrui, jidai, shutudochi)
            return {'item_id': detail_url, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}

        org_path = row.get('organization_path_name') or ''
        page_url = (f'{COLBASE_BASE}/collection_items/{org_path}/{detail_url}'
                    if org_path else COLBASE_BASE)
        era_raw = ' '.join(x for x in (jidai, title) if x)
        era_result = map_era_zh(era_raw)
        extra = {
            'title': title,
            'material_raw': material,
            'dimensions_raw': row.get('houryo') or '',
            'page_url': page_url,
            'accession_number': detail_url,
            'culture': bunrui,
            'era_raw': era_raw,
            'classification': bunrui,
            'designation': row.get('bunkazai') or '',
            'collection': row.get('collection_title') or '',
            'institution': row.get('organization_title') or '',
            'donor': row.get('kizousha') or '',
            'license': 'ColBase 統合検索公開画像 (研究用途)',
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
            'item_id': detail_url,
            'title': title,
            'era': era_raw,
            'material': material,
            'dimensions': row.get('houryo') or '',
            'source': 'ColBase 文化遺産オンライン',
            'image_groups': [[u] for u in img_urls],
            'extra_metadata': extra,
        }
