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
from .overseas.asia_other.colbase import ColbaseSpider
from .overseas.asia_other.npm import NpmSpider
from .domestic.central.gugong import GugongSpider
from .domestic.central.guobo import GuoboSpider
from .domestic.municipal.capital_museum import CapitalMuseumSpider
from .domestic.municipal.yin_ruins import YinRuinsSpider
from .domestic.municipal.chongqing import ChongqingSpider
from .domestic.municipal.liangzhu import LiangzhuSpider
from .domestic.provincial.henan import HenanSpider
from .domestic.provincial.hunan import HunanSpider
from .domestic.provincial.shandong import ShandongSpider
from .domestic.provincial.shaanxi import ShaanxiSpider
from .domestic.provincial.shanxi import ShanxiSpider
from .domestic.provincial.liaoning import LiaoningSpider
from .domestic.provincial.guangdong import GuangdongSpider
from .domestic.provincial.sanxingdui import SanxingduiSpider
from .domestic.provincial.gansu import GansuSpider
from .domestic.provincial.hebei import HebeiSpider
from .domestic.provincial.shanghai import ShanghaiSpider
from .domestic.provincial.zhejiang import ZhejiangSpider

SPIDERS: Dict[str, Type[BaseJadeSpider]] = {
    'met': MetSpider,
    'cleveland': ClevelandSpider,
    'vam': VamSpider,
    'tnm': TnmSpider,
    'emuseum': EmuseumSpider,
    'knmdb': KnmdbSpider,
    'colbase': ColbaseSpider,
    'npm': NpmSpider,
    'gugong': GugongSpider,  # 骨架 (需 Playwright, 下轮实现)
    'guobo': GuoboSpider,
    'capital_museum': CapitalMuseumSpider,
    'yin_ruins': YinRuinsSpider,
    'chongqing': ChongqingSpider,
    'liangzhu': LiangzhuSpider,
    'henan': HenanSpider,
    'hunan': HunanSpider,
    'shandong': ShandongSpider,
    'shaanxi': ShaanxiSpider,
    'shanxi': ShanxiSpider,
    'liaoning': LiaoningSpider,
    'guangdong': GuangdongSpider,
    'sanxingdui': SanxingduiSpider,
    'gansu': GansuSpider,
    'hebei': HebeiSpider,
    'shanghai': ShanghaiSpider,
    'zhejiang': ZhejiangSpider,
}
