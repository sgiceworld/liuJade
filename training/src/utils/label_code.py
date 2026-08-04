"""
古玉鉴真 — 标签编码生成器
根据定义规则自动生成标签编码和总登录号

编码结构: {真伪代码}_{总登录号}_{日期时间}_{年代代码}_{序号}
"""

from datetime import datetime
from typing import Dict, Tuple


# ── 年代枚举 ────────────────────────────────────────────

ERA_CODE = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N']

ERA_NAMES: Dict[str, str] = {
    'A': '文化期', 'B': '商代', 'C': '春秋', 'D': '战国',
    'E': '秦汉', 'F': '三国两晋南北朝', 'G': '唐', 'H': '宋',
    'I': '金元', 'J': '明', 'K': '清', 'L': '民国',
    'M': '出口创汇', 'N': '现代',
}

ERA_GROUPS: Dict[int, str] = {
    0: '远古', 1: '古典', 2: '中古', 3: '近古', 4: '近现代',
}

ERA_TO_GROUP: Dict[str, int] = {
    'A': 0, 'B': 0,                    # 远古
    'C': 1, 'D': 1, 'E': 1,            # 古典
    'F': 2, 'G': 2, 'H': 2,            # 中古
    'I': 3, 'J': 3, 'K': 3,            # 近古
    'L': 4, 'M': 4, 'N': 4,            # 近现代
}

# ── 真伪枚举 ────────────────────────────────────────────

AUTH_CODE = {'0': '真老', '1': '新仿'}

# ── 材质枚举 ────────────────────────────────────────────

MATERIALS = [
    '和田白玉', '和田青玉', '和田碧玉', '和田青花',
    '翡翠（翠玉）', '岫玉', '玛瑙', '水晶',
    '独山玉', '绿松石', '琥珀', '其他',
]

SOURCE_TYPES = ['馆藏', '拍卖', '著录']

# ── 标签编码生成 ────────────────────────────────────────

def generate_login_number(date: datetime, daily_seq: int) -> str:
    """生成总登录号: JY + YYYYMMDD + 6位流水号"""
    return f"JY{date.strftime('%Y%m%d')}{daily_seq:06d}"


def generate_label_code(
    authenticity: str,
    era_code: str,
    date: datetime,
    seq: int,
    daily_seq: int,
) -> str:
    """
    生成完整标签编码。

    Args:
        authenticity: '0' (真老) 或 '1' (新仿)
        era_code: 年代代码 A-N
        date: 标注日期时间
        seq: 同日同年代流水号 (3位)
        daily_seq: 当日全局流水号 (6位)

    Returns:
        标签编码字符串, 如 '0_JY20260802000001_20260802143025_G_001'
    """
    login_number = generate_login_number(date, daily_seq)
    return f"{authenticity}_{login_number}_{date.strftime('%Y%m%d%H%M%S')}_{era_code}_{seq:03d}"


def parse_label_code(code: str) -> Dict[str, str]:
    """解析标签编码，返回各字段。"""
    parts = code.split('_')
    if len(parts) != 5:
        raise ValueError(f"Invalid label code: {code}")

    return {
        'auth_code': parts[0],
        'login_number': parts[1],
        'datetime': parts[2],
        'era_code': parts[3],
        'sequence': parts[4],
    }
