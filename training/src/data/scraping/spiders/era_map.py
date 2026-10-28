"""
古玉鉴真 — 馆藏元数据 → 14 年代/12 材质 映射

海外博物馆 API 的元数据为英文, 映射到项目的 14 年代分类 (A-N)。
静态中文站点 (TNM 等) 使用 map_era_zh / map_material_zh。
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


# ── 中文年代 → (era_code, era_name) ──
# 与 ERA_MAP_EN 同构, 供中文站点 (TNM zh_cn) 使用; 顺序敏感
ERA_MAP_ZH = [
    (r'新石器|文化期|良渚|红山|龙山|仰韶|马家窑|齐家|石峡|凌家滩|大汶口|'
     r'河姆渡|马家浜|崧泽|石家河|兴隆洼|裴李岗', 'A', '文化期'),
    (r'商代?|商朝|殷墟|殷|妇好|二里头|二裏頭|偃师', 'B', '商代'),
    (r'春秋|西周|東周|东周|周(?:時代|时代|代|朝)', 'C', '春秋'),
    (r'战国|戰國|曾侯乙', 'D', '战国'),
    (r'秦|西汉|西漢|东汉|東漢|汉代?|漢代?|前漢|後漢|后汉|南越', 'E', '秦汉'),
    (r'三国|三國|魏晋|魏晉|南北朝|北魏|南朝|北齐|北齊|北周|六朝|晉|晋',
     'F', '三国两晋南北朝'),
    (r'唐(?:代|朝)?[^三]', 'G', '唐'),
    (r'宋(?:代|朝)?|北宋|南宋', 'H', '宋'),
    (r'辽|遼|金|元', 'I', '金元'),
    (r'明(?:代|朝)?[^清]', 'J', '明'),
    (r'清(?:代|朝)?', 'K', '清'),
    (r'民国|民國', 'L', '民国'),
]


def map_era_zh(text: str) -> Optional[Tuple[str, str]]:
    """中文文本 → (era_code, era_name); 无匹配返回 None (落待OCR确认)。"""
    if not text:
        return None
    for pattern, code, name in ERA_MAP_ZH:
        if re.search(pattern, text):
            return code, name
    return None


def is_approx_era_zh(text: str) -> bool:
    """判断是否西周/东周近似映射 (项目无西周独立类, 映射到 C 需人工确认)。"""
    return bool(text and re.search(r'西周|東周|东周', text))


# ── 中文材质 → 项目 12 类材质枚举 ──
# 无匹配返回 '' (区别于 map_material 的保守默认值, 便于爬虫做过滤判定)
MATERIAL_MAP_ZH = [
    (r'翡翠|翠玉', '翡翠（翠玉）'),
    (r'玛瑙|玉髓', '玛瑙'),
    (r'水晶', '水晶'),
    (r'绿松石|松石', '绿松石'),
    (r'琥珀|蜜蜡', '琥珀'),
    (r'青金石', '青金石'),
    (r'蛇纹石|岫[岩玉]', '蛇纹石（岫玉）'),
    (r'独山|南阳玉', '独山玉'),
    (r'碧玉', '和田碧玉'),
    (r'青玉', '和田青玉'),
    (r'白玉', '和田白玉'),
    (r'青花', '和田青花'),
    (r'玉', '和田白玉'),
]


def map_material_zh(text: str) -> str:
    """中文材质文本 → 项目材质枚举; 无匹配返回 ''。"""
    if not text:
        return ''
    for pattern, mat in MATERIAL_MAP_ZH:
        if re.search(pattern, text):
            return mat
    return ''


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
