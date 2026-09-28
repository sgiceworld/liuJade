"""
古玉鉴真 — 英文馆藏元数据 → 14 年代/12 材质 映射

海外博物馆 API 的元数据为英文, 映射到项目的 14 年代分类 (A-N)。
顺序敏感: 先长后短、先具体后宽泛。映射结果仅作初稿,
人工审查兜底 (西周/东周近似映射到 C 春秋, notes 会标注)。
"""

import re
from typing import Optional, Tuple

# ── 英文年代 → (era_code, era_name) ──
# 注意: 项目 B=商代、C=春秋, 无西周独立类; western/eastern zhou 近似映射到 C
ERA_MAP_EN = [
    (r'neolithic|hongshan|liangzhu|longshan|qijia|shijiahe|dawenkou|hemudu|'
     r'majiabang|songze|majiayao|xinglongwa|shixia|lingjiatan|yangshao', 'A', '文化期'),
    (r'\bshang\b|yin\s*xu|erlitou|anyang|fu\s*hao', 'B', '商代'),
    (r'spring and autumn|western zhou|eastern zhou|\bzhou dynasty', 'C', '春秋'),
    (r'warring states', 'D', '战国'),
    (r'\bhan dynasty|qin dynasty|western han|eastern han|\bhan\b', 'E', '秦汉'),
    (r'six dynasties|three kingdoms|wei dynasty|northern qi|northern wei|'
     r'jin dynasty.*(?:265|420)|western jin|eastern jin', 'F', '三国两晋南北朝'),
    (r'\btang dynasty', 'G', '唐'),
    (r'\bsong dynasty|northern song|southern song|\bsong\b', 'H', '宋'),
    (r'liao dynasty|khitan|jurchen|jin dynasty|\byuan dynasty|\byuan\b', 'I', '金元'),
    (r'\bming dynasty', 'J', '明'),
    (r'qing dynasty|qianlong|kangxi|yongzheng|jiaqing|daoguang', 'K', '清'),
    (r'republic of china|\b1912\b|republic period', 'L', '民国'),
]


def map_era(text: str) -> Optional[Tuple[str, str]]:
    """英文文本 → (era_code, era_name); 无匹配返回 None (落待OCR确认)。

    西周/东周近似映射到 C 时, 返回值附第 3 项 flag 供 notes 标注。
    为保持签名简单, 近似映射通过 ERA_APPROX 全局集判断。
    """
    if not text:
        return None
    t = text.lower()
    for pattern, code, name in ERA_MAP_EN:
        if re.search(pattern, t):
            return code, name
    return None


def is_approx_era(text: str) -> bool:
    """判断是否西周/东周近似映射 (需人工审查兜底)。"""
    if not text:
        return False
    t = text.lower()
    return bool(re.search(r'western zhou|eastern zhou|\bzhou dynasty', t))


# ── 英文材质 → 项目 12 类材质枚举 ──
MATERIAL_MAP_EN = [
    (r'jadeite', '翡翠（翠玉）'),
    (r'agate|chalcedony', '玛瑙'),
    (r'crystal', '水晶'),
    (r'turquoise', '绿松石'),
    (r'amber', '琥珀'),
    (r'lapis', '青金石'),
    (r'serpentine', '蛇纹石（岫玉）'),
    (r'nephrite|\bjade\b|jadestone', '和田白玉'),
]


def map_material(text: str) -> str:
    """英文材质文本 → 项目材质枚举; 无匹配返回 '和田白玉' 之外的保守值。"""
    if not text:
        return ''
    t = text.lower()
    for pattern, mat in MATERIAL_MAP_EN:
        if re.search(pattern, t):
            return mat
    return '和田白玉'
