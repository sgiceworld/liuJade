"""
古玉鉴真 — 故宫博物院爬虫

技术策略:
- 故宫数字文物库使用 JavaScript 动态加载 → Playwright headless
- 藏品列表通过 XHR API 分页加载
- 高清图需从详情页的 viewer 中提取
"""

import json
from typing import List, Dict
from ..base import BaseJadeSpider, ScraperConfig


class GugongSpider(BaseJadeSpider):
    """故宫博物院玉器藏品爬虫。"""

    def __init__(self, config: ScraperConfig = None):
        super().__init__(
            name='gugong',
            museum_name='The Palace Museum',
            museum_name_cn='故宫博物院',
            base_url='https://www.dpm.org.cn',
            config=config,
        )

    def discover_items(self) -> List[Dict]:
        """
        通过故宫数字文物库 API 发现玉器藏品。

        注意: 故宫 API 需要处理 CSRF token 和动态渲染。
        详细实现需要 Playwright 集成，此处提供骨架。
        """
        items = []

        # TODO: 实际部署时使用 Playwright 驱动
        # 1. 访问 https://www.dpm.org.cn/collection/jade/
        # 2. 等待 JS 渲染完成
        # 3. 拦截 XHR 请求获取藏品列表 API 返回
        # 4. 翻页遍历所有藏品

        # 示例占位: 直接模拟一个藏品条目结构
        search_keywords = ['玉', '玉器', '古玉', '玉雕']
        # 实际 API endpoint (需要反混淆)
        # API: /collection/jade/list?page=1&size=20

        return items

    def parse_detail(self, detail_url: str) -> Dict:
        """
        解析藏品详情页。

        故宫详情页结构:
        - 左侧大图 viewer → 提取高清图 URL
        - 右侧信息栏 → 提取名称、年代、材质、尺寸
        """
        result = {
            'item_id': '',
            'title': '',
            'era': '',
            'description': '',
            'material': '',
            'dimensions': '',
            'source': '故宫博物院',
            'image_urls': [],
        }

        # TODO: Playwright 解析详情页

        return result
