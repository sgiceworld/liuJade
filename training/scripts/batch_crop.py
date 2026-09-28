#!/usr/bin/env python3
"""
古玉鉴真 — 批量页面裁剪

遍历 jade.db 中全部玉器记录对应的书页图片, 运行 image_splitter
自动裁剪黑底玉器照片, 按年代归档到 training_data/{年代}/,
追加 training_manifest.jsonl, 并回写 jade.db 的 training_image 列
(审查接口 /ocr/review/next 优先返回该裁剪图)。

年代确认策略:
- era != '待OCR确认' → 按 era_code 归档到 {code}_{年代名}/
- era == '待OCR确认' → 归档到 A_待OCR确认/ (待后续人工审查)

用法:
    cd training
    python scripts/batch_crop.py                # 全量
    python scripts/batch_crop.py --limit 200    # 前 200 页 (测试)
    python scripts/batch_crop.py --skip-existing # 跳过已有裁剪图的记录
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / 'inference' / 'src'))

from utils.image_splitter import split_page  # noqa: E402

ERA_NAMES = {
    'A': '文化期', 'B': '商代', 'C': '春秋', 'D': '战国', 'E': '秦汉',
    'F': '三国两晋南北朝', 'G': '唐', 'H': '宋', 'I': '金元', 'J': '明',
    'K': '清', 'L': '民国', 'M': '出口创汇', 'N': '现代',
}
UNCONFIRMED_DIR = 'A_待OCR确认'


def main():
    ap = argparse.ArgumentParser(description='批量裁剪玉器页面图')
    ap.add_argument('--db', type=Path, default=REPO_ROOT / 'jade.db')
    ap.add_argument('--out', type=Path, default=REPO_ROOT / 'training_data')
    ap.add_argument('--manifest', type=Path,
                    default=REPO_ROOT / 'training_data' / 'training_manifest.jsonl')
    ap.add_argument('--limit', type=int, default=None, help='仅处理前 N 条 (测试)')
    ap.add_argument('--skip-existing', action='store_true',
                    help='跳过 manifest 中已有裁剪图的记录')
    args = ap.parse_args()

    con = sqlite3.connect(str(args.db), timeout=30)
    cur = con.cursor()
    rows = cur.execute(
        "SELECT p.id, p.era, p.era_code, p.authenticity, p.product_name, "
        "       p.label_code, i.file_path "
        "FROM jade_pieces p LEFT JOIN images i ON i.piece_id = p.id "
        "WHERE i.file_path IS NOT NULL"
    ).fetchall()
    print(f"待处理记录: {len(rows)} 条")

    existing = set()
    if args.manifest.exists():
        with open(args.manifest, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    existing.add(json.loads(line).get('piece_id'))

    manifest_f = open(args.manifest, 'a', encoding='utf-8')

    stats = {'cropped': 0, 'no_artifact': 0, 'missing_page': 0,
             'skipped_existing': 0, 'errors': 0}
    era_counts = {}
    t0 = time.time()

    for idx, (piece_id, era, era_code, auth, product_name,
              label_code, file_path) in enumerate(rows):
        if args.limit and idx >= args.limit:
            print(f"(达到 --limit {args.limit}, 停止)")
            break

        if args.skip_existing and piece_id in existing:
            stats['skipped_existing'] += 1
            continue

        page = REPO_ROOT / Path(str(file_path).replace('\\', '/'))
        if not page.exists():
            stats['missing_page'] += 1
            continue

        try:
            result = split_page(str(page))
        except Exception as e:
            stats['errors'] += 1
            if stats['errors'] <= 5:
                print(f"  ⚠ {page.name}: {e}")
            continue

        if not result['has_artifact'] or not result['artifact_path']:
            stats['no_artifact'] += 1
            continue

        # 归档目录
        if '待OCR确认' in str(era):
            era_dir = UNCONFIRMED_DIR
        else:
            name = ERA_NAMES.get(era_code or 'A', era_code or 'A')
            era_dir = f"{era_code}_{name}" if era_code else UNCONFIRMED_DIR

        out_dir = args.out / era_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        src = Path(result['artifact_path'])
        dst_name = f"{era_dir.split('_')[0]}_{piece_id[:8]}_{src.stem}_p_artifact.png"
        dst = out_dir / dst_name
        if dst.exists():
            dst_name = f"{era_dir.split('_')[0]}_{piece_id[:8]}_{src.stem}_{idx}_p_artifact.png"
            dst = out_dir / dst_name
        import shutil
        shutil.copy2(src, dst)

        rec = {
            'piece_id': piece_id,
            'label_code': label_code,
            'era_code': era_code or 'A',
            'era_name': era,
            'authenticity': auth,
            'product_name': product_name,
            'training_image': str(dst.relative_to(REPO_ROOT)).replace('\\', '/'),
            'original_page': str(page.relative_to(REPO_ROOT)).replace('\\', '/'),
            'cropped_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        manifest_f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        manifest_f.flush()

        # 同步回写数据库 (审查接口 /ocr/review/next 依赖此列)
        cur.execute('UPDATE jade_pieces SET training_image=? WHERE id=?',
                    (rec['training_image'], piece_id))
        if stats['cropped'] % 50 == 0:
            con.commit()

        era_counts[era_dir] = era_counts.get(era_dir, 0) + 1
        stats['cropped'] += 1

        if stats['cropped'] % 100 == 0:
            el = time.time() - t0
            print(f"  ... {stats['cropped']} 张已裁剪 "
                  f"({el:.0f}s, {stats['cropped']/el:.1f} 张/s)")

    manifest_f.close()
    con.commit()
    con.close()
    el = time.time() - t0
    print(f"\n完成: {stats} (耗时 {el:.0f}s)")
    print("年代分布:", dict(sorted(era_counts.items())))


if __name__ == '__main__':
    main()
