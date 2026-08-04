#!/usr/bin/env python3
"""
古玉鉴真 — 批量 OCR 标注回填

优化策略:
- 图片缩小到 800px 宽 (大幅提速)
- 仅 OCR 页面底部 35% (描述文字区域)
- 每 100 条记录存盘，可中断续
- 同时更新 genuine.jsonl + SQLite

运行: PYTHONIOENCODING=utf-8 python run_ocr.py
"""

import sys, os, json, re
from pathlib import Path
from datetime import datetime

# ── Config ──
JSONL_FILE = Path(r"D:\liuJade\annotation_data\genuine.jsonl")
IMG_ROOT = Path(r"D:\liuJade")
CHECKPOINT_FILE = Path(r"D:\liuJade\annotation_data\ocr_checkpoint.json")
MAX_IMG_WIDTH = 800        # Resize to speed up OCR
CROP_BOTTOM_RATIO = 0.35   # Only OCR bottom 35% of page

# ── Parsers ──

def parse_era(text):
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
    ]
    for pattern, code, name in patterns:
        if re.search(pattern, text):
            return code, name
    return 'A', '文化期'

def parse_material(text):
    for pat, mat in [
        (r'白玉|羊脂', '和田白玉'), (r'青玉', '和田青玉'), (r'碧玉', '和田碧玉'),
        (r'青花', '和田青花'), (r'翡翠|翠玉', '翡翠（翠玉）'), (r'岫[岩玉]', '岫玉'),
        (r'玛瑙', '玛瑙'), (r'水晶', '水晶'), (r'独山', '独山玉'),
        (r'绿松|松石', '绿松石'), (r'琥珀|蜜蜡', '琥珀'),
    ]:
        if re.search(pat, text): return mat
    return '和田白玉'

def parse_dimensions(text):
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

def parse_artifact_name(text):
    m = re.search(r'(?:\d+[\.\、\s]+)?(?P<name>玉\S{1,18})', text)
    if m:
        return re.sub(r'[，。；、]$', '', m.group('name'))
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 2]
    return lines[0][:25] if lines else '玉器'

def parse_collection(text):
    m = re.search(r'(?:收藏单位|收藏|现藏|藏)[：:\s]*(?P<u>[^\n]{3,40})', text)
    if m: return m.group('u').strip()
    m = re.search(r'(?P<u>[^\n]{2,20}(?:博物馆|研究所|考古所|文物局|文管所|博物院|文物工作站))', text)
    if m: return m.group('u').strip()
    return None

def generate_product_name(era_name, material, artifact_name):
    name = re.sub(r'[（(].*?[）)]', '', artifact_name).strip()
    return f"{era_name}{material}{name}"

# ── Main ──

def main(start_from=0, max_count=None):
    # Load checkpoint
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            ck = json.load(f)
            start_from = ck.get('processed', 0)
        print(f"Resuming from record {start_from}")

    # Load records
    records = []
    with open(JSONL_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    total = len(records)
    if max_count:
        total = min(total, start_from + max_count)
    print(f"Total: {len(records)} records, processing {start_from}-{total-1}")

    # Init OCR
    import easyocr
    import numpy as np
    from PIL import Image
    print("Loading EasyOCR...")
    reader = easyocr.Reader(['ch_sim'], gpu=False)
    print("Ready.\n")

    updated = 0
    for i in range(start_from, total):
        rec = records[i]
        # Skip already OCR'd
        if rec.get('annotation_confidence', 1) >= 3:
            continue

        paths = rec.get('image_paths', [])
        if not paths:
            continue

        img_path = IMG_ROOT / paths[0].replace('\\', '/')
        if not img_path.exists():
            continue

        try:
            # Load and resize
            img = Image.open(img_path)
            w, h = img.size
            if w > MAX_IMG_WIDTH:
                ratio = MAX_IMG_WIDTH / w
                img = img.resize((MAX_IMG_WIDTH, int(h * ratio)), Image.LANCZOS)

            # Crop bottom portion (description text)
            new_h = img.size[1]
            crop_top = int(new_h * (1 - CROP_BOTTOM_RATIO))
            text_region = img.crop((0, crop_top, img.size[0], new_h))

            # OCR
            results = reader.readtext(np.array(text_region), detail=0)
            ocr_text = '\n'.join(results)

            if not ocr_text.strip():
                continue

            # Parse
            era_code, era_name = parse_era(ocr_text)
            material = parse_material(ocr_text)
            dims = parse_dimensions(ocr_text)
            artifact_name = parse_artifact_name(ocr_text)
            collection = parse_collection(ocr_text)
            product_name = generate_product_name(era_name, material, artifact_name)

            # Build source detail
            detail_parts = [rec.get('source_detail', '')]
            if collection:
                detail_parts.append(f"藏: {collection}")

            # Update record
            rec.update({
                'era_code': era_code,
                'era_name': era_name,
                'product_name': product_name,
                'material': material,
                'dimensions': dims,
                'source_detail': '; '.join(detail_parts),
                'artifact_name': artifact_name,
                'annotation_confidence': 4,
                'annotated_by': 'OCR自动标注',
                'notes': rec.get('notes', '') + ' [OCR已处理]',
                'ocr_processed_at': datetime.now().isoformat(),
            })
            updated += 1

        except Exception as e:
            print(f"  Err record {i}: {e}")

        # Checkpoint every 100
        if (i + 1) % 100 == 0:
            # Write JSONL
            with open(JSONL_FILE, 'w', encoding='utf-8') as f:
                for r in records:
                    f.write(json.dumps(r, ensure_ascii=False) + '\n')
            # Save checkpoint
            with open(CHECKPOINT_FILE, 'w') as f:
                json.dump({'processed': i + 1, 'updated': updated, 'total': len(records)}, f)
            print(f"  [{i+1}/{len(records)}] Updated {updated} records")

    # Final save
    with open(JSONL_FILE, 'w', encoding='utf-8') as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump({'processed': total, 'updated': updated, 'total': len(records)}, f)

    print(f"\nDone! Updated {updated} of {total} records")
    return records


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--start', type=int, default=0, help='Start from record N')
    p.add_argument('--max', type=int, default=None, help='Max records to process')
    args = p.parse_args()
    main(start_from=args.start, max_count=args.max)
