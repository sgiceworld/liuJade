"""
古玉鉴真 — 爬虫注册表

run_spider.py 通过 --spider {id} 查找爬虫类。
新增爬虫后在此登记即可。
"""

from typing import Dict, Type

from .base import BaseJadeSpider
from .overseas.north_america.met import MetSpider
from .overseas.north_america.cleveland import ClevelandSpider
from .domestic.central.gugong import GugongSpider

SPIDERS: Dict[str, Type[BaseJadeSpider]] = {
    'met': MetSpider,
    'cleveland': ClevelandSpider,
    'gugong': GugongSpider,  # 骨架 (需 Playwright, 下轮实现)
}
