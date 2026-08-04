"""古玉鉴真 — 博物馆爬虫模块

88个目标站点，分优先级别爬取:
  P0: 故宫、国博、台北故宫、南博、上博 + 图书资源
  P1: 省级博物馆 (34家) + 重点市级馆
  P2: 其他市级馆 + 北美博物馆
  P3: 欧洲、亚洲其他博物馆
"""

from .spiders.base import BaseJadeSpider, ScraperConfig

__all__ = [
    "BaseJadeSpider",
    "ScraperConfig",
]
