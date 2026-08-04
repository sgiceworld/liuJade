#!/usr/bin/env python3
"""
古玉鉴真 — 《中国出土玉器全集》标注导入器

将扫描版 PDF 中的玉器图片和元数据提取为标注格式。
工作流程:
1. 提取 PDF 页面为图片 (PyMuPDF)
2. OCR 识别文字描述 (EasyOCR)
3. 解析结构化元数据 (品名/年代/材质/尺寸/来源)
4. 保存到 genuine.jsonl (出土玉器全为真老)
"""

import sys
import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# ── 配置 ────────────────────────────────────────────────

PDF_DIR = Path(r"D:\联想备份1\backup 2025Jan\中国出土玉器全集")
OUTPUT_DIR = Path(r"D:\liuJade\annotation_data")
IMAGE_OUTPUT_DIR = Path(r"D:\liuJade\scraped_data\出土玉器全集\images")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 正则解析器 ──────────────────────────────────────────

# 品名匹配: 编号. 名称 或 (编号:名称)
RE_NAME = re.compile(
    r'(?:^\d+[\.\、\s]+|编号[:：]\s*)?'
    r'(?P<name>玉[^，。,\n]{1,20})'
)

# 时代匹配 (映射到14年代代码)
ERA_MAP = [
    # (regex_pattern, era_code, era_name, coarse_group)
    (r'文化期|新石器|良渚|红山|龙山|仰韶|马家窑|齐家|石峡|凌家滩|大汶口|河姆渡|马家浜|崧泽|石家河', 'A', '文化期'),
    (r'商代?|殷墟|妇好|二里[头岗]|偃师', 'B', '商代'),
    (r'春秋', 'C', '春秋'),
    (r'战国|曾侯乙', 'D', '战国'),
    (r'秦|西汉|东汉|汉代?|汉墓|南越', 'E', '秦汉'),
    (r'三国|魏晋|南北朝|北魏|南朝|北齐|北周', 'F', '三国两晋南北朝'),
    (r'唐(?:代|朝)?[^三]', 'G', '唐'),
    (r'宋(?:代|朝)?|北宋|南宋', 'H', '宋'),
    (r'辽|金|元', 'I', '金元'),
    (r'明(?:代|朝)?[^清]', 'J', '明'),
    (r'清(?:代|朝)?', 'K', '清'),
    (r'民国', 'L', '民国'),
]

# 材质匹配
MATERIAL_MAP = [
    (r'和田白玉|羊脂白玉|白玉', '和田白玉'),
    (r'和田青玉|青玉', '和田青玉'),
    (r'和田碧玉|碧玉', '和田碧玉'),
    (r'青花', '和田青花'),
    (r'翡翠|翠玉', '翡翠（翠玉）'),
    (r'岫[岩玉]|蛇纹石', '岫玉'),
    (r'玛瑙', '玛瑙'),
    (r'水晶', '水晶'),
    (r'独山|南阳玉', '独山玉'),
    (r'绿松石|松石', '绿松石'),
    (r'琥珀|蜜蜡', '琥珀'),
]

# 来源提取
RE_SOURCE_COLLECTION = re.compile(
    r'(?:收藏单位|收藏|藏)[：:]\s*(?P<unit>[^\n]{2,30})'
)
RE_SOURCE_EXCAVATION = re.compile(
    r'(?:出土地点|出土)[：:]\s*(?P<site>[^\n]{2,50})'
)

# 尺寸提取 (支持多种格式)
RE_SIZE = re.compile(
    r'(?:尺寸|长|宽|高|厚|直径|射径|口径|通高|通长)'
    r'[：:\s]*'
    r'(?P<value>[\d.,，、\s\.]+)\s*(?:厘米|cm|毫米|mm)?'
)


def parse_era(text: str) -> Tuple[str, str, int]:
    """从文本中提取年代代码。返回 (era_code, era_name, group_idx)。"""
    for pattern, code, name in ERA_MAP:
        if re.search(pattern, text):
            group_map = {'A': 0, 'B': 0, 'C': 1, 'D': 1, 'E': 1,
                         'F': 2, 'G': 2, 'H': 2, 'I': 3, 'J': 3,
                         'K': 3, 'L': 4, 'M': 4, 'N': 4}
            return code, name, group_map.get(code, 0)
    return 'Z', '未知', -1  # 需要人工确认


def parse_material(text: str) -> str:
    """从文本中提取材质。"""
    for pattern, material in MATERIAL_MAP:
        if re.search(pattern, text):
            return material
    return '和田白玉'  # 默认（出土古玉大多为和田玉）


