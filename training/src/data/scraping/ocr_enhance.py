#!/usr/bin/env python3
"""
古玉鉴真 — OCR 元数据增强

对 imported 记录执行 OCR，从页面图片中提取:
- 品名 (artifact name)
- 年代 (era)
- 材质 (material)
- 尺寸 (dimensions)
- 来源/收藏单位 (source)

工作流程:
1. 读取 genuine.jsonl 中 annotation_confidence=1 的记录
2. 加载对应页面图片
3. 对页面下半部分执行 OCR (描述文字区域)
4. 解析 OCR 文本为结构化字段
5. 更新 genuine.jsonl 记录
"""

import sys, os, json, re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple

OUT_DIR = Path(r"D:\liuJade\annotation_data")

# ── Metadata Parsers ────────────────────────────────────

ERA_PATTERNS = [
    (r'新石器|良渚|红山|龙山|仰韶|马家窑|齐家|凌家滩|大汶口|河姆渡|马家浜|崧泽|石家河|兴隆洼', 'A', '文化期'),
    (r'商代?|殷墟|妇好|二里[头岗]|偃师', 'B', '商代'),
    (r'春秋', 'C', '春秋'),
    (r'战国|曾侯乙', 'D', '战国'),
    (r'秦代?|西汉|东汉|汉代?|南越', 'E', '秦汉'),
    (r'三国|魏晋|南北朝|北魏|南朝|北齐', 'F', '三国两晋南北朝'),
    (r'唐代?', 'G', '唐'),
    (r'宋代?|北宋|南宋', 'H', '宋'),
    (r'辽代?|金代?|元代?', 'I', '金元'),
    (r'明代?', 'J', '明'),
    (r'清代?', 'K', '清'),
    (r'民国', 'L', '民国'),
]

MATERIAL_PATTERNS = [
    (r'白玉|羊脂白', '和田白玉'),
    (r'青玉', '和田青玉'),
    (r'碧玉', '和田碧玉'),
    (r'青花', '和田青花'),
    (r'翡翠|翠玉', '翡翠（翠玉）'),
    (r'岫[岩玉]|蛇纹石', '岫玉'),
    (r'玛瑙', '玛瑙'),
    (r'水晶', '水晶'),
    (r'独山', '独山玉'),
    (r'绿松|松石', '绿松石'),
    (r'琥珀|蜜蜡', '琥珀'),
]


def parse_era(text: str) -> Tuple[str, str]:
    for pattern, code, name in ERA_PATTERNS:
        if re.search(pattern, text):
            return code, name
    return 'A', '文化期'  # safest default for excavated jade


def parse_material(text: str) -> str:
    for pattern, mat in MATERIAL_PATTERNS:
        if re.search(pattern, text):
            return mat
    # Try to detect "玉" type descriptions
    if '黄玉' in text: return '和田白玉'  # ancient "黄玉" often = fine white
    if '墨玉' in text: return '和田青花'
    return '和田白玉'  # default for excavated jade


def parse_dimensions(text: str) -> Optional[Dict]:
    dims = {}
    patterns = [
        (r'(?:通高|高)\s*(\d+[\.\d]*)\s*(?:厘米|cm)?', 'height'),
        (r'(?:长|通长)\s*(\d+[\.\d]*)\s*(?:厘米|cm)?', 'length'),
        (r'(?:宽)\s*(\d+[\.\d]*)\s*(?:厘米|cm)?', 'width'),
        (r'(?:厚)\s*(\d+[\.\d]*)\s*(?:厘米|cm)?', 'thickness'),
        (r'(?:直径|射径|口径)\s*(\d+[\.\d]*)\s*(?:厘米|cm)?', 'diameter'),
    ]
    for pattern, key in patterns:
        m = re.search(pattern, text)
        if m:
            try:
                dims[key] = float(m.group(1))
            except ValueError:
                pass
    return dims if dims else None


def parse_artifact_name(text: str) -> str:
    """Extract artifact name from first line or numbered item."""
    # Common format: "1. 玉琮" or "玉琮（M12:98）"
    m = re.search(r'(?:\d+[\.\、]?\s*)?(?P<name>玉\S{1,20})', text)
    if m:
        name = m.group('name')
        # Clean up trailing punctuation
        name = re.sub(r'[，。；、]$', '', name)
        return name
    # Fallback: first significant line
    lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 2]
    return lines[0][:25] if lines else '玉器'


