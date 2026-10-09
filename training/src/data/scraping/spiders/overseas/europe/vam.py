"""
古玉鉴真 — 维多利亚与阿尔伯特博物馆爬虫 (V&A Collections API v2)

- 搜索: /v2/objects/search?q=jade&page_size=100&page={n} (17 页, 1622 条)
- 搜索结果含 _primaryPlace/_primaryImageId, 材质/尺寸需按件取详情
  /v2/museumobject/{systemNumber} → parse_detail 合并两层数据
- 版权: V&A 图片条款 (非商用+署名), API 无 license 字段, notes 标注
- 图片: framemark IIIF 高清 (full) 优先, !1024 中图兜底
"""

from typing import Dict, List

from ...api_spider import ApiMuseumSpider


class VamSpider(ApiMuseumSpider):
    """维多利亚与阿尔伯特博物馆玉器藏品爬虫。"""

    # objectIDs 模式: 强制按件取详情 (搜索记录不含材质/尺寸)
    pagination_mode = "objectIDs"
    page_size = 100

    def __init__(self, config=None):
        super().__init__(
            name='vam',
            museum_name='Victoria and Albert Museum',
            museum_name_cn='维多利亚与阿尔伯特博物馆',
            base_url='https://api.vam.ac.uk',
            config=config,
        )
        self.search_url = (self.base_url +
                           '/v2/objects/search?q=jade&page_size=100')

    # ── 数据获取 ──

    def search_raw(self) -> List[dict]:
        rows = []
        page = 1
        total = None
        while total is None or len(rows) < total:
            url = f'{self.search_url}&page={page}'
            data = self.get(url).json()
            info = data.get('info', {})
            total = total if total is not None else info.get('record_count', 0)
            batch = data.get('records') or []
            rows.extend(batch)
            print(f"[vam] page {page}: {len(rows)}/{total}")
            if not batch:
                break
            page += 1
        return rows

    def discover_items(self) -> List[Dict]:
        """按 systemNumber 建立条目 (ApiMuseumSpider 默认键为 objectID/id)。"""
        items = []
        for raw in self.search_raw():
            sid = str(raw.get('systemNumber') or '')
            if not sid:
                continue
            self._raw_cache[sid] = raw
            items.append({'item_id': sid, 'detail_url': sid})
        return items

    def fetch_detail(self, item_id: str) -> dict:
        try:
            data = self.get(
                f'{self.base_url}/v2/museumobject/{item_id}').json()
            return data.get('record') or {}
        except Exception:
            return {}

    def parse_detail(self, detail_url: str) -> Dict:
        """详情记录与搜索记录合并: 详情含材质/尺寸, 搜索含产地/主图 id。

        搜索记录已含 _primaryPlace → 非中国产地直接跳过, 省一次详情请求。
        """
        search_raw = self._raw_cache.get(detail_url) or {}
        if not self.is_jade(search_raw):
            return self.map_detail(search_raw)
        detail = self.fetch_detail(detail_url) or {}
        if not detail:
            # 详情拉取失败 → 不标记已处理, 下次续跑重试
            return {'item_id': str(search_raw.get('systemNumber') or ''),
                    'title': '', 'image_urls': [], 'skip_reason': 'API error'}
        merged = dict(detail)
        merged['_primaryPlace'] = search_raw.get('_primaryPlace') or ''
        merged['_primaryImageId'] = search_raw.get('_primaryImageId') or ''
        merged['_search_images'] = search_raw.get('_images') or {}
        return self.map_detail(merged)

    # ── 过滤 ──

    def is_allowed(self, raw: dict) -> bool:
        # V&A API 无 license 字段; 条款 (非商用+署名) 记入 notes
        return True

    def is_jade(self, raw: dict) -> bool:
        place = str(raw.get('_primaryPlace') or '').lower()
        return 'china' in place

    # ── 映射 ──

    @staticmethod
    def _extract_image_urls(raw: dict) -> List[List[str]]:
        """主图高清 (full) + 中图兜底 (!1024), 返回 [[url, url]] 组。"""
        img_id = raw.get('_primaryImageId') or ''
        if img_id:
            full = (f'https://framemark.vam.ac.uk/collections/{img_id}'
                    f'/full/full/0/default.jpg')
            mid = (f'https://framemark.vam.ac.uk/collections/{img_id}'
                   f'/full/!1024,1024/0/default.jpg')
            return [[full, mid]]
        thumb = (raw.get('_search_images') or {}).get('_primary_thumbnail') or ''
        if thumb:
            full = thumb.replace('!100,100', 'full')
            return [[full, thumb]]
        return []

    @staticmethod
    def _places_text(raw: dict) -> str:
        # placesOfOrigin 条目形状不一: dict / {'place': dict} / 纯字符串
        parts = []
        for p in raw.get('placesOfOrigin') or []:
            if isinstance(p, str):
                parts.append(p)
                continue
            if not isinstance(p, dict):
                continue
            inner = p.get('place') if isinstance(p.get('place'), dict) else p
            if isinstance(inner, dict):
                parts.append(str(inner.get('text') or inner.get('name') or ''))
        return ' '.join(x for x in parts if x)

    @staticmethod
    def _first_title(raw: dict) -> str:
        # titles 元素可能为 {'title': ...} 或纯字符串
        for t in raw.get('titles') or []:
            if isinstance(t, dict):
                v = t.get('title')
                if v:
                    return str(v)
            elif isinstance(t, str) and t:
                return t
        return ''

    @staticmethod
    def _first_date_text(raw: dict) -> str:
        for pd in raw.get('productionDates') or []:
            if isinstance(pd, str):
                return pd
            if not isinstance(pd, dict):
                continue
            d = pd.get('date')
            if isinstance(d, dict):
                if d.get('text'):
                    return str(d['text'])
            elif d:
                return str(d)
        return ''

    def map_detail(self, raw: dict) -> Dict:
        sid = str(raw.get('systemNumber') or '')
        if not raw:
            return {'item_id': sid, 'title': '', 'image_urls': [],
                    'skip_reason': 'API error'}
        if not self.is_jade(raw):
            return {'item_id': sid, 'title': '', 'image_urls': [],
                    'skip_reason': 'not Chinese jade'}

        date_text = self._first_date_text(raw)
        places = self._places_text(raw)
        title = self._first_title(raw)
        era_raw = ' '.join(x for x in [date_text, places, title or ''] if x)
        era_result = self.map_era_common([era_raw])

        groups = self._extract_image_urls(raw)
        materials = str(raw.get('materials') or '')
        if not materials:
            materials = '; '.join(
                str(m.get('text') or '')
                for m in (raw.get('materialsAndTechniques') or [])
                if isinstance(m, dict))
        dims = '; '.join(
            f"{d.get('dimension', '')} {d.get('value', '')} {d.get('unit', '')}".strip()
            for d in (raw.get('dimensions') or [])[:5]
            if isinstance(d, dict))

        page_url = f'https://collections.vam.ac.uk/item/{sid}/'
        extra = self.build_extra_metadata(
            sid, title or '', era_result, materials, dims, page_url)
        extra['accession_number'] = raw.get('accessionNumber') or ''
        extra['culture'] = places
        extra['license'] = 'V&A terms (non-commercial, attribution)'
        if era_result and len(era_result) > 2 and era_result[2]:
            extra['era_approx'] = True

        return {
            'item_id': sid,
            'title': title or '',
            'era_raw': era_raw,
            'era_mapped': era_result,
            'material': materials,
            'dimensions': dims,
            'image_urls': [u for g in groups for u in g],
            'image_groups': groups,
            'page_url': page_url,
            'extra_metadata': extra,
        }
