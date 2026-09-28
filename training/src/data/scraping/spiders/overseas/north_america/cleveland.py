"""
古玉鉴真 — 克利夫兰艺术博物馆爬虫 (Cleveland Open Access API)

- 搜索: api/artworks?q=jade&type=Jade&cc0=1&has_image=1&skip={n}&limit=50
- 搜索结果已含完整记录 → parse_detail 零额外请求
- 版权: 搜索已带 cc0=1, is_allowed 双保险
- 图片: images.print.url (高清) 优先, images.web.url 兜底 + 前 3 张 alternate
"""

from typing import Dict, List

from ...api_spider import ApiMuseumSpider


class ClevelandSpider(ApiMuseumSpider):
    """克利夫兰艺术博物馆玉器藏品爬虫。"""

    pagination_mode = "offset"
    page_size = 50

    def __init__(self, config=None):
        super().__init__(
            name='cleveland',
            museum_name='The Cleveland Museum of Art',
            museum_name_cn='克利夫兰艺术博物馆',
            base_url='https://openaccess-api.clevelandart.org',
            config=config,
        )
        self.search_url_tpl = (
            self.base_url + '/api/artworks?q=jade&type=Jade&cc0=1&has_image=1'
            '&skip={skip}&limit={limit}')

    # ── 数据获取 ──

    def search_raw(self) -> List[dict]:
        rows = []
        skip = 0
        total = None
        while total is None or skip < total:
            url = self.search_url_tpl.format(skip=skip, limit=self.page_size)
            data = self.get(url).json()
            info = data.get('info', {})
            total = total if total is not None else info.get('total', 0)
            batch = data.get('data') or []
            rows.extend(batch)
            print(f"[cleveland] fetched {skip + len(batch)}/{total}")
            if not batch:
                break
            skip += len(batch)
        return rows

    def fetch_detail(self, item_id: str) -> dict:
        # 搜索结果已含完整记录; 兜底单独取
        try:
            data = self.get(
                f'{self.base_url}/api/artworks/{item_id}').json()
            return data.get('data') or {}
        except Exception:
            return {}

    # ── 过滤 ──

    def is_allowed(self, raw: dict) -> bool:
        return str(raw.get('share_license_status') or '').upper() == 'CC0'

    def is_jade(self, raw: dict) -> bool:
        type_f = str(raw.get('type') or '').lower()
        culture = str(raw.get('culture') or '').lower()
        medium = str(raw.get('medium') or '').lower()
        return ('jade' in type_f or 'jade' in medium) and 'china' in culture

    # ── 映射 ──

    @staticmethod
    def _extract_image_urls(raw: dict) -> List[str]:
        """print 高清优先, web 兜底; alternate 各取 web。"""
        urls = []
        images = raw.get('images') or {}
        print_url = (images.get('print') or {}).get('url') or ''
        web_url = (images.get('web') or {}).get('url') or ''
        if print_url:
            urls.append(print_url)
        elif web_url:
            urls.append(web_url)
        for alt in (raw.get('alternate_images') or [])[:3]:
            alt_print = (alt.get('print') or {}).get('url') or ''
            alt_web = (alt.get('web') or {}).get('url') or ''
            if alt_print:
                urls.append(alt_print)
            elif alt_web:
                urls.append(alt_web)
        return urls

    def map_detail(self, raw: dict) -> Dict:
        iid = str(raw.get('id', ''))
        if not raw:
            return {'item_id': iid, 'title': '', 'image_urls': [],
                    'skip_reason': 'API error'}
        if not self.is_allowed(raw):
            return {'item_id': iid, 'title': raw.get('title', ''), 'image_urls': [],
                    'skip_reason': 'not CC0'}
        if not self.is_jade(raw):
            return {'item_id': iid, 'title': raw.get('title', ''), 'image_urls': [],
                    'skip_reason': 'not Chinese jade'}

        era_raw = ' '.join([str(raw.get('creation_date') or ''),
                            str(raw.get('culture') or '')])
        era_result = self.map_era_common([era_raw])

        urls = self._extract_image_urls(raw)
        page_url = f'https://www.clevelandart.org/art/{iid}'
        extra = self.build_extra_metadata(
            iid, raw.get('title', ''), era_result,
            raw.get('medium', ''), raw.get('technique', ''), page_url)
        extra['accession_number'] = raw.get('accession_number', '')
        extra['culture'] = raw.get('culture', '')
        if era_result and len(era_result) > 2 and era_result[2]:
            extra['era_approx'] = True

        return {
            'item_id': iid,
            'title': raw.get('title', ''),
            'era_raw': era_raw,
            'era_mapped': era_result,
            'material': raw.get('medium', ''),
            'dimensions': raw.get('technique', ''),
            'image_urls': urls,
            'image_groups': [[u] for u in urls],
            'page_url': page_url,
            'extra_metadata': extra,
        }
