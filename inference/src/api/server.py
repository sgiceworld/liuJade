"""
古玉鉴真 — FastAPI 推理服务

本地推理 API 端点:
- POST /authenticate   — 执行鉴定
- POST /annotations     — 保存标注
- GET  /annotations     — 列出标注
- GET  /models/status   — 模型状态
- GET  /health          — 健康检查
"""

import sys
import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# 添加推理引擎到 path
sys.path.insert(0, str(Path(__file__).parent.parent))
from engine.inference import JadeInferenceEngine
from engine.preprocessing import validate_image
from db.models import create_database, JadePiece, Image as ImageModel, AuthResult


app = FastAPI(
    title="古玉鉴真 - 推理引擎",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本地 Electron 应用
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局推理引擎实例
engine: Optional[JadeInferenceEngine] = None
db_session = None


def get_engine() -> JadeInferenceEngine:
    global engine
    if engine is None:
        model_dir = Path(__file__).parent.parent.parent.parent / 'models'
        engine = JadeInferenceEngine(str(model_dir))
    return engine


# 项目唯一权威数据库 (绝对路径, 不受启动目录影响)
# batch_crop.py / prepare_data.py / run_ocr.py 均以根库为准
DB_PATH = Path(r"D:\liuJade\jade.db")


def get_db():
    global db_session
    if db_session is None:
        db_session = create_database(str(DB_PATH))
    return db_session


# ── 请求/响应模型 ──────────────────────────────────────

class AuthenticateRequest(BaseModel):
    macro_images: list[str]   # 宏观图路径或 base64
    micro_images: list[str]   # 微距图路径


class AnnotationRequest(BaseModel):
    piece_id: Optional[str] = None
    pieceId: Optional[str] = None
    authenticity: str
    era_code: Optional[str] = None
    eraCode: Optional[str] = None   # camelCase alias
    product_name: Optional[str] = None
    productName: Optional[str] = None
    material: Optional[str] = None
    dimensions: Optional[dict] = None
    source_type: Optional[str] = None
    sourceType: Optional[str] = None
    source_detail: Optional[str] = None
    sourceDetail: Optional[str] = None
    annotated_by: Optional[str] = None
    annotatedBy: Optional[str] = None
    annotation_confidence: Optional[int] = None
    annotationConfidence: Optional[int] = None
    image_paths: list[str] = []
    imagePaths: list[str] = []


# ── API 端点 ──────────────────────────────────────────

IMAGE_ROOT = Path(r"D:\liuJade")

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": engine is not None}

@app.get("/images/{filepath:path}")
def serve_image(filepath: str):
    """Serve scraped page images from disk."""
    clean = filepath.replace('\\', '/')
    full_path = IMAGE_ROOT / clean
    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"Image not found: {clean}")
    return FileResponse(full_path, media_type="image/png")

# ── Interactive OCR Review ──

