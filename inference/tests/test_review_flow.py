#!/usr/bin/env python3
"""
古玉鉴真 — 审查流程回归测试 (沙箱隔离, 不动真实数据)

验证 /ocr/review/next + /ocr/review/confirm 的裁剪图闭环:
1. next 优先返回批量裁剪图 (training_image), 而非原始书页
2. confirm 确认年代后: 裁剪图从 A_待OCR确认 迁移到 {年代} 目录
   + 文件名前缀修正 + DB training_image 更新 + manifest 原地更新
3. 非玉器确认: 文件保留原处, manifest 标记 authenticity

运行: cd inference && python tests/test_review_flow.py
"""

import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # d:\liuJade
sys.path.insert(0, str(REPO_ROOT / 'inference' / 'src'))

import api.server as server  # noqa: E402


def _pick_queue_record(db: Path, exclude: set) -> dict:
    """选一条队列中 (conf<3) 且已有裁剪图的记录。"""
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    rows = cur.execute(
        "SELECT id, label_code, era, era_code, training_image FROM jade_pieces "
        "WHERE training_image IS NOT NULL AND training_image != '' "
        "AND (annotation_confidence IS NULL OR annotation_confidence < 3)"
    ).fetchall()
    con.close()
    for r in rows:
        if r[0] not in exclude and (REPO_ROOT / r[4].replace('\\', '/')).exists():
            return {'id': r[0], 'label_code': r[1], 'era': r[2],
                    'era_code': r[3], 'training_image': r[4].replace('\\', '/')}
    raise SystemExit('沙箱数据库中没有可用的队列记录')


def _backdate(db: Path, piece_id: str, date: str):
    con = sqlite3.connect(str(db))
    con.execute('UPDATE jade_pieces SET created_at=? WHERE id=?', (date, piece_id))
    con.commit()
    con.close()


