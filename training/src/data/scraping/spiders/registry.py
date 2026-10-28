"""
古玉鉴真 — 爬虫注册表

run_spider.py 通过 --spider {id} 查找爬虫类。
新增爬虫后在此登记即可。
"""

from typing import Dict, Type

from .base import BaseJadeSpider
from .overseas.north_america.met import MetSpider
from .overseas.north_america.cleveland import ClevelandSpider
from .overseas.europe.vam import VamSpider
from .overseas.asia_other.tnm import TnmSpider
from .overseas.asia_other.emuseum import EmuseumSpider
from .overseas.asia_other.knmdb import KnmdbSpider
from .domestic.central.gugong import GugongSpider

SPIDERS: Dict[str, Type[BaseJadeSpider]] = {
    'met': MetSpider,
    'cleveland': ClevelandSpider,
    'vam': VamSpider,
    'tnm': TnmSpider,
    'emuseum': EmuseumSpider,
    'knmdb': KnmdbSpider,
    'gugong': GugongSpider,  # 骨架 (需 Playwright, 下轮实现)
}
