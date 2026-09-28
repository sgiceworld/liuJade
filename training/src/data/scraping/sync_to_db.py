#!/usr/bin/env python3
"""Sync genuine.jsonl records to SQLite database."""

import sys, json, uuid
from pathlib import Path
from datetime import datetime

sys.path.insert(0, r'D:\liuJade\inference\src')
from db.models import create_database, JadePiece, Image as ImageModel

def sync():
    jsonl = Path(r'D:\liuJade\annotation_data\genuine.jsonl')
    # 唯一权威数据库 (与 inference/src/api/server.py 的 DB_PATH 一致)
    db_path = r'D:\liuJade\jade.db'

    records = []
    with open(jsonl, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    print(f'Loaded {len(records)} records from JSONL')

    # Count OCR'd records
    ocred = sum(1 for r in records if r.get('annotation_confidence', 0) >= 3)
    print(f'OCR processed: {ocred}')

    # Sample some OCR'd records
    ocred_records = [r for r in records if r.get('annotation_confidence', 0) >= 3]
    if ocred_records:
        print('\nSample OCR results:')
        for r in ocred_records[:5]:
            print(f"  {r.get('product_name','?')[:40]}")
            print(f"    era={r.get('era_name','?')}({r.get('era_code','?')}) mat={r.get('material','?')}")
            if r.get('dimensions'): print(f"    dims={r.get('dimensions')}")

    # Import to root DB only
    for db in [db_path]:
        # Delete existing data
        session = create_database(db)
        session.query(ImageModel).delete()
        session.query(JadePiece).delete()
        session.commit()

        now = datetime.now()
        for i, rec in enumerate(records):
            piece_id = str(uuid.uuid4())
            login_num = f'JY{now.strftime("%Y%m%d")}{i+1:06d}'
            label_code = f'0_{login_num}_{now.strftime("%Y%m%d%H%M%S")}_{rec.get("era_code","A")}_{(i%1000)+1:03d}'

            piece = JadePiece(
                id=piece_id, label_code=label_code, login_number=login_num,
                product_name=rec.get('product_name', ''),
                material=rec.get('material', '和田白玉'),
                dimensions=json.dumps(rec.get('dimensions')) if rec.get('dimensions') else None,
                source_type=rec.get('source_type', '著录'),
                source_detail=rec.get('source_detail', ''),
                authenticity=rec.get('authenticity', '真老'),
                era=rec.get('era_name', '待OCR确认'),
                era_code=rec.get('era_code', 'A'),
                annotated_by=rec.get('annotated_by', ''),
                annotation_confidence=rec.get('annotation_confidence', 1),
                notes=rec.get('notes', ''),
                created_at=now,
            )
            session.add(piece)
            for img_path in rec.get('image_paths', []):
                session.add(ImageModel(piece_id=piece_id, file_path=str(img_path), image_type='macro'))

            if (i+1) % 500 == 0:
                session.commit()
                print(f'  DB {db}: {i+1}/{len(records)}')

        session.commit()
        print(f'  DB {db}: Done ({len(records)} records)')

    print('\nSync complete. Restart API server to see updates.')

if __name__ == '__main__':
    sync()
