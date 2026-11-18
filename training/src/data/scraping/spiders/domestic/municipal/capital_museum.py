"""
古玉鉴真 — 首都博物馆 (capital_museum) 爬虫

- 站点为 Nuxt SPA, 藏品列表走客户端 API (2026-11-18 Playwright 抓 XHR 挖出,
  证据 scraped_data/_capital_probe/playwright_capture/):
  GET https://m.canalmuseum.org.cn/mmodule/sbdg.cms/ajax/website/collectionList
      ?page=N&classid={32位hex}&pagesize=M
- 全站仅「馆藏精品」精选 ~55 件, 9 分类 (2026-11-18 实测 total):
  陶瓷器14 金银器15 绘画12 书法2 文玩1 佛造像2 织绣4 玉器4 钱币1
- 玉器 classid=4b670c7ab9094c179c22ac062c079eb6 (4 件, 全收);
  文玩 classid=3e5d2fd3337f4047962e7cdbcb1b58b9 (1 件, 玉质关键词过滤)
- 列表响应即完整记录 (name/dynasty/detail_age/summary/detail_specification/
  imgurl 750x960/colladdress) → parse_detail 零额外请求
- 详情页 /collection/{cid} SSR 静态 (字段与列表 API 相同, 无增量信息)
- 图片: imgurl 带 ?750x960 尺寸后缀 (实测可用); 去后缀裸 URL 作组内回退
- 网络: 国内站点直连 (不走 Clash); API 域对连发敏感
  (2026-11-18 探测时 9 连发触发 ConnectionReset 10054 临时限流),
  已守基类 3-8s 延时, 连接错误靠基类重试 + 组内回退
- item_id 前缀 cm_: 馆方 cid 为 32 位 hex, 与库内数字 ID 无碰撞风险
- robots.txt: 404 (无声明)
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional

import requests

from ...base import BaseJadeSpider
from ...era_map import map_era_zh, is_approx_era_zh, map_material_zh

SITE_BASE = 'https://www.capitalmuseum.org.cn'
API_BASE = 'https://m.canalmuseum.org.cn'
LIST_API = API_BASE + '/mmodule/sbdg.cms/ajax/website/collectionList'
PAGE_SIZE = 50

# (分类名, classid hash) — 玉器全收; 文玩需玉质关键词过滤 (2026-11-18 实测)
CATEGORY_AXES = [
    ('玉器', '4b670c7ab9094c179c22ac062c079eb6'),
    ('文玩', '3e5d2fd3337f4047962e7cdbcb1b58b9'),
]

# 文玩类目玉质判定关键词 (材质 + 器形, 参照 knmdb/senoku 复核词表)
JADE_KW_RE = re.compile(
    r'玉|翡翠|玛瑙|瑪瑙|碧玉|青金|琥珀|水晶|璧|琮|圭|璜|玦|珑|玲|瑗|環|珏')

# 石雕类排除 (2026-11-18 实测): 玉器类目混入「石雕麒麟纹栏板」(元代),
# 标题为石雕、summary 无任何玉质词 — 石质栏板误入, 参照青铜嵌石教训不收入
STONE_TITLE_RE = re.compile(r'石雕|石刻|栏板|石栏')
JADE_MATERIAL_RE = re.compile(
    r'玉质|玉製|白玉|青玉|碧玉|青白玉|翡翠|玛瑙|瑪瑙|和田|岫玉|独山|玉器|玉带')

# npm 教训: 详情时代字段带「西元」纪年注记时, 「元」字会被金元模式误配。
# 映射前剥掉西元纪年 (capital_museum detail_age 形如 金代（1115-1234）)
XINIAN_RE = re.compile(r'[（(]?西元[^）)]*[）)]?|公元[^）)]*[）)]?')


def _clean_era_text(*parts: str) -> str:
    return XINIAN_RE.sub('', ' '.join(x for x in parts if x)).strip()


class CapitalMuseumSpider(BaseJadeSpider):
    """首都博物馆玉器藏品爬虫 (Nuxt SPA 客户端 API)。"""

    def __init__(self, config=None):
        super().__init__(
            name='capital_museum',
            museum_name='Capital Museum',
            museum_name_cn='首都博物馆',
            base_url=SITE_BASE,
            config=config,
        )
        self._records: Dict[str, Dict] = {}

    # ── 发现 ──

    def _fetch_list(self, classid: str, page: int) -> Optional[Dict]:
        try:
            resp = self.get(LIST_API, params={
                'page': page, 'classid': classid, 'pagesize': PAGE_SIZE,
            })
            data = resp.json()
        except requests.RequestException:
            return None
        except ValueError:
            return None
        if data.get('code') != 'A00006':
            return None
        return data

    def discover_items(self) -> List[Dict]:
        items: List[Dict] = []
        for cat, classid in CATEGORY_AXES:
            first = self._fetch_list(classid, 1)
            if first is None:
                print(f"[capital_museum] 分类 {cat} 首页请求失败, 本轮跳过")
                continue
            pageinfo = first.get('page') or {}
            total = pageinfo.get('total', 0)
            pagecount = max(1, int(pageinfo.get('pagecount', 1) or 1))
            print(f"[capital_museum] 分类 {cat}: total={total} pagecount={pagecount}")
            records: List[Dict] = list(first.get('collectionlist') or [])
            for p in range(2, pagecount + 1):
                data = self._fetch_list(classid, p)
                if data is None:
                    print(f"[capital_museum] 分类 {cat} 第 {p} 页失败, "
                          f"本轮收尾该分类 (下轮补)")
                    break
                records.extend(data.get('collectionlist') or [])
            for rec in records:
                cid = rec.get('cid') or ''
                if not cid:
                    continue
                item_id = f'cm_{cid}'
                rec['_category'] = cat
                self._records[item_id] = rec
                items.append({
                    'item_id': item_id,
                    'title': rec.get('name') or '',
                    'era': _clean_era_text(rec.get('dynasty', ''),
                                           rec.get('detail_age', '')),
                    'detail_url': f'{SITE_BASE}/collection/{cid}',
                })
        return items

    # ── 详情 (列表响应即完整记录, 零额外请求) ──

    def _record_skip(self, item_id: str, reason: str, title: str,
                     category: str, era: str):
        """跳过诊断日志: 逐件留档被拒项 (负结果复核证据)。"""
        with open(self.output_dir / 'skip_log.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'item_id': item_id,
                'reason': reason,
                'title': title,
                'category': category,
                'era': era,
                'logged_at': datetime.now().isoformat(),
            }, ensure_ascii=False) + '\n')
            f.flush()

    def parse_detail(self, detail_url: str) -> Dict:
        cid = re.search(r'/collection/([0-9a-f]{32})', detail_url or '')
        item_id = f'cm_{cid.group(1)}' if cid else ''
        rec = self._records.get(item_id)
        if rec is None:
            return {'item_id': item_id, 'title': '', 'image_urls': [],
                    'skip_reason': '网络错误'}

        title = rec.get('name') or ''
        category = rec.get('_category') or ''
        era_raw = _clean_era_text(rec.get('dynasty', ''),
                                  rec.get('detail_age', ''))

        summary = rec.get('summary') or ''
        # 文玩类目玉质过滤: 非玉件终态留档 (玉器类目信任馆方分类)
        if category != '玉器' and not JADE_KW_RE.search(title + ' ' + summary):
            self._record_skip(item_id, 'not jade (文玩类目)', title, category,
                              era_raw)
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'not jade'}
        # 石雕类排除 (即使馆方归入玉器类目): 标题石雕/栏板且
        # summary 无玉质词 → 石质误入, 终态留档
        if (STONE_TITLE_RE.search(title) and
                not JADE_MATERIAL_RE.search(summary)):
            self._record_skip(item_id, 'not jade (石雕误入玉器类目)', title,
                              category, era_raw)
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'not jade'}

        imgurl = rec.get('imgurl') or ''
        if not imgurl:
            self._record_skip(item_id, 'no image', title, category, era_raw)
            return {'item_id': item_id, 'title': title, 'image_urls': [],
                    'skip_reason': 'no image'}
        # 组内回退: 带 ?750x960 后缀 (实测可用) → 裸 URL (可能原图)
        bare = imgurl.split('?')[0]
        groups: List[List[str]] = [[imgurl, bare] if bare != imgurl
                                   else [imgurl]]

        era_result, era_approx = map_era_zh(era_raw), False
        if era_result:
            era_approx = is_approx_era_zh(era_raw)
        material_raw = ' '.join(x for x in [category, title] if x)
        extra = {
            'title': title,
            'material_raw': material_raw,
            'dimensions_raw': rec.get('detail_specification', '') or '',
            'page_url': detail_url or '',
            'accession_number': '',
            'culture': '中国',
            'era_raw': era_raw,
            'location': rec.get('colladdress', '') or '',
            'license': '首都博物馆官网图片 (未声明授权条款, 学术研究使用)',
        }
        if era_result:
            extra['era_mapped_code'] = era_result[0]
            extra['era_mapped_name'] = era_result[1]
            if era_approx:
                extra['era_approx'] = True
        else:
            extra['era_mapped_code'] = None
            extra['era_mapped_name'] = None

        desc_parts = [p for p in (rec.get('summary'), rec.get('detail_outward'))
                      if p and p != rec.get('summary')]
        description = '\n'.join(x for x in
                                ([rec.get('summary') or ''] + desc_parts) if x)
        return {
            'item_id': item_id,
            'title': title,
            'era': era_raw,
            'description': description,
            'material': map_material_zh(material_raw),
            'dimensions': rec.get('detail_specification', '') or '',
            'source': '首都博物馆',
            'image_groups': groups,
            'extra_metadata': extra,
        }
