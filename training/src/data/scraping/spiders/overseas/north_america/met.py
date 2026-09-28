"""
古玉鉴真 — 大都会艺术博物馆爬虫 (Met Collection API)

- 搜索: q=jade&hasImages=true → {total, objectIDs} (一次拿全, 本地切片)
- 详情: /public/collection/v1/objects/{id}
- 版权: 仅下载 isPublicDomain=true 的图片
- 过滤: medium 含 jade 且 culture 含 China
- 图片: primaryImage (过大被拒时回退 primaryImageSmall) + 前 3 张 additionalImages
"""

from typing import Dict, List

from ...api_spider import ApiMuseumSpider


class MetSpider(ApiMuseumSpider):
    """大都会艺术博物馆玉器藏品爬虫。"""

    pagination_mode = "objectIDs"
    # 多查询合并去重: 中文相关词优先, 宽泛 jade 兜底覆盖全部玉器
    queries = ['chinese jade', 'china jade', 'jade']

    def __init__(self, config=None):
        super().__init__(
            name='met',
            museum_name='The Metropolitan Museum of Art',
            museum_name_cn='大都会艺术博物馆',
            base_url='https://collectionapi.metmuseum.org',
            config=config,
        )
        self.search_url_tpl = (self.base_url +
                               '/public/collection/v1/search?q={q}&hasImages=true')
        self.detail_url_tpl = self.base_url + '/public/collection/v1/objects/{id}'

    # ── 数据获取 ──

    def search_raw(self) -> List[dict]:
        seen = set()
        rows = []
        for q in self.queries:
            url = self.search_url_tpl.format(q=q.replace(' ', '%20'))
            data = self.get(url).json()
            ids = data.get('objectIDs') or []
            new = [i for i in ids if i not in seen]
            print(f"[met] q={q!r}: total={data.get('total')}, 新增 {len(new)}")
            for i in new:
                seen.add(i)
                rows.append({'objectID': i})
        print(f"[met] 合并去重后共 {len(rows)} 件")
        return rows

    def fetch_detail(self, item_id: str) -> dict:
        try:
            return self.get(self.detail_url_tpl.format(id=item_id)).json()
        except Exception:
            return {}

    # ── 过滤 ──

    def is_allowed(self, raw: dict) -> bool:
        return bool(raw.get('isPublicDomain'))

    def is_jade(self, raw: dict) -> bool:
        medium = str(raw.get('medium') or '').lower()
        culture = str(raw.get('culture') or '').lower()
        return 'jade' in medium and ('china' in culture)

    # ── 映射 ──

    def map_detail(self, raw: dict) -> Dict:
        iid = str(raw.get('objectID', ''))
        if not raw:
            return {'item_id': iid, 'title': '', 'image_urls': [],
                    'skip_reason': 'API error'}
        if not self.is_allowed(raw):
            return {'item_id': iid, 'title': raw.get('title', ''), 'image_urls': [],
                    'skip_reason': 'not public domain'}
        if not self.is_jade(raw):
            return {'item_id': iid, 'title': raw.get('title', ''), 'image_urls': [],
                    'skip_reason': 'not Chinese jade'}

        era_raw = ' '.join([str(raw.get('objectDate') or ''),
                            str(raw.get('period') or ''),
                            str(raw.get('culture') or '')])
        era_result = self.map_era_common([era_raw])

        # 图片组: [主图, 备选小图] + 各附加图
        groups = []
        primary = raw.get('primaryImage') or ''
        primary_small = raw.get('primaryImageSmall') or ''
        if primary:
            groups.append([primary] + ([primary_small] if primary_small else []))
        for alt in (raw.get('additionalImages') or [])[:3]:
            if alt:
                groups.append([alt])

        page_url = raw.get('objectURL') or (
            f'https://www.metmuseum.org/art/collection/search/{iid}')
        extra = self.build_extra_metadata(
            iid, raw.get('title', ''), era_result,
            raw.get('medium', ''), raw.get('dimensions', ''), page_url)
        extra['accession_number'] = raw.get('accessionNumber', '')
        extra['culture'] = raw.get('culture', '')
        if era_result and len(era_result) > 2 and era_result[2]:
            extra['era_approx'] = True

        return {
            'item_id': iid,
            'title': raw.get('title', ''),
            'era_raw': era_raw,
            'era_mapped': era_result,
            'material': raw.get('medium', ''),
            'dimensions': raw.get('dimensions', ''),
            'image_urls': [u for g in groups for u in g],
            'image_groups': groups,
            'page_url': page_url,
            'extra_metadata': extra,
        }
