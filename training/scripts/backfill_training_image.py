#!/usr/bin/env python3
"""
古玉鉴真 — training_image 回写数据库

batch_crop.py 历史版本只把裁剪图写入 training_manifest.jsonl,
未更新 jade.db 的 jade_pieces.training_image 列。
本脚本按 piece_id 匹配 manifest, 将裁剪图路径回写数据库,
使审查接口 /ocr/review/next 能直接返回批量裁剪图。

用法:
    cd training
    python scripts/backfill_training_image.py
    python scripts/backfill_training_image.py --manifest ../training_data/training_manifest.jsonl --db ../jade.db
"""

import argparse
import json
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def main():
    ap = argparse.ArgumentParser(description='将 manifest 中的裁剪图路径回写 jade.db')
    ap.add_argument('--manifest', type=Path,
                    default=REPO_ROOT / 'training_data' / 'training_manifest.jsonl')
    ap.add_argument('--db', type=Path, default=REPO_ROOT / 'jade.db')
    ap.add_argument('--dry-run', action='store_true', help='只统计不写库')
    args = ap.parse_args()

    if not args.manifest.exists():
        raise SystemExit(f"manifest 不存在: {args.manifest}")
    if not args.db.exists():
        raise SystemExit(f"数据库不存在: {args.db}")

    # piece_id -> 最后一条 manifest 记录的 training_image (同 id 后写覆盖)
    wanted = {}
    dupes = 0
    with open(args.manifest, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            pid = rec.get('piece_id')
            img = rec.get('training_image', '')
            if not pid or not img:
                continue
            if pid in wanted:
                dupes += 1
            wanted[pid] = img.replace('\\', '/')

    print(f"manifest 记录: {len(wanted)} 条 (重复 piece_id: {dupes})")

    # 核对文件存在性
    missing = [pid for pid, img in wanted.items()
               if not (REPO_ROOT / img).exists()]
    print(f"文件缺失: {len(missing)} 条")

    con = sqlite3.connect(str(args.db))
    cur = con.cursor()
    n_total = cur.execute('SELECT COUNT(*) FROM jade_pieces').fetchone()[0]
    n_match = n_update = 0
    for pid, img in wanted.items():
        row = cur.execute('SELECT training_image FROM jade_pieces WHERE id=?',
                          (pid,)).fetchone()
        if row is None:
            continue  # manifest 中有、库里无 (不应发生)
        n_match += 1
        cur_img = (row[0] or '').replace('\\', '/')
        if cur_img == img:
            continue
        if not args.dry_run:
            cur.execute('UPDATE jade_pieces SET training_image=? WHERE id=?',
                        (img, pid))
        n_update += 1

    if not args.dry_run:
        con.commit()
    con.close()

    print(f"数据库记录: {n_total}, 匹配到: {n_match}, 需更新: {n_update}"
          f"{' (dry-run, 未写入)' if args.dry_run else ' — 已写入'}")


if __name__ == '__main__':
    main()