def parse_collection(text: str) -> Optional[str]:
    """Extract collection unit."""
    patterns = [
        r'(?:收藏单位|收藏|现藏)[：:\s]*(?P<unit>[^\n]{3,40})',
        r'(?P<unit>[^\n]{2,20}(?:博物馆|研究所|考古所|文物局|文管所|博物院))',
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            unit = m.group('unit').strip()
            # Filter out non-unit matches
            if len(unit) >= 4:
                return unit
    return None


def parse_excavation(text: str) -> Optional[str]:
    """Extract excavation site."""
    patterns = [
        r'(?:出土地点|出土)[：:\s]*(?P<site>[^\n]{3,50})',
        r'(?P<year>\d{4})年[^，,\n]{2,20}(?:出土|发掘|发现)',
        r'(?:出土于|发现于)\s*(?P<site>[^\n]{3,30})',
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            if 'site' in m.groupdict() and m.group('site'):
                return m.group('site').strip()
            if 'year' in m.groupdict() and m.group('year'):
                return m.group(0).strip()
    return None


def enhance_record(record: Dict, ocr_text: str) -> Dict:
    """Enhance a record with OCR-extracted metadata."""
    era_code, era_name = parse_era(ocr_text)
    material = parse_material(ocr_text)
    dimensions = parse_dimensions(ocr_text)
    artifact_name = parse_artifact_name(ocr_text)
    collection = parse_collection(ocr_text)
    excavation = parse_excavation(ocr_text)

    # Build product name: era + material + artifact type
    product_name = f"{era_name}{material}{artifact_name}"

    # Source detail
    source_parts = []
    if collection:
        source_parts.append(f"藏: {collection}")
    if excavation:
        source_parts.append(f"出土: {excavation}")
    source_detail = '; '.join(source_parts) if source_parts else record.get('source_detail', '')

    record.update({
        'era_code': era_code,
        'era_name': era_name,
        'product_name': product_name,
        'material': material,
        'dimensions': dimensions,
        'source_detail': source_detail,
        'artifact_name': artifact_name,
        'annotation_confidence': 4,  # OCR result, high but may need review
        'annotated_by': 'OCR增强',
        'ocr_text_sample': ocr_text[:200],
        'ocr_enhanced_at': datetime.now().isoformat(),
        'notes': record.get('notes', '') + ' [OCR已回填]',
    })
    return record


# ── Main ────────────────────────────────────────────────

def main(n_samples: int = 0):
    """
    Enhance records with OCR.

    Args:
        n_samples: Number of records to process (0 = all pending)
    """
    import easyocr
    import numpy as np
    from PIL import Image

    genuine_file = OUT_DIR / 'genuine.jsonl'
    if not genuine_file.exists():
        print("No genuine.jsonl found. Run batch_import.py first.")
        return

    # Read all records
    records = []
    with open(genuine_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    # Filter pending
    pending = [r for r in records if r.get('annotation_confidence', 0) <= 2]
    print(f"Total records: {len(records)}")
    print(f"Pending OCR:   {len(pending)}")

    if n_samples > 0:
        pending = pending[:n_samples]
        print(f"Processing:     {len(pending)} (sample mode)")

    if not pending:
        print("No records need OCR enhancement.")
        return

    # Init EasyOCR
    print("Initializing EasyOCR (Chinese)...")
    reader = easyocr.Reader(['ch_sim'], gpu=False)
    print("Ready.\n")

    enhanced = 0
    for i, record in enumerate(pending):
        try:
            image_paths = record.get('image_paths', [])
            if not image_paths:
                continue

            img_path = image_paths[0]
            if not os.path.exists(img_path):
                # Try relative to liuJade
                alt_path = Path(r'D:\liuJade') / img_path
                if alt_path.exists():
                    img_path = str(alt_path)
                else:
                    continue

            # Load image and crop to bottom 40% (description area)
            img = Image.open(img_path)
            w, h = img.size
            # Text is typically in bottom 40% of page
            text_region = img.crop((0, int(h * 0.6), w, h))
            text_np = np.array(text_region)

            # OCR
            results = reader.readtext(text_np, detail=0)
            ocr_text = '\n'.join(results)

            if ocr_text.strip():
                # Enhance the record
                record = enhance_record(record, ocr_text)
                enhanced += 1

                if enhanced % 10 == 0:
                    print(f"  OCR enhanced: {enhanced}/{len(pending)}")

        except Exception as e:
            print(f"  ⚠ Error on record {i}: {e}")

    # Write back updated records
    with open(genuine_file, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    print(f"\n✅ OCR enhancement complete: {enhanced} records updated")
    print(f"   File: {genuine_file}")

    # Show sample
    if enhanced > 0:
        updated = [r for r in records if r.get('annotation_confidence', 0) >= 3]
        if updated:
            sample = updated[-1]
            print(f"\nSample enhanced record:")
            print(f"  品名: {sample.get('product_name')}")
            print(f"  年代: {sample.get('era_name')} ({sample.get('era_code')})")
            print(f"  材质: {sample.get('material')}")
            print(f"  尺寸: {sample.get('dimensions')}")
            print(f"  来源: {sample.get('source_detail')}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--samples', type=int, default=0,
                        help='Number of samples to process (0=all)')
    args = parser.parse_args()
    main(n_samples=args.samples)