@app.get("/ocr/review/next")
def ocr_review_next():
    """Get next un-reviewed record, run OCR, return image + parsed fields."""
    db = get_db()
    # Find next record that hasn't been reviewed (annotation_confidence < 3 or unset)
    piece = db.query(JadePiece).filter(
        JadePiece.annotation_confidence.is_(None) | (JadePiece.annotation_confidence < 3)
    ).order_by(JadePiece.created_at.asc()).first()

    if not piece:
        return {'success': True, 'data': None, 'message': 'All records reviewed'}

    # Get image path
    image_path = None
    if piece.images and len(piece.images) > 0:
        raw = piece.images[0].file_path
        image_path = raw.replace('\\', '/') if raw else None

    # Count remaining (same filter as the queue above)
    remaining = db.query(JadePiece).filter(
        (JadePiece.annotation_confidence == None) | (JadePiece.annotation_confidence < 3)
    ).count()

    # Review tag info
    review_count = getattr(piece, 'review_count', None) or 0
    review_status = getattr(piece, 'review_status', None) or 'imported'
    last_reviewed = getattr(piece, 'last_reviewed_at', None) or ''

    # 优先使用批量裁剪图 (batch_crop.py 产物, 已回写 training_image 列);
    # 无裁剪图时回退到现场 split_page 分割原始书页
    artifact_url = None
    text_url = None
    ocr_fields = {}

    crop_path = None
    crop_rel = (piece.training_image or '').replace('\\', '/')
    if crop_rel:
        cand = IMAGE_ROOT / crop_rel
        if cand.exists():
            crop_path = cand

    is_museum = (piece.source_type == '馆藏')

    if crop_path:
        # 批量裁剪图直接作为玉器照片; 原始书页作为文字描述上下文
        artifact_url = f'/images/{crop_rel}'
        if image_path and (IMAGE_ROOT / image_path.replace('\\', '/')).exists():
            text_url = f'/images/{image_path}'
    elif image_path:
        full_path = IMAGE_ROOT / image_path.replace('\\', '/')
        if full_path.exists():
            if is_museum:
                # 馆藏单物照片不适用书页分割算法, 直接用原图作玉器照片
                artifact_url = f'/images/{image_path}'
            else:
                try:
                    from utils.image_splitter import split_page
                    split = split_page(str(full_path))
                    if split['has_artifact']:
                        # Convert artifact/text paths to relative URLs
                        art_rel = Path(split['artifact_path']).relative_to(IMAGE_ROOT) if split['artifact_path'] else None
                        txt_rel = Path(split['text_path']).relative_to(IMAGE_ROOT) if split['text_path'] else None
                        artifact_url = f"/images/{str(art_rel).replace(chr(92), '/')}" if art_rel else None
                        text_url = f"/images/{str(txt_rel).replace(chr(92), '/')}" if txt_rel else None
                except Exception as e:
                    print(f"Split error: {e}")

            # Run OCR (skip if already reviewed — use cached results)
            if review_count == 0 and not is_museum:
                try:
                    from utils.ocr_engine import ocr_single_page
                    ocr_fields = ocr_single_page(str(full_path))
                except ImportError:
                    pass
                except Exception as e:
                    ocr_fields = {'error': str(e)}

    return {
        'success': True,
        'data': {
            'id': piece.id,
            'label_code': piece.label_code,
            'product_name': piece.product_name or '',
            'material': piece.material or '',
            'era': piece.era or '',
            'era_code': piece.era_code or '',
            'authenticity': piece.authenticity or '真老',
            'source_type': piece.source_type or '',
            'source_detail': piece.source_detail or '',
            'notes': piece.notes or '',
            'image_path': image_path,
            'image_url': f'/images/{image_path}' if image_path else None,
            'training_image': crop_rel or None,
            'artifact_url': artifact_url,
            'text_url': text_url,
            'remaining': remaining,
            'review_count': review_count,
            'review_status': review_status,
            'last_reviewed_at': last_reviewed,
            'ocr_suggestions': ocr_fields,
        },
    }


TRAINING_DATA_DIR = Path(r"D:\liuJade\training_data")
ANNOTATION_JSONL = Path(r"D:\liuJade\annotation_data\genuine.jsonl")


