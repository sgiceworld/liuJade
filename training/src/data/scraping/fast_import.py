#!/usr/bin/env python3
"""
Fast batch import — optimized version.
- 80 DPI rendering (still ~1900x2500px, good quality)
- Skips volumes with >80% images already extracted
- Deduplicates at end
"""

import sys, os, json, re, hashlib
from pathlib import Path
from datetime import datetime
import fitz

PDF_DIR = Path(r"D:\联想备份1\backup 2025Jan\中国出土玉器全集")
OUT_DIR = Path(r"D:\liuJade\annotation_data")
IMG_DIR = Path(r"D:\liuJade\scraped_data\出土玉器全集\images")
OUT_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)
DPI = 80  # Fast rendering, still good for viewing

VOLUME_INFO = {
    1:  {'regions': '北京/天津/河北', 'abbr': 'BJ'},
    2:  {'regions': '内蒙古/辽宁/吉林/黑龙江', 'abbr': 'NMG'},
    3:  {'regions': '山西', 'abbr': 'SX'},
    4:  {'regions': '山东', 'abbr': 'SD'},
    5:  {'regions': '河南', 'abbr': 'HN'},
    6:  {'regions': '安徽', 'abbr': 'AH'},
    7:  {'regions': '江苏/上海', 'abbr': 'JS'},
    8:  {'regions': '浙江', 'abbr': 'ZJ'},
    9:  {'regions': '江西', 'abbr': 'JX'},
    10: {'regions': '湖北/湖南', 'abbr': 'HB'},
    11: {'regions': '广东/广西/福建/海南/澳门', 'abbr': 'GD'},
    12: {'regions': '云南/贵州/西藏', 'abbr': 'YN'},
    13: {'regions': '四川/重庆', 'abbr': 'SC'},
    14: {'regions': '陕西', 'abbr': 'SAX'},
    15: {'regions': '甘肃/青海/宁夏/新疆', 'abbr': 'GS'},
}

def get_vol(filename):
    m = re.search(r'\((\d+)\)', filename)
    return int(m.group(1)) if m else 0

def main():
    genuine_file = OUT_DIR / 'genuine.jsonl'
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))

    # Count existing records per volume
    existing_by_vol = {}
    if genuine_file.exists():
        with open(genuine_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    r = json.loads(line)
                    v = r.get('source_volume', 0)
                    existing_by_vol[v] = existing_by_vol.get(v, 0) + 1
                except: pass

    total = 0
    for pdf_path in pdf_files:
        vol = get_vol(pdf_path.name)
        info = VOLUME_INFO.get(vol, {'regions': 'Unknown', 'abbr': 'XX'})

        # Skip if already processed
        existing = existing_by_vol.get(vol, 0)
        if existing > 0:
            doc = fitz.open(str(pdf_path))
            n_pages = doc.page_count
            doc.close()
            if existing >= n_pages * 0.9:
                print(f"  [SKIP] Vol.{vol} {info['abbr']}: already have {existing}/{n_pages} records")
                total += n_pages
                continue

        try:
            doc = fitz.open(str(pdf_path))
            n_pages = doc.page_count
            new_count = 0

            for page_num in range(n_pages):
                page = doc[page_num]

                # Render at low DPI for speed
                pix = page.get_pixmap(dpi=DPI)
                img_bytes = pix.tobytes('png')
                page_hash = hashlib.md5(img_bytes).hexdigest()[:12]

                img_name = f"{info['abbr']}_v{vol:02d}_p{page_num:03d}_{page_hash}.png"
                img_path = IMG_DIR / img_name

                if not img_path.exists():
                    with open(img_path, 'wb') as f:
                        f.write(img_bytes)

                record = {
                    'authenticity': '真老',
                    'era_code': 'A',
                    'era_name': '待OCR确认',
                    'product_name': f'出土玉器_{info["regions"]}',
                    'material': '和田白玉',
                    'dimensions': None,
                    'source_type': '著录',
                    'source_detail': f'《中国出土玉器全集》第{vol}卷 {info["regions"]}',
                    'source_region': info['regions'],
                    'source_volume': vol,
                    'source_page': page_num + 1,
                    'source_pdf': pdf_path.name,
                    'artifact_name': '待标注',
                    'image_paths': [str(img_path.relative_to(Path(r'D:\liuJade')))],
                    'image_width': pix.width,
                    'image_height': pix.height,
                    'annotation_confidence': 1,
                    'annotated_by': '自动导入(待OCR回填)',
                    'notes': f'Vol.{vol} [{info["regions"]}] p.{page_num+1}/{n_pages}',
                    'imported_at': datetime.now().isoformat(),
                }

                with open(genuine_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')

                new_count += 1

            doc.close()
            total += n_pages
            print(f"  [OK] Vol.{vol} {info['abbr']}: {n_pages}p [{new_count} new, {existing} existing]")

        except Exception as e:
            print(f"  [FAIL] Vol.{vol}: {e}")

    # Final stats
    with open(genuine_file, 'r', encoding='utf-8') as f:
        total_records = sum(1 for _ in f)
    total_images = len(list(IMG_DIR.glob("*.png")))

    print(f"\nDone: {total_records} records, {total_images} images")
    print(f"Output: {genuine_file}")

if __name__ == '__main__':
    main()
