#!/usr/bin/env python3
"""
古玉鉴真 — 《中国出土玉器全集》批量标注导入

策略:
1. 快速提取所有页面图片 (150 DPI 平衡质量与速度)
2. 从 PDF 文件名推断地域 + 从页码位置粗略推断年代
3. 写入 genuine.jsonl 作为标注初稿
4. 后续通过 OCR 或人工回填精确字段

Volume -> Region mapping:
  1: 北京/天津/河北
  2: 内蒙古/辽宁/吉林/黑龙江
  3: 山西
  4: 山东
  5: 河南
  6: 安徽
  7: 江苏/上海
  8: 浙江
  9: 江西
  10: 湖北/湖南
  11: 广东/广西/福建/海南/澳门
  12: 云南/贵州/西藏
  13: 四川/重庆
  14: 陕西
  15: 甘肃/青海/宁夏/新疆
"""

import sys, os, json, re, hashlib
from pathlib import Path
from datetime import datetime
import fitz  # PyMuPDF

# ── Config ──
PDF_DIR = Path(r"D:\联想备份1\backup 2025Jan\中国出土玉器全集")
OUT_DIR = Path(r"D:\liuJade\annotation_data")
IMG_DIR = Path(r"D:\liuJade\scraped_data\出土玉器全集\images")
OUT_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)

# Volume metadata
VOLUME_INFO = {
    1:  {'regions': '北京/天津/河北', 'abbr': 'BJ', 'era_hint': 'A-K'},
    2:  {'regions': '内蒙古/辽宁/吉林/黑龙江', 'abbr': 'NMG', 'era_hint': 'A-K'},
    3:  {'regions': '山西', 'abbr': 'SX', 'era_hint': 'A-K'},
    4:  {'regions': '山东', 'abbr': 'SD', 'era_hint': 'A-K'},
    5:  {'regions': '河南', 'abbr': 'HN', 'era_hint': 'A-K'},
    6:  {'regions': '安徽', 'abbr': 'AH', 'era_hint': 'A-K'},
    7:  {'regions': '江苏/上海', 'abbr': 'JS', 'era_hint': 'A-K'},
    8:  {'regions': '浙江', 'abbr': 'ZJ', 'era_hint': 'A-K'},
    9:  {'regions': '江西', 'abbr': 'JX', 'era_hint': 'A-K'},
    10: {'regions': '湖北/湖南', 'abbr': 'HB', 'era_hint': 'A-K'},
    11: {'regions': '广东/广西/福建/海南/澳门', 'abbr': 'GD', 'era_hint': 'A-K'},
    12: {'regions': '云南/贵州/西藏', 'abbr': 'YN', 'era_hint': 'A-K'},
    13: {'regions': '四川/重庆', 'abbr': 'SC', 'era_hint': 'A-K'},
    14: {'regions': '陕西', 'abbr': 'SX2', 'era_hint': 'A-K'},
    15: {'regions': '甘肃/青海/宁夏/新疆', 'abbr': 'GS', 'era_hint': 'A-K'},
}

def get_volume_number(filename: str) -> int:
    """Extract volume number from filename like '中国出土玉器全集(1)+...'"""
    m = re.search(r'\((\d+)\)', filename)
    return int(m.group(1)) if m else 0

def import_all():
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    genuine_file = OUT_DIR / 'genuine.jsonl'
    total_count = 0

    print(f"Source: {PDF_DIR}")
    print(f"Output: {genuine_file}")
    print(f"Images: {IMG_DIR}")
    print(f"Files: {len(pdf_files)} PDFs")
    print()

    # Track processed volumes for resume
    processed_vols = set()

    for pdf_path in pdf_files:
        vol = get_volume_number(pdf_path.name)
        info = VOLUME_INFO.get(vol, {'regions': 'Unknown', 'abbr': 'XX'})

        # Skip if this volume was already fully processed
        if vol in processed_vols:
            continue

    for pdf_path in pdf_files:
        vol = get_volume_number(pdf_path.name)
        info = VOLUME_INFO.get(vol, {'regions': '未知', 'abbr': 'XX'})

        try:
            doc = fitz.open(str(pdf_path))
            n_pages = doc.page_count

            for page_num in range(n_pages):
                page = doc[page_num]

                # Render at 150 DPI (good balance)
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes('png')
                page_hash = hashlib.md5(img_bytes).hexdigest()[:12]

                # Save image
                img_name = f"{info['abbr']}_v{vol:02d}_p{page_num:03d}_{page_hash}.png"
                img_path = IMG_DIR / img_name

                # Skip if already exists
                if not img_path.exists():
                    with open(img_path, 'wb') as f:
                        f.write(img_bytes)

                # Build annotation record
                # Pages early in volume (lower numbers) tend to be earlier eras
                # This is a rough heuristic - OCR will refine later
                relative_pos = page_num / max(n_pages - 1, 1)

                record = {
                    'authenticity': '真老',
                    'era_code': 'A',   # Default: 文化期 (will be refined by OCR)
                    'era_name': '待OCR确认',
                    'product_name': f'出土玉器_{info["regions"]}',
                    'material': '和田白玉',   # Default (most excavated jade is Hetian)
                    'dimensions': None,
                    'source_type': '著录',
                    'source_detail': f'《中国出土玉器全集》第{vol}卷 {info["regions"]}',
                    'source_region': info['regions'],
                    'source_volume': vol,
                    'source_page': page_num + 1,
                    'source_pdf': pdf_path.name,
                    'artifact_name': '待标注',
                    'image_paths': [str(img_path)],
                    'image_width': pix.width,
                    'image_height': pix.height,
                    'page_position': round(relative_pos, 3),
                    'annotation_confidence': 1,  # 1 = needs OCR/manual review
                    'annotated_by': '自动导入(待OCR回填)',
                    'notes': f'《中国出土玉器全集》Vol.{vol} [{info["regions"]}] p.{page_num+1}/{n_pages} — OCR待回填',
                    'imported_at': datetime.now().isoformat(),
                }

                # Append to genuine.jsonl
                with open(genuine_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')

                total_count += 1

                if total_count % 100 == 0:
                    print(f"  Progress: {total_count} records...")

            doc.close()
            print(f"  [OK] Vol.{vol} {info['abbr']}: {n_pages} pages -> {n_pages} records")

        except Exception as e:
            print(f"  [FAIL] {pdf_path.name}: {e}")

    # Summary
    print(f"\n{'='*60}")
    print(f"✅ Import complete!")
    print(f"   Total records: {total_count}")
    print(f"   Output file:   {genuine_file}")
    print(f"   Image dir:     {IMG_DIR}")

    # Count images
    img_count = len(list(IMG_DIR.glob("*.png")))
    print(f"   Images:        {img_count} PNG files")

    # Show sample record
    with open(genuine_file, 'r', encoding='utf-8') as f:
        first = json.loads(f.readline())
    print(f"\nSample record:")
    print(json.dumps({k: v for k, v in first.items() if 'image' not in k},
                     ensure_ascii=False, indent=2)[:500])

if __name__ == '__main__':
    import_all()