def _update_manifest_entry(piece_id: str, updates: dict):
    """原地更新 training_manifest.jsonl 中该 piece_id 的既有条目 (不追加新行)。"""
    manifest_file = TRAINING_DATA_DIR / "training_manifest.jsonl"
    if not manifest_file.exists():
        return
    try:
        lines = []
        with open(manifest_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    lines.append(line)
                    continue
                if rec.get('piece_id') == piece_id:
                    rec.update(updates)
                lines.append(json.dumps(rec, ensure_ascii=False))
        with open(manifest_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
    except Exception as e:
        print(f"Manifest update error: {e}")


@app.post("/ocr/review/confirm")
def ocr_review_confirm(data: dict):
    """Confirm/correct a reviewed record. Saves cropped artifact to training set."""
    db = get_db()
    piece = db.query(JadePiece).filter(JadePiece.id == data['id']).first()
    if not piece:
        raise HTTPException(status_code=404, detail="Record not found")

    authenticity = data.get('authenticity', piece.authenticity)
    era_code = data.get('era_code', piece.era_code)
    is_non_jade = (authenticity == '非玉器数据')
    training_image_path = None

    # Update fields from user confirmation
    piece.product_name = data.get('product_name', piece.product_name)
    piece.material = data.get('material', piece.material)
    piece.era = data.get('era', piece.era)
    piece.era_code = era_code
    piece.authenticity = authenticity
    piece.source_type = data.get('source_type', piece.source_type)
    piece.source_detail = data.get('source_detail', piece.source_detail)
    piece.notes = data.get('notes', piece.notes)
    piece.annotation_confidence = data.get('annotation_confidence', 5)
    piece.annotated_by = data.get('annotated_by', '人工确认')
    piece.updated_at = datetime.now()

    # ── Review tracking ──
    review_count = (getattr(piece, 'review_count', None) or 0) + 1
    piece.review_count = review_count
    piece.review_status = 'reviewed'
    piece.last_reviewed_at = datetime.now().isoformat()
    if not hasattr(piece, 'notes_extra'): pass
    try: piece.notes = f"{piece.notes or ''} [审查#{review_count}]".strip()
    except: pass

    if data.get('dimensions'):
        piece.dimensions = json.dumps(data['dimensions'], ensure_ascii=False)

    # ── Save cropped artifact to training set ──
    era_names_map = {'A':'文化期','B':'商代','C':'春秋','D':'战国','E':'秦汉',
        'F':'三国两晋南北朝','G':'唐','H':'宋','I':'金元','J':'明',
        'K':'清','L':'民国','M':'出口创汇','N':'现代'}
    era_cn = era_names_map.get(era_code, 'Unknown')
    training_image_path = None

    existing_crop = (piece.training_image or '').replace('\\', '/')
    existing_abs = IMAGE_ROOT / existing_crop if existing_crop else None

    if not is_non_jade and era_code and existing_abs and existing_abs.exists():
        # ── 批量裁剪图: 从 A_待OCR确认 迁移到确认年代目录, 修正文件名前缀 ──
        era_dir = TRAINING_DATA_DIR / f"{era_code}_{data.get('era') or piece.era or era_cn}"
        era_dir.mkdir(parents=True, exist_ok=True)

        import shutil
        new_name = existing_abs.name
        prefix = f"{era_code}_"
        if not new_name.startswith(prefix):
            parts = new_name.split('_', 1)
            new_name = prefix + (parts[1] if len(parts) > 1 else new_name)
        dest_path = era_dir / new_name
        if dest_path != existing_abs:
            if dest_path.exists():
                # 目标名冲突: 加序号
                i = 1
                while dest_path.exists():
                    dest_path = era_dir / f"{prefix}{new_name[len(prefix):].split('.')[0]}_{i}.png"
                    i += 1
            shutil.move(str(existing_abs), str(dest_path))
        training_image_path = str(dest_path.relative_to(IMAGE_ROOT)).replace('\\', '/')
    elif not is_non_jade and era_code:
        # ── 无批量裁剪图: 归档训练图 ──
        # 馆藏单物照片直接归档原图; 书页记录现场分割并复制裁剪图 (原流程)
        page_image = None
        if piece.images and len(piece.images) > 0:
            raw = piece.images[0].file_path
            page_image = IMAGE_ROOT / raw.replace('\\', '/')
            if not page_image.exists():
                page_image = None

        if page_image:
            is_museum = (piece.source_type == '馆藏')
            src_image = page_image if is_museum else \
                (page_image.parent / f"{page_image.stem}_artifact.png")
            if src_image.exists():
                era_dir = TRAINING_DATA_DIR / f"{era_code}_{data.get('era') or piece.era or era_cn}"
                era_dir.mkdir(parents=True, exist_ok=True)

                import shutil
                suffix = src_image.suffix or '.jpg'
                dest_name = f"{era_cn}_{piece.id[:8]}_{page_image.stem[:30]}{suffix}"
                dest_path = era_dir / dest_name
                shutil.copy2(src_image, dest_path)
                training_image_path = str(dest_path.relative_to(IMAGE_ROOT)).replace('\\', '/')

                # Append to training manifest
                manifest_file = TRAINING_DATA_DIR / "training_manifest.jsonl"
                manifest_entry = {
                    'piece_id': piece.id,
                    'label_code': piece.label_code,
                    'era_code': era_code,
                    'era_name': era_cn,
                    'authenticity': authenticity,
                    'material': piece.material,
                    'product_name': piece.product_name,
                    'training_image': training_image_path,
                    'original_page': str(page_image.relative_to(IMAGE_ROOT)),
                    'reviewed_at': datetime.now().isoformat(),
                }
                with open(manifest_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(manifest_entry, ensure_ascii=False) + '\n')

    # 修复: 此前赋值发生在计算 training_image_path 之前, 从未真正写入数据库
    if training_image_path:
        piece.training_image = training_image_path

    # ── 更新 manifest 中该记录的既有条目 (原地更新, 不重复追加) ──
    if existing_crop or training_image_path:
        _update_manifest_entry(piece.id, {
            'era_code': era_code,
            'era_name': piece.era or era_cn,
            'authenticity': authenticity,
            'product_name': piece.product_name,
            'material': piece.material,
            'training_image': (training_image_path or existing_crop).replace('\\', '/'),
            'reviewed_at': datetime.now().isoformat(),
        })

    db.commit()

    # ── Update JSONL manifest entry ──
    if training_image_path:
        try:
            jsonl_file = ANNOTATION_JSONL
            if jsonl_file.exists():
                records = []
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            records.append(json.loads(line))
                for r in records:
                    if r.get('image_paths') and piece.images and len(piece.images) > 0:
                        img = piece.images[0].file_path
                        if img and img.replace('\\', '/') in str(r.get('image_paths', [''])[0]).replace('\\', '/'):
                            r['training_image'] = training_image_path
                            r['era_code'] = era_code
                            r['era_name'] = data.get('era', r.get('era_name', ''))
                            r['authenticity'] = authenticity
                            r['product_name'] = piece.product_name
                            r['material'] = piece.material
                            r['annotation_confidence'] = 5
                            r['annotated_by'] = '人工确认'
                            break
                with open(jsonl_file, 'w', encoding='utf-8') as f:
                    for r in records:
                        f.write(json.dumps(r, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"JSONL update error: {e}")

    return {
        'success': True,
        'message': 'Saved' + (' + training image' if training_image_path else ''),
        'training_image': training_image_path,
    }


@app.post("/authenticate")
def authenticate(req: AuthenticateRequest):
    """执行古玉鉴定。"""
    # 验证图片
    for path in req.macro_images + req.micro_images:
        valid, err = validate_image(path)
        if not valid:
            raise HTTPException(status_code=400, detail=f"图片校验失败: {path} - {err}")

    try:
        result = get_engine().authenticate(
            macro_image_paths=req.macro_images,
            micro_image_paths=req.micro_images,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推理失败: {str(e)}")

    # 保存鉴定记录
    db = get_db()
    piece_id = str(uuid.uuid4())

    # 生成标签编码
    now = datetime.now()
    from utils.label_code import generate_label_code, generate_login_number

    # 简化: 用内存中的计数器代替真实数据库查询
    login_num = generate_login_number(now, 1)
    label_code = generate_label_code(
        '0' if result['predicted_authenticity'] == '真老' else '1',
        result['era_code'],
        now,
        seq=1,
        daily_seq=1,
    )

    piece = JadePiece(
        id=piece_id,
        label_code=label_code,
        login_number=login_num,
        authenticity=result['predicted_authenticity'],
        era=result['predicted_era'],
        era_code=result['era_code'],
        created_at=now,
    )
    db.add(piece)

    # 保存图片记录
    for path in req.macro_images:
        db.add(ImageModel(
            piece_id=piece_id,
            file_path=path,
            image_type='macro',
        ))
    for path in req.micro_images:
        db.add(ImageModel(
            piece_id=piece_id,
            file_path=path,
            image_type='micro',
        ))

    # 保存鉴定结果
    auth_result = AuthResult(
        piece_id=piece_id,
        label_code=label_code,
        model_version='0.1.0',
        predicted_era=result['predicted_era'],
        era_code=result['era_code'],
        era_probabilities=json.dumps(result['era_probabilities'], ensure_ascii=False),
        predicted_authenticity=result['predicted_authenticity'],
        authenticity_confidence=result['authenticity_confidence'],
        macro_features_analyzed=result['macro_features_analyzed'],
        micro_features_analyzed=result['micro_features_analyzed'],
        inference_time_ms=result['inference_time_ms'],
        created_at=now,
    )
    db.add(auth_result)
    db.commit()

    return {
        'success': True,
        'data': {
            'piece_id': piece_id,
            'label_code': label_code,
            **result,
        },
    }


@app.post("/annotations")
def save_annotation(req: AnnotationRequest):
    """保存手工标注。"""
    db = get_db()
    now = datetime.now()

    # Accept both camelCase and snake_case from frontend
    era_code = req.era_code or req.eraCode or 'A'
    product_name = req.product_name or req.productName or ''
    material = req.material or '和田白玉'
    source_type = req.source_type or req.sourceType or '著录'
    source_detail = req.source_detail or req.sourceDetail or ''
    annotated_by = req.annotated_by or req.annotatedBy or ''
    ann_confidence = req.annotation_confidence or req.annotationConfidence or 1
    img_paths = req.image_paths or req.imagePaths or []

    from utils.label_code import generate_label_code, generate_login_number

    # 查询当日全局序号
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    count = db.query(JadePiece).filter(
        JadePiece.created_at >= day_start
    ).count()

    daily_seq = count + 1

    # 查询当日同年代序号
    era_count = db.query(JadePiece).filter(
        JadePiece.created_at >= day_start,
        JadePiece.era_code == era_code,
    ).count()

    login_num = generate_login_number(now, daily_seq)
    label_code = generate_label_code(
        '0' if req.authenticity == '真老' else '1',
        era_code,
        now,
        seq=era_count + 1,
        daily_seq=daily_seq,
    )

    piece_id = req.piece_id or req.pieceId or str(uuid.uuid4())
    is_update = bool(req.piece_id or req.pieceId)

    era_names = {
        'A': '文化期','B': '商代','C': '春秋','D': '战国',
        'E': '秦汉','F': '三国两晋南北朝','G': '唐','H': '宋',
        'I': '金元','J': '明','K': '清','L': '民国',
        'M': '出口创汇','N': '现代',
    }

    if is_update:
        piece = db.query(JadePiece).filter(JadePiece.id == piece_id).first()
        if piece:
            piece.review_count = (piece.review_count or 0) + 1
            piece.review_status = 'annotated'
            piece.last_reviewed_at = now.isoformat()
            piece.product_name = product_name
            piece.material = material
            piece.source_type = source_type
            piece.source_detail = source_detail
            piece.authenticity = req.authenticity
            piece.era = era_names[era_code]
            piece.era_code = era_code
            piece.annotated_by = annotated_by
            piece.annotation_confidence = ann_confidence
            piece.updated_at = now
            if req.dimensions:
                piece.dimensions = json.dumps(req.dimensions, ensure_ascii=False)
    else:
        piece = JadePiece(
            id=piece_id, label_code=label_code, login_number=login_num,
            product_name=product_name, material=material,
            dimensions=json.dumps(req.dimensions, ensure_ascii=False) if req.dimensions else None,
            source_type=source_type, source_detail=source_detail,
            authenticity=req.authenticity, era=era_names[era_code], era_code=era_code,
            annotated_by=annotated_by, annotation_confidence=ann_confidence,
            created_at=now,
        )
        db.add(piece)

    # Only add image records for new pieces
    if not is_update:
        for path in img_paths:
            db.add(ImageModel(
            piece_id=piece_id,
            file_path=path,
            image_type='macro',  # 标注时简化
        ))

    db.commit()

    # ── Update JSONL (replace existing or append) ──
    data_dir = Path('./annotation_data')
    data_dir.mkdir(parents=True, exist_ok=True)
    jsonl_file = data_dir / 'genuine.jsonl'
    record = {
        'label_code': label_code, 'login_number': login_num,
        'product_name': product_name, 'material': material,
        'dimensions': req.dimensions, 'source_type': source_type,
        'source_detail': source_detail, 'authenticity': req.authenticity,
        'era_code': era_code, 'annotated_by': annotated_by,
        'annotation_confidence': ann_confidence, 'image_paths': img_paths,
        'created_at': now.isoformat(),
    }
    if is_update and jsonl_file.exists():
        # Read all lines, replace matching record
        lines = []
        updated = False
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                try:
                    r = json.loads(line)
                    if r.get('label_code') == piece.label_code:
                        lines.append(json.dumps({**r, **record}, ensure_ascii=False))
                        updated = True
                    else:
                        lines.append(line.rstrip('\n'))
                except:
                    lines.append(line.rstrip('\n'))
        if not updated:
            lines.append(json.dumps(record, ensure_ascii=False))
        with open(jsonl_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
    else:
        with open(jsonl_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
            f.flush()

    return {
        'success': True,
        'data': {
            'piece_id': piece_id,
            'label_code': label_code,
        },
    }


@app.get("/annotations")
def list_annotations(limit: int = 100, offset: int = 0):
    """列出所有标注记录（分页）。"""
    db = get_db()
    from sqlalchemy import func
    total = db.query(func.count(JadePiece.id)).scalar()

    pieces = db.query(JadePiece).order_by(
        JadePiece.review_count.desc(),
        JadePiece.annotation_confidence.desc(),
        JadePiece.created_at.desc(),
    ).offset(offset).limit(limit).all()

    result = []
    for p in pieces:
        image_paths = [img.file_path for img in p.images] if p.images else []
        result.append({
            'id': p.id,
            'label_code': p.label_code,
            'product_name': p.product_name,
            'material': p.material,
            'era': p.era,
            'era_code': p.era_code,
            'authenticity': p.authenticity,
            'source_type': p.source_type,
            'source_detail': p.source_detail,
            'annotated_by': p.annotated_by,
            'annotation_confidence': p.annotation_confidence,
            'notes': p.notes,
            'image_paths': image_paths,
            'training_image': getattr(p, 'training_image', None) or '',
            'review_count': getattr(p, 'review_count', None) or 0,
            'review_status': getattr(p, 'review_status', None) or 'imported',
            'last_reviewed_at': getattr(p, 'last_reviewed_at', None) or '',
            'created_at': p.created_at.isoformat() if p.created_at else None,
        })

    return {'success': True, 'data': result, 'total': total, 'limit': limit, 'offset': offset}


@app.get("/models/status")
def model_status():
    """获取当前加载的模型状态。"""
    try:
        eng = get_engine()
        version_info = eng.model_manager.get_version_info()
        return {
            'success': True,
            'data': {
                'loaded': True,
                'version': version_info.get('version', 'unknow'),
                'providers': eng.model_manager.providers,
            },
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
        }


def _append_to_annotation_file(
    req: AnnotationRequest,
    label_code: str,
    login_number: str,
    timestamp: datetime,
):
    """追加标注记录到 JSONL 文件。"""
    data_dir = Path('./annotation_data')
    data_dir.mkdir(parents=True, exist_ok=True)

    if req.authenticity == '真老':
        file_path = data_dir / 'genuine.jsonl'
    else:
        file_path = data_dir / 'fake.jsonl'

    record = {
        'label_code': label_code,
        'login_number': login_num,
        'product_name': product_name,
        'material': material,
        'dimensions': req.dimensions,
        'source_type': source_type,
        'source_detail': source_detail,
        'authenticity': req.authenticity,
        'era_code': era_code,
        'annotated_by': annotated_by,
        'annotation_confidence': ann_confidence,
        'image_paths': img_paths,
        'created_at': now.isoformat(),
    }

    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')
        f.flush()


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8720)
