#!/usr/bin/env python3
"""
古玉鉴真 — 博物馆爬取数据导入标注库 (append-only)

读 scraped_data/{museum}/metadata.jsonl (爬虫产物, 每行一张图),
按藏品聚合后生成标注记录, append 到:
- annotation_data/genuine.jsonl (标注 JSONL)
- jade.db (jade_pieces + images, 权威数据库)

安全约束:
- 纯追加, 绝不 DELETE/清表 (sync_to_db.py 会清表, 禁止用于本流程)
- 幂等: scraped_data/{museum}/import_state.json 记录已导入的 phash
- era 已映射 → confidence=4 / annotated_by='API映射'
- era 未映射 → era='待OCR确认', confidence=1 (进人工审查队列)

用法:
    cd training
    python src/data/scraping/import_museum_data.py --museum met --dry-run
    python src/data/scraping/import_museum_data.py --museum met --limit 10
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]  # training/src/data/scraping → 仓库根
sys.path.insert(0, str(REPO_ROOT / 'training' / 'src'))
sys.path.insert(0, str(REPO_ROOT / 'inference' / 'src'))

from db.models import create_database, JadePiece, Image as ImageModel  # noqa: E402
from utils.label_code import generate_login_number, generate_label_code  # noqa: E402

SCRAPED_ROOT = REPO_ROOT / 'scraped_data'
GENUINE_JSONL = REPO_ROOT / 'annotation_data' / 'genuine.jsonl'
DEFAULT_DB = REPO_ROOT / 'jade.db'


def load_metadata(museum: str) -> list:
    """读取爬虫产出的 metadata.jsonl (每行一张图)。"""
    meta_file = SCRAPED_ROOT / museum / 'metadata.jsonl'
    if not meta_file.exists():
        raise SystemExit(f"metadata 不存在: {meta_file} (先跑 run_spider.py)")
    rows = []
    with open(meta_file, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_import_state(museum: str) -> set:
    """已导入的 phash 集合 (幂等)。"""
    state_file = SCRAPED_ROOT / museum / 'import_state.json'
    if not state_file.exists():
        return set()
    with open(state_file, encoding='utf-8') as f:
        return set(json.load(f).get('imported_phash', []))


def save_import_state(museum: str, imported: set):
    state_file = SCRAPED_ROOT / museum / 'import_state.json'
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump({'imported_phash': sorted(imported),
                   'updated_at': datetime.now().isoformat()},
                  f, ensure_ascii=False, indent=2)


def group_by_item(rows: list) -> dict:
    """按藏品 (item_id) 聚合图片行; 无 item_id 的图单独成件。"""
    groups = {}
    orphans = 0
    for r in rows:
        iid = r.get('item_id')
        if iid:
            groups.setdefault(str(iid), []).append(r)
        else:
            groups[f'_orphan_{orphans}'] = [r]
            orphans += 1
    return groups


def build_annotation_record(item_id: str, group: list, now: datetime,
                            login_number: str, label_code: str) -> dict:
    """聚合组 → 标注记录 (对齐 genuine.jsonl 现有字段)。"""
    from data.scraping.spiders.era_map import map_material
    first = group[0]
    era_code = first.get('era_mapped_code') or 'A'
    era_name = first.get('era_mapped_name') or '待OCR确认'
    material = map_material(first.get('material_raw') or '')
    if not material:
        material = '和田白玉'
    title = first.get('title') or ''
    confidence = 4 if first.get('era_mapped_code') else 1
    notes_parts = []
    if first.get('accession_number'):
        notes_parts.append(f"馆藏编号: {first['accession_number']}")
    if first.get('era_approx'):
        notes_parts.append('年代为近似映射 (西周/东周), 需人工确认')
    if not first.get('era_mapped_code'):
        notes_parts.append('年代待OCR确认')
    notes_parts.append(f"license: {first.get('license', '')}")
    notes = '; '.join(p for p in notes_parts if p) or None

    image_paths = []
    for r in group:
        p = Path(r['file_path'])
        try:
            rel = p.relative_to(REPO_ROOT)
        except ValueError:
            continue  # 异常路径跳过
        image_paths.append(str(rel).replace('\\', '/'))

    era_prefix = '' if era_name == '待OCR确认' else era_name
    product_name = f"{era_prefix}{material}{title[:30]}".strip() or '未命名'

    return {
        'label_code': label_code,
        'login_number': login_number,
        'authenticity': '真老',
        'era_code': era_code,
        'era_name': era_name,
        'product_name': product_name,
        'material': material,
        'source_type': '馆藏',
        'source_detail': f"{first.get('museum_cn', '')} | {first.get('page_url', '')}".strip(' |'),
        'annotation_confidence': confidence,
        'annotated_by': 'API映射',
        'image_paths': image_paths,
        'notes': notes,
        'created_at': now.isoformat(),
    }


def _counter(base_key: str, counter: dict):
    counter[base_key] = counter.get(base_key, 0) + 1
    return counter[base_key]


def import_museum(museum: str, db_path: str = None, dry_run: bool = False,
                  limit: int = None) -> dict:
    """导入指定博物馆的爬取数据。返回统计 dict。"""
    db_path = db_path or str(DEFAULT_DB)
    rows = load_metadata(museum)
    imported_state = load_import_state(museum)
    groups = group_by_item(rows)

    # 过滤: 已导入的组 (组内任一图 phash 已导入即视为已处理)
    fresh_groups = {}
    for iid, grp in groups.items():
        phashes = [r.get('phash') for r in grp]
        if any(p in imported_state for p in phashes):
            continue
        fresh_groups[iid] = grp

    if limit:
        fresh_groups = dict(list(fresh_groups.items())[:limit])

    print(f"{museum}: 元数据 {len(rows)} 行 → {len(groups)} 件藏品, "
          f"本次导入 {len(fresh_groups)} 件 (已导入 {len(groups) - len(fresh_groups)} 件)")
    if dry_run:
        for iid, grp in list(fresh_groups.items())[:10]:
            r = grp[0]
            print(f"  [dry-run] {r.get('title', '?')[:40]} | "
                  f"era={r.get('era_mapped_name') or '待OCR确认'} | {len(grp)} 图")
        return {'dry_run': True, 'to_import': len(fresh_groups)}

    if not fresh_groups:
        print("  无新数据")
        return {'imported': 0, 'skipped_conflict': 0}

    session = create_database(db_path)
    now = datetime.now()
    stats = {'imported': 0, 'skipped_conflict': 0, 'images': 0}
    # 每日流水从库中今日已有记录数 + 1 起算, 避免同日重复登录号
    today_prefix = f"JY{now.strftime('%Y%m%d')}"
    from sqlalchemy import func
    base_seq = session.query(func.count(JadePiece.id)).filter(
        JadePiece.login_number.like(f"{today_prefix}%")).scalar() or 0
    counter = {'login': base_seq, 'era': {}}
    new_phash = set()

    jsonl_f = open(GENUINE_JSONL, 'a', encoding='utf-8')

    try:
        for iid, grp in fresh_groups.items():
            # 登录号/标签编码: 单一每日流水, 两处共用同一 daily_seq
            era_code = grp[0].get('era_mapped_code') or 'A'
            daily_seq = _counter('login', counter)
            label_code = generate_label_code(
                '0', era_code, now,
                seq=_counter(f"era_{era_code}", counter['era']),
                daily_seq=daily_seq,
            )
            login_number = generate_login_number(now, daily_seq)
            rec = build_annotation_record(iid, grp, now, login_number, label_code)

            # 冲突检测 (label_code 或 login_number 已存在则跳过)
            exist = session.query(JadePiece).filter(
                (JadePiece.label_code == label_code) |
                (JadePiece.login_number == login_number)
            ).first()
            if exist:
                stats['skipped_conflict'] += 1
                continue

            piece = JadePiece(
                id=iid,  # 用馆方 item_id 作主键, 天然幂等
                label_code=label_code,
                login_number=login_number,
                product_name=rec['product_name'],
                material=rec['material'],
                source_type='馆藏',
                source_detail=rec['source_detail'],
                authenticity='真老',
                era=rec['era_name'],
                era_code=rec['era_code'],
                annotated_by='API映射',
                annotation_confidence=rec['annotation_confidence'],
                notes=rec['notes'],
                created_at=now,
                updated_at=now,
            )
            session.add(piece)
            for img_path in rec['image_paths']:
                session.add(ImageModel(piece_id=iid, file_path=img_path,
                                       image_type='macro'))
                stats['images'] += 1

            for r in grp:
                if r.get('phash'):
                    new_phash.add(r['phash'])

            # 追加 JSONL
            jsonl_f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            jsonl_f.flush()

            stats['imported'] += 1
            if stats['imported'] % 10 == 0:
                session.commit()
                print(f"  ... {stats['imported']} 件")

        session.commit()
        imported_state |= new_phash
        save_import_state(museum, imported_state)
    finally:
        jsonl_f.close()

    print(f"完成: 导入 {stats['imported']} 件 / {stats['images']} 图, "
          f"冲突跳过 {stats['skipped_conflict']}")
    return stats


def main():
    ap = argparse.ArgumentParser(description='博物馆数据导入标注库 (append-only)')
    ap.add_argument('--museum', type=str, required=True, help='爬虫 ID (如 met)')
    ap.add_argument('--db', type=Path, default=DEFAULT_DB)
    ap.add_argument('--limit', type=int, default=None, help='仅导入前 N 件')
    ap.add_argument('--dry-run', action='store_true', help='只统计不写入')
    args = ap.parse_args()

    import_museum(args.museum, db_path=str(args.db),
                  dry_run=args.dry_run, limit=args.limit)


if __name__ == '__main__':
    main()
