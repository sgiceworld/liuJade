"""
古玉鉴真 — OCR 引擎 (API 端)

为交互式审查提供单页 OCR。
返回解析后的建议字段，由用户确认或修改。
"""

import re
import numpy as np
from PIL import Image
from pathlib import Path


def ocr_single_page(image_path: str, max_width: int = 1000, crop_bottom: float = 0.4) -> dict:
    """
    OCR a single page and return parsed metadata suggestions.

    Args:
        image_path: Full path to the page image
        max_width: Resize to this width for OCR speed
        crop_bottom: Fraction of image bottom to OCR (0.4 = bottom 40%)

    Returns:
        dict with suggested era_code, era_name, material, artifact_name,
             dimensions, collection, raw_text
    """
    try:
        import easyocr

        reader = easyocr.Reader(['ch_sim'], gpu=False)

        img = Image.open(image_path)
        w, h = img.size

        # Resize for speed
        if w > max_width:
            ratio = max_width / w
            img = img.resize((max_width, int(h * ratio)), Image.LANCZOS)

        # Crop bottom portion
        new_h = img.size[1]
        crop_top = int(new_h * (1 - crop_bottom))
        text_region = img.crop((0, crop_top, img.size[0], new_h))

        # OCR
        results = reader.readtext(np.array(text_region), detail=0)
        ocr_text = '\n'.join(results)
    except Exception as e:
        return {'raw_text': '', 'error': str(e)}

    if not ocr_text.strip():
        return {'raw_text': ''}

    return {
        'raw_text': ocr_text[:500],
        **parse_ocr_text(ocr_text),
    }


def parse_ocr_text(text: str) -> dict:
    """Parse OCR text into structured metadata suggestions."""
    era_code, era_name = _parse_era(text)
    material = _parse_material(text)
    artifact_name = _parse_artifact_name(text)
    dims = _parse_dimensions(text)
    collection = _parse_collection(text)

    return {
        'era_code': era_code,
        'era_name': era_name,
        'material': material,
        'artifact_name': artifact_name,
        'dimensions': dims,
        'collection': collection,
    }


# ── Private parsers ──

def _parse_era(text):
    patterns = [
        (r'文化期|新石器|良渚|红山|龙山|仰韶|马家窑|齐家|凌家滩|大汶口|河姆渡|马家浜|崧泽|石家河|兴隆洼|裴李岗', 'A', '文化期'),
        (r'(?<!夏)商(?:代|朝)?(?!周)|殷墟|妇好|二里[头岗]', 'B', '商代'),
        (r'春秋(?!战国)', 'C', '春秋'),
        (r'战国|曾侯乙', 'D', '战国'),
        (r'秦(?:代|朝)?(?!汉)|西汉|东汉|汉代?|汉墓|南越', 'E', '秦汉'),
        (r'三国|魏晋|南北朝|北魏|南朝|北齐|北周|十六国', 'F', '三国两晋南北朝'),
        (r'唐(?:代|朝)?(?!五)', 'G', '唐'),
        (r'宋(?:代|朝)?|北宋|南宋(?!元)', 'H', '宋'),
        (r'辽(?:代|朝)?|金(?:代|朝)?(?!元)|元(?:代|朝)?', 'I', '金元'),
        (r'明(?:代|朝)?(?!清)', 'J', '明'),
        (r'清(?:代|朝)?(?!民)', 'K', '清'),
        (r'民国', 'L', '民国'),
        (r'出口创汇|创汇', 'M', '出口创汇'),
        (r'现代[^化]|当代', 'N', '现代'),
    ]
    for pattern, code, name in patterns:
        if re.search(pattern, text):
            return code, name
    return 'A', '文化期'


def _parse_material(text):
    for pat, mat in [
        (r'白玉|羊脂', '和田白玉'), (r'青玉', '和田青玉'), (r'碧玉', '和田碧玉'),
        (r'青花', '和田青花'), (r'翡翠|翠玉', '翡翠（翠玉）'), (r'岫[岩玉]', '岫玉'),
        (r'玛瑙', '玛瑙'), (r'水晶', '水晶'), (r'独山', '独山玉'),
        (r'绿松|松石', '绿松石'), (r'琥珀|蜜蜡', '琥珀'),
    ]:
        if re.search(pat, text): return mat
    return '和田白玉'


def _parse_dimensions(text):
    dims = {}
    for pat, key in [
        (r'高\s*(\d+[\.\d]*)', 'height'), (r'长\s*(\d+[\.\d]*)', 'length'),
        (r'宽\s*(\d+[\.\d]*)', 'width'), (r'厚\s*(\d+[\.\d]*)', 'thickness'),
        (r'(?:直径|射径|口径)\s*(\d+[\.\d]*)', 'diameter'),
    ]:
        m = re.search(pat, text)
        if m:
            try: dims[key] = float(m.group(1))
            except: pass
    return dims if dims else None


def _parse_artifact_name(text):
    m = re.search(r'(?:\d+[\.\、\s]+)?(?P<name>玉\S{1,18})', text)
    if m:
        return re.sub(r'[，。；、]$', '', m.group('name'))
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 2]
    return lines[0][:25] if lines else '玉器'


def _parse_collection(text):
    m = re.search(r'(?:收藏单位|收藏|现藏|藏)[：:\s]*(?P<u>[^\n]{3,40})', text)
    if m: return m.group('u').strip()
    m = re.search(r'(?P<u>[^\n]{2,20}(?:博物馆|研究所|考古所|文物局|文管所|博物院))', text)
    if m: return m.group('u').strip()
    return None