def parse_dimensions(text: str) -> Dict[str, Optional[float]]:
    """从文本中提取尺寸信息。"""
    dims = {}
    dim_patterns = [
        (r'长\s*[:：]?\s*([\d.]+)', 'length'),
        (r'宽\s*[:：]?\s*([\d.]+)', 'width'),
        (r'高\s*[:：]?\s*([\d.]+)', 'height'),
        (r'厚\s*[:：]?\s*([\d.]+)', 'thickness'),
        (r'直径\s*[:：]?\s*([\d.]+)', 'diameter'),
        (r'射径\s*[:：]?\s*([\d.]+)', 'diameter'),
        (r'口径\s*[:：]?\s*([\d.]+)', 'diameter'),
    ]
    for pattern, key in dim_patterns:
        m = re.search(pattern, text)
        if m:
            try:
                dims[key] = float(m.group(1))
            except ValueError:
                pass
    return dims


def parse_source(text: str) -> Tuple[str, str]:
    """从文本中提取来源信息。返回 (source_type, source_detail)。"""
    # 优先取收藏单位
    m = RE_SOURCE_COLLECTION.search(text)
    if m:
        return '馆藏', m.group('unit').strip()

    # 其次取出土地点
    m = RE_SOURCE_EXCAVATION.search(text)
    if m:
        return '馆藏', f"出土: {m.group('site').strip()}"

    return '馆藏', '中国出土玉器全集'


def parse_name(text: str) -> str:
    """从文本中提取品名。"""
    # 常见格式: 数字. 名称 或 数字、名称
    m = re.search(r'(?:\d+[\.\、\s]+)?(?P<name>玉\S{1,15})', text)
    if m:
        return m.group('name')
    # Fallback: 取第一行
    lines = text.strip().split('\n')
    return lines[0][:30] if lines else '未知玉器'


def generate_product_name(era_name: str, material: str, artifact_name: str) -> str:
    """生成标准品名: 时代+材质+器型。"""
    # 清理 artifact_name
    name = re.sub(r'[（(].*?[）)]', '', artifact_name)
    name = name.strip()
    return f"{era_name}{material}{name}"


# ── 主导入流程 ──────────────────────────────────────────

def import_volume(pdf_path: Path) -> int:
    """导入单卷 PDF。返回成功导入的记录数。"""
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    volume_name = pdf_path.stem[:40]
    count = 0

    print(f"\n{'='*60}")
    print(f"Processing: {volume_name}")
    print(f"  Pages: {doc.page_count}")
    print(f"{'='*60}")

    for page_num in range(doc.page_count):
        try:
            page = doc[page_num]

            # 提取页面为图片 (300 DPI)
            pix = page.get_pixmap(dpi=300)
            page_img_bytes = pix.tobytes("png")

            # 保存原始页面图片
            page_hash = hashlib.md5(page_img_bytes).hexdigest()[:12]
            img_filename = f"{volume_name[:8]}_p{page_num:03d}_{page_hash}.png"
            img_path = IMAGE_OUTPUT_DIR / img_filename
            with open(img_path, 'wb') as f:
                f.write(page_img_bytes)

            # OCR 识别文字 (由调用者处理)
            # 这里先收集 OCR 文本再解析

            # 如果 OCR 可用，传入文本；否则记录为待OCR
            record = _build_annotation_record(
                pdf_stem=pdf_path.stem,
                page=page_num,
                img_filename=img_filename,
                ocr_text=None,  # 待 OCR 后回填
            )

            if record:
                _append_to_genuine(record)
                count += 1

        except Exception as e:
            print(f"  ⚠ Page {page_num}: {e}")

    doc.close()
    print(f"  ✓ Imported {count} records from {volume_name}")
    return count


def _build_annotation_record(
    pdf_stem: str,
    page: int,
    img_filename: str,
    ocr_text: Optional[str] = None,
) -> Optional[Dict]:
    """构建一条标注记录。"""

    # 从 PDF 文件名推断地域信息
    region = _infer_region(pdf_stem)

    # OCR 文本解析 (如果有)
    if ocr_text:
        era_code, era_name, era_group = parse_era(ocr_text)
        material = parse_material(ocr_text)
        dimensions = parse_dimensions(ocr_text)
        source_type, source_detail = parse_source(ocr_text)
        artifact_name = parse_name(ocr_text)
        product_name = generate_product_name(era_name, material, artifact_name)
    else:
        era_code, era_name = 'A', '文化期'  # 默认，待人工标注
        material = '和田白玉'
        dimensions = {}
        source_type, source_detail = '著录', f'《中国出土玉器全集》{pdf_stem[:30]}'
        artifact_name = '玉器'
        product_name = '待标注'

    # 生成标签编码
    now = datetime.now()
    record = {
        'authenticity': '真老',
        'era_code': era_code,
        'era_name': era_name,
        'product_name': product_name,
        'material': material,
        'dimensions': dimensions if dimensions else None,
        'source_type': source_type,
        'source_detail': source_detail,
        'source_region': region,
        'source_pdf': pdf_stem,
        'source_page': page,
        'artifact_name': artifact_name,
        'image_paths': [str(IMAGE_OUTPUT_DIR / img_filename)],
        'annotation_confidence': 3 if ocr_text else 2,  # OCR=3分, 无OCR=2分需人工复核
        'annotated_by': 'OCR自动导入' if ocr_text else '待人工标注',
        'notes': f'《中国出土玉器全集》{pdf_stem[:40]} 第{page+1}页' + (
            '' if ocr_text else ' [需OCR回填]'
        ),
    }
    return record


