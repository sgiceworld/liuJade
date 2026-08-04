#!/usr/bin/env python3
"""
Clean import — process all 60 PDFs without skip logic.
Each PDF = 1 part of a volume. Each page = 1 record.
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
DPI = 80

VOLUME_REGIONS = {
    1: '北京/天津/河北', 2: '内蒙古/辽宁/吉林/黑龙江', 3: '山西',
    4: '山东', 5: '河南', 6: '安徽', 7: '江苏/上海',
    8: '浙江', 9: '江西', 10: '湖北/湖南',
    11: '广东/广西/福建/海南/澳门', 12: '云南/贵州/西藏',
    13: '四川/重庆', 14: '陕西', 15: '甘肃/青海/宁夏/新疆',
}

def get_vol(filename):
    m = re.search(r'\((\d+)\)', filename)
    return int(m.group(1)) if m else 0

def main():
    genuine_file = OUT_DIR / 'genuine.jsonl'
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))

    print(f"Processing {len(pdf_files)} PDF files...")
    total = 0

    for pdf_path in pdf_files:
        vol = get_vol(pdf_path.name)
        regions = VOLUME_REGIONS.get(vol, 'Unknown')
        abbr = ''.join(w[0] for w in regions.split('/'))[:4]

        doc = fitz.open(str(pdf_path))
        n_pages = doc.page_count

        for page_num in range(n_pages):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=DPI)
            img_bytes = pix.tobytes('png')

            # Save image
            img_name = f"{abbr}_v{vol:02d}_{pdf_path.stem[:20]}_p{page_num:03d}.png"
            img_path = IMG_DIR / img_name
            if not img_path.exists():
                with open(img_path, 'wb') as f:
                    f.write(img_bytes)

            record = {
                'authenticity': '真老',
                'era_code': 'A',
                'era_name': '待OCR确认',
                'product_name': f'待标注_{regions}',
                'material': '和田白玉',
                'dimensions': None,
                'source_type': '著录',
                'source_detail': f'《中国出土玉器全集》第{vol}卷 {regions}',
                'source_region': regions,
                'source_volume': vol,
                'source_page': page_num + 1,
                'source_pdf': pdf_path.name,
                'artifact_name': '待标注',
                'image_paths': [str(img_path.relative_to(Path(r'D:\liuJade')))],
                'image_width': pix.width,
                'image_height': pix.height,
                'annotation_confidence': 1,
                'annotated_by': '自动导入',
                'notes': f'Vol.{vol} [{regions}] {pdf_path.name[:30]} p.{page_num+1}/{n_pages}',
            }

            with open(genuine_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

            total += 1

        doc.close()

        if total % 500 == 0:
            print(f"  {total} records... ({pdf_path.name[:30]})")

    print(f"\nDone: {total} records")
    print(f"Output: {genuine_file}")

if __name__ == '__main__':
    main()
