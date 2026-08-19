#!/usr/bin/env python3
"""
古玉鉴真 — 训练数据准备

将 training_manifest.jsonl (裁剪图清单) + jade.db (标注数据库)
转换为 JadeMultiViewDataset 期望的布局:

    data_root/
    ├── annotations.json      # 标注清单 (eras + images)
    ├── annotations_val.json  # 验证集 (按年代分层抽样)
    └── images/               # 拷贝的裁剪图

用法:
    cd training
    python scripts/prepare_data.py \
        --manifest ../training_data/training_manifest.jsonl \
        --db ../jade.db \
        --output ../training/data
"""

import argparse
import json
import shutil
import sqlite3
from pathlib import Path

from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def load_db_labels(db_path: Path) -> dict:
    """从 jade.db 读取每件玉器的权威标注 (era/era_code/authenticity)。"""
    if not db_path.exists():
        return {}
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    rows = cur.execute(
        "SELECT id, era, era_code, authenticity, product_name, label_code "
        "FROM jade_pieces"
    ).fetchall()
    con.close()
    return {
        r[0]: {
            'era': r[1], 'era_code': r[2], 'authenticity': r[3],
            'product_name': r[4], 'label_code': r[5],
        }
        for r in rows
    }


def main():
    ap = argparse.ArgumentParser(description='准备古玉鉴真训练数据')
    ap.add_argument('--manifest', type=Path,
                    default=REPO_ROOT / 'training_data' / 'training_manifest.jsonl')
    ap.add_argument('--db', type=Path, default=REPO_ROOT / 'jade.db')
    ap.add_argument('--output', type=Path,
                    default=REPO_ROOT / 'training' / 'data')
    ap.add_argument('--include-unconfirmed', action='store_true',
                    help='包含 era="待OCR确认" 的记录 (默认跳过)')
    ap.add_argument('--val-split', type=float, default=0.0,
                    help='验证集比例 (0-1, 按年代分层)')
    ap.add_argument('--no-copy', action='store_true',
                    help='不拷贝图片, 仅生成 annotations.json (images 已就位)')
    args = ap.parse_args()

    if not args.manifest.exists():
        raise SystemExit(f"manifest 不存在: {args.manifest}")

    db_labels = load_db_labels(args.db)
    print(f"DB 标注记录: {len(db_labels)} 条")

    # ── 收集有效样本 ──
    pieces = {}
    skipped = defaultdict(int)
    with open(args.manifest, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)

            piece_id = rec.get('piece_id')
            image = rec.get('training_image', '')
            if not piece_id or not image:
                skipped['no_image'] += 1
                continue

            # 图片路径 (manifest 中为仓库根相对路径)
            image = Path(str(image).replace('\\', '/'))
            image_abs = REPO_ROOT / image
            if not image_abs.exists():
                skipped['file_missing'] += 1
                continue

            # DB 为权威标注来源; manifest 兜底
            label = db_labels.get(piece_id, rec)
            era = label.get('era') or rec.get('era_name', '')
            if '待OCR确认' in str(era) and not args.include_unconfirmed:
                skipped['unconfirmed'] += 1
                continue
            auth = label.get('authenticity') or rec.get('authenticity', '')
            if '非玉器' in str(auth):
                skipped['non_jade'] += 1
                continue

            era_code = label.get('era_code') or rec.get('era_code', 'A')
            if era_code not in 'ABCDEFGHIJKLMN':
                skipped['bad_era'] += 1
                continue

            label_code = (label.get('label_code') or rec.get('label_code')
                          or f"{piece_id}")
            pieces.setdefault(piece_id, {
                'label_code': label_code,
                'era': era,
                'era_code': era_code,
                'authenticity': auth,
                'product_name': label.get('product_name') or rec.get('product_name', ''),
                'images': [],
            })
            pieces[piece_id]['images'].append(image_abs)

    print(f"有效样本 (件): {len(pieces)}")
    if skipped:
        print(f"跳过: {dict(skipped)}")

    # ── 拷贝图片 + 生成 annotations ──
    out_root = args.output
    images_dir = out_root / 'images'
    images_dir.mkdir(parents=True, exist_ok=True)

    annotations = []
    for piece_id, piece in pieces.items():
        ann_images = []
        for i, src in enumerate(piece['images']):
            dst_rel = f"{piece['era_code']}_{piece_id[:8]}_{i}{src.suffix.lower()}"
            dst = images_dir / dst_rel
            if not args.no_copy and not dst.exists():
                shutil.copy2(src, dst)
            ann_images.append(dst_rel)
        annotations.append({
            'label_code': piece['label_code'],
            'era': piece['era'],
            'era_code': piece['era_code'],
            'authenticity': piece['authenticity'],
            'product_name': piece['product_name'],
            'images': ann_images,
            'image_types': ['macro'] * len(ann_images),
        })

    # ── 按年代分层拆分 val ──
    by_era = defaultdict(list)
    for ann in annotations:
        by_era[ann['era_code']].append(ann)

    train_anns, val_anns = [], []
    for era, anns in by_era.items():
        n_val = max(0, int(round(len(anns) * args.val_split)))
        # 每年代至少留 1 条训练 (除非只有 1 条且 val>0 时不强制)
        if n_val >= len(anns) and len(anns) > 1:
            n_val = len(anns) - 1
        if args.val_split > 0 and len(anns) > 1:
            val_anns.extend(anns[:n_val])
            train_anns.extend(anns[n_val:])
        else:
            train_anns.extend(anns)

    with open(out_root / 'annotations.json', 'w', encoding='utf-8') as f:
        json.dump(train_anns, f, ensure_ascii=False, indent=2)
    print(f"annotations.json: {len(train_anns)} 训练样本")

    if val_anns:
        with open(out_root / 'annotations_val.json', 'w', encoding='utf-8') as f:
            json.dump(val_anns, f, ensure_ascii=False, indent=2)
        print(f"annotations_val.json: {len(val_anns)} 验证样本")

    # 年代分布
    dist = defaultdict(int)
    for ann in train_anns:
        dist[ann['era_code']] += 1
    print("训练集年代分布:", dict(sorted(dist.items())))


if __name__ == '__main__':
    main()