def _infer_region(pdf_stem: str) -> str:
    """从 PDF 文件名推断省份/地区。"""
    region_map = {
        '北京': '北京', '天津': '天津', '河北': '河北',
        '内蒙古': '内蒙古', '辽宁': '辽宁', '吉林': '吉林', '黑龙江': '黑龙江',
        '山西': '山西', '山东': '山东', '河南': '河南', '安徽': '安徽',
        '江苏': '江苏', '上海': '上海', '浙江': '浙江', '江西': '江西',
        '湖北': '湖北', '湖南': '湖南',
        '广东': '广东', '广西': '广西', '福建': '福建', '海南': '海南',
        '云南': '云南', '贵州': '贵州', '西藏': '西藏',
        '四川': '四川', '重庆': '重庆',
        '陕西': '陕西', '甘肃': '甘肃', '青海': '青海', '宁夏': '宁夏', '新疆': '新疆',
    }
    for key, region in region_map.items():
        if key in pdf_stem:
            return region
    return '未知地区'


def _append_to_genuine(record: Dict):
    """追加一条记录到 genuine.jsonl。"""
    genuine_file = OUTPUT_DIR / 'genuine.jsonl'
    with open(genuine_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')
        f.flush()


# ── OCR 批处理 ──────────────────────────────────────────

def batch_ocr_pages(pdf_path: Path, reader) -> List[str]:
    """
    对一个 PDF 的所有页面执行 OCR，返回每页的文本列表。

    Args:
        pdf_path: PDF 文件路径
        reader: EasyOCR Reader 实例

    Returns:
        List[str] 每页的 OCR 文本
    """
    import fitz

    doc = fitz.open(str(pdf_path))
    texts = []

    for page_num in range(doc.page_count):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=200)  # 200 DPI 节省 OCR 时间
        img_bytes = pix.tobytes("png")

        import numpy as np
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_bytes))
        img_np = np.array(img)

        # OCR
        results = reader.readtext(img_np, detail=0)
        page_text = '\n'.join(results)
        texts.append(page_text)

        if (page_num + 1) % 10 == 0:
            print(f"  OCR progress: {page_num + 1}/{doc.page_count}")

    doc.close()
    return texts


# ── 主入口 ──────────────────────────────────────────────

def main():
    """主导入流程。"""
    print("=" * 60)
    print("古玉鉴真 — 《中国出土玉器全集》标注导入")
    print("=" * 60)

    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    print(f"\nFound {len(pdf_files)} PDF files in {PDF_DIR}")
    print(f"Output: {OUTPUT_DIR / 'genuine.jsonl'}")

    # 尝试初始化 EasyOCR
    use_ocr = False
    reader = None
    try:
        import easyocr
        print("\nInitializing EasyOCR (Chinese)...")
        reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
        use_ocr = True
        print("✓ EasyOCR ready")
    except ImportError:
        print("⚠ EasyOCR not installed, will import page images only (metadata needs manual annotation)")
    except Exception as e:
        print(f"⚠ EasyOCR init failed: {e}")

    total = 0
    for pdf_file in pdf_files:
        try:
            # 提取页面图片
            count = import_volume(pdf_file)

            # 如果 OCR 可用，对已导入的记录回填元数据
            if use_ocr and reader:
                print(f"  Running OCR on {pdf_file.name}...")
                page_texts = batch_ocr_pages(pdf_file, reader)
                print(f"  OCR completed: {len(page_texts)} pages")

                # TODO: 回填 OCR 文本到记录

            total += count
        except Exception as e:
            print(f"  ✗ Failed to process {pdf_file.name}: {e}")

    print(f"\n{'='*60}")
    print(f"✅ 导入完成: {total} 条记录")
    print(f"   输出文件: {OUTPUT_DIR / 'genuine.jsonl'}")
    print(f"   图片目录: {IMAGE_OUTPUT_DIR}")

    # 显示样例
    genuine_file = OUTPUT_DIR / 'genuine.jsonl'
    if genuine_file.exists():
        with open(genuine_file, 'r', encoding='utf-8') as f:
            count = sum(1 for _ in f)
        print(f"   当前总记录数: {count}")
        print(f"\n最新一条记录:")
        with open(genuine_file, 'r', encoding='utf-8') as f:
            # 读最后一行
            lines = f.readlines()
            if lines:
                sample = json.loads(lines[-1])
                print(json.dumps(sample, ensure_ascii=False, indent=2)[:400])


if __name__ == '__main__':
    main()