def main():
    tmp = Path(tempfile.mkdtemp(prefix='review_flow_test_'))
    sandbox_db = tmp / 'jade.db'
    sandbox_data = tmp / 'training_data'
    sandbox_img = tmp
    shutil.copy2(REPO_ROOT / 'jade.db', sandbox_db)

    # ── 沙箱替换 server 的硬编码路径 ──
    server.DB_PATH = sandbox_db
    server.IMAGE_ROOT = sandbox_img
    server.TRAINING_DATA_DIR = sandbox_data
    server.ANNOTATION_JSONL = tmp / 'genuine.jsonl'
    server.db_session = None
    (tmp / 'genuine.jsonl').write_text('', encoding='utf-8')

    # ── 准备记录 1: 确认年代 (I=金元) ──
    rec1 = _pick_queue_record(sandbox_db, set())
    _backdate(sandbox_db, rec1['id'], '2000-01-01T00:00:00')
    rel1 = rec1['training_image']
    (sandbox_img / rel1).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / rel1, sandbox_img / rel1)

    # ── 准备记录 2: 非玉器 ──
    rec2 = _pick_queue_record(sandbox_db, {rec1['id']})
    _backdate(sandbox_db, rec2['id'], '2000-01-02T00:00:00')
    rel2 = rec2['training_image']
    (sandbox_img / rel2).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / rel2, sandbox_img / rel2)

    # ── manifest: 只放这两条 (镜像真实 manifest 对应条目) ──
    manifest_in = {}
    with open(REPO_ROOT / 'training_data' / 'training_manifest.jsonl', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get('piece_id') in (rec1['id'], rec2['id']):
                manifest_in.setdefault(r['piece_id'], r)
    manifest_file = sandbox_data / 'training_manifest.jsonl'
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_file, 'w', encoding='utf-8') as f:
        for pid in (rec1['id'], rec2['id']):
            f.write(json.dumps(manifest_in[pid], ensure_ascii=False) + '\n')
    manifest_lines_before = 2

    errors = []
    n_checks = [0]

    def check(name, cond, detail=''):
        n_checks[0] += 1
        print(f"  {'✓' if cond else '✗'} {name}" + (f' — {detail}' if detail else ''))
        if not cond:
            errors.append(name)
        return cond

    # ── 1. next 应返回记录 1 及其裁剪图 ──
    r1 = server.ocr_review_next()
    d1 = r1.get('data') or {}
    check('next 返回记录 1', d1.get('id') == rec1['id'], d1.get('id'))
    check('next 返回裁剪图路径',
          d1.get('training_image') == rel1, d1.get('training_image'))
    check('artifact_url 指向裁剪图',
          d1.get('artifact_url') == f'/images/{rel1}', d1.get('artifact_url'))

    # ── 2. confirm: 确认金元 → 迁移 + 前缀修正 + DB + manifest ──
    resp = server.ocr_review_confirm({
        'id': rec1['id'], 'authenticity': '真老',
        'era_code': 'I', 'era': '金元',
    })
    new_rel = 'training_data/I_金元/' + 'I_' + Path(rel1).name.split('_', 1)[1]
    check('confirm 返回成功', resp.get('success') is True, str(resp))
    check('旧文件已迁出', not (sandbox_img / rel1).exists(), rel1)
    check('新文件在年代目录且前缀修正',
          (sandbox_img / new_rel).exists(), new_rel)

    con = sqlite3.connect(str(sandbox_db))
    row = con.execute(
        'SELECT era, era_code, training_image, review_count, review_status '
        'FROM jade_pieces WHERE id=?', (rec1['id'],)).fetchone()
    con.close()
    check('DB: 年代/编码已更新', row[0] == '金元' and row[1] == 'I', f'{row[0]}/{row[1]}')
    check('DB: training_image 已更新', row[2] == new_rel, row[2])
    check('DB: review_count=1, reviewed', row[3] == 1 and row[4] == 'reviewed',
          f'{row[3]}/{row[4]}')

    with open(manifest_file, encoding='utf-8') as f:
        mlines = [json.loads(l) for l in f if l.strip()]
    m1 = [m for m in mlines if m['piece_id'] == rec1['id']]
    check('manifest: 原地更新未追加', len(mlines) == manifest_lines_before and len(m1) == 1,
          f'{len(mlines)} 行')
    check('manifest: 条目年代/路径已更新',
          m1 and m1[0]['era_code'] == 'I' and m1[0]['training_image'] == new_rel,
          m1 and f"{m1[0]['era_code']}/{m1[0]['training_image']}")

    # ── 3. next 应轮到记录 2 (记录 1 已出队) ──
    r2 = server.ocr_review_next()
    d2 = r2.get('data') or {}
    check('next 返回记录 2', d2.get('id') == rec2['id'], d2.get('id'))

    # ── 4. confirm: 非玉器 → 文件不动, manifest 标记 ──
    resp2 = server.ocr_review_confirm({
        'id': rec2['id'], 'authenticity': '非玉器数据',
        'era_code': rec2['era_code'], 'era': rec2['era'],
    })
    check('非玉器 confirm 成功', resp2.get('success') is True, str(resp2))
    check('非玉器: 文件保留原处', (sandbox_img / rel2).exists(), rel2)
    with open(manifest_file, encoding='utf-8') as f:
        mlines2 = [json.loads(l) for l in f if l.strip()]
    m2 = [m for m in mlines2 if m['piece_id'] == rec2['id']]
    check('非玉器: manifest 标记', m2 and m2[0]['authenticity'] == '非玉器数据',
          m2 and m2[0]['authenticity'])

    # ── 收尾 ──
    shutil.rmtree(tmp, ignore_errors=True)
    print()
    if errors:
        print(f"FAILED: {len(errors)} 项未通过: {errors}")
        sys.exit(1)
    print(f"全部 {n_checks[0]} 项检查通过 ✓ (沙箱已清理)")


if __name__ == '__main__':
    main()
