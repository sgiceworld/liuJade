"""
古玉鉴真 — 通用 JSON API 博物馆爬虫抽象

面向提供公开藏品 API 的博物馆 (Met / Cleveland / ...)。
子类只需配置搜索端点、分页模式与字段映射, 基类负责:
限速 (BaseJadeSpider 按域名)、版权过滤、去重、断点续传。

分页模式:
- "objectIDs": 一次搜索拿全部 ID, 本地切片 (Met: search 返回 total+objectIDs)
- "offset":    服务端 skip/limit 分页 (Cleveland)
"""

from typing import Dict, List

from .base import BaseJadeSpider, ScraperConfig
from .era_map import map_era, map_material, is_approx_era


class ApiMuseumSpider(BaseJadeSpider):
    """JSON API 博物馆爬虫基类。"""

    # ── 子类配置 ──
    queries: List[str] = ["jade"]                # 搜索词 (可多个)
    pagination_mode = "objectIDs"                # "objectIDs" | "offset"
    page_size = 50                               # offset 模式每页条数
    image_domains: List[str] = []                # 图片 CDN 域名 (仅文档用途, 限速按 host 自动)

    def __init__(self, name, museum_name, museum_name_cn, base_url,
                 config: ScraperConfig = None):
        super().__init__(name, museum_name, museum_name_cn, base_url, config)
        # 详情原始 JSON 缓存 (同 item 多图共享, 避免重复请求)
        self._raw_cache: Dict[str, dict] = {}

    # ── 子类必须实现 ──

    def search_raw(self) -> List[dict]:
        """返回搜索结果的原始条目列表 (每条目是完整记录或 {objectID} 壳)。"""
        raise NotImplementedError

    def fetch_detail(self, item_id: str) -> dict:
        """返回单个藏品的完整原始 JSON。"""
        raise NotImplementedError

    def is_allowed(self, raw: dict) -> bool:
        """版权过滤: 仅开放获取 (isPublicDomain/CC0) 的藏品。"""
        raise NotImplementedError

    def is_jade(self, raw: dict) -> bool:
        """材质过滤: 必须为玉器且中国 (culture 含 China)。"""
        raise NotImplementedError

    def map_detail(self, raw: dict) -> Dict:
        """
        原始 JSON → 标准详情 dict:
            {item_id, title, era_raw, era_mapped, material, dimensions,
             image_urls, page_url, skip_reason, extra_metadata}
        """
        raise NotImplementedError

    # ── 通用流程 ──

    def discover_items(self) -> List[Dict]:
        items = []
        for raw in self.search_raw():
            iid = raw.get('objectID') or raw.get('id')
            if not iid:
                continue
            self._raw_cache[str(iid)] = raw
            items.append({'item_id': str(iid), 'detail_url': str(iid)})
        return items

    def parse_detail(self, detail_url: str) -> Dict:
        raw = self._raw_cache.get(detail_url)
        if raw is None or (self.pagination_mode == 'objectIDs'
                           and not self._is_full_record(raw)):
            raw = self.fetch_detail(detail_url)
            self._raw_cache[detail_url] = raw
        return self.map_detail(raw)

    @staticmethod
    def _is_full_record(raw: dict) -> bool:
        """objectIDs 模式的搜索结果只有 {objectID}, 完整记录需另取。"""
        return 'objectID' not in raw or 'title' in raw or 'primaryImage' in raw

    # ── 公共映射工具 (子类复用) ──

    def map_era_common(self, text_parts: List[str]):
        """拼串 → era 映射 → (era_code, era_name) 或 None; 近似映射返回 (code, name, True)。"""
        text = ' '.join(p for p in text_parts if p)
        result = map_era(text)
        if not result:
            return None
        code, name = result
        if is_approx_era(text):
            return code, name, True
        return code, name, False

    def build_extra_metadata(self, item_id: str, title: str, era_result,
                             material: str, dimensions: str,
                             page_url: str) -> Dict:
        """构造并入图片 metadata.jsonl 行的详情字段。"""
        extra = {
            'title': title or '',
            'material_raw': material or '',
            'dimensions_raw': dimensions or '',
            'page_url': page_url or '',
        }
        if era_result:
            extra['era_mapped_code'] = era_result[0]
            extra['era_mapped_name'] = era_result[1]
            if len(era_result) > 2 and era_result[2]:
                extra['era_approx'] = True
        else:
            extra['era_mapped_code'] = None
            extra['era_mapped_name'] = None
        return extra
