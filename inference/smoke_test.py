#!/usr/bin/env python3
"""
古玉鉴真 — 推理引擎冒烟测试

验证:
1. 预处理管线 (图片加载、tile 切分)
2. 数据库模型 (SQLite 创建 + CRUD)
3. 标签编码本地生成
4. FastAPI 服务启动
"""

import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime

# 添加路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

# ═══════════════════════════════════════════════════════
# TEST 1: 预处理管线
# ═══════════════════════════════════════════════════════
print("=" * 60)
print("TEST 1: 图片预处理")
print("=" * 60)

import numpy as np
from PIL import Image
from engine.preprocessing import (
    load_and_preprocess, load_and_tile_micro,
    validate_image, detect_is_micro,
)

# 创建测试图片
tmp_dir = tempfile.mkdtemp()
macro_img_path = os.path.join(tmp_dir, "test_macro.jpg")
micro_img_path = os.path.join(tmp_dir, "test_micro.jpg")

Image.fromarray(
    np.random.randint(0, 255, (800, 600, 3), dtype=np.uint8)
).save(macro_img_path)

Image.fromarray(
    np.random.randint(0, 255, (4000, 3000, 3), dtype=np.uint8)
).save(micro_img_path)

# 验证图片
valid, err = validate_image(macro_img_path)
assert valid, f"Macro image validation failed: {err}"
print(f"  ✓ 图片校验通过: {macro_img_path}")

# 宏观图预处理
macro_tensor = load_and_preprocess(macro_img_path, target_size=512)
assert macro_tensor.shape == (3, 512, 512), f"Shape: {macro_tensor.shape}"
assert macro_tensor.dtype == np.float32
print(f"  ✓ 宏观图预处理: {macro_tensor.shape}, dtype={macro_tensor.dtype}")

# 微距图 tile 切分
micro_tiles = load_and_tile_micro(micro_img_path)
assert len(micro_tiles) > 1, f"Expected multiple tiles, got {len(micro_tiles)}"
if micro_tiles:
    assert micro_tiles[0].shape == (3, 224, 224), f"Tile shape: {micro_tiles[0].shape}"
print(f"  ✓ 微距图 tile: {len(micro_tiles)} tiles, shape={micro_tiles[0].shape}")

# 微距检测
assert detect_is_micro(micro_img_path), "Should detect as micro"
assert not detect_is_micro(macro_img_path), "Should not detect macro as micro"
print(f"  ✓ 微距图自动检测正确")
print()

# ═══════════════════════════════════════════════════════
# TEST 2: 数据库模型
# ═══════════════════════════════════════════════════════
print("=" * 60)
print("TEST 2: 数据库模型 (SQLite)")
print("=" * 60)

from db.models import (
    create_database, JadePiece, Image as ImageModel,
    AuthResult, ModelVersion, gen_uuid,
)

db_path = os.path.join(tmp_dir, "test_jade.db")
session = create_database(db_path)

# 创建玉器记录
piece_id = gen_uuid()
now = datetime.now()
piece = JadePiece(
    id=piece_id,
    label_code="0_JY20260731000001_20260731100000_G_001",
    login_number="JY20260731000001",
    product_name="清和田玉三羊开泰摆件",
    material="和田白玉",
    authenticity="真老",
    era="清",
    era_code="K",
    source_type="馆藏",
    source_detail="故宫博物院",
    annotated_by="测试标注人",
    annotation_confidence=5,
    created_at=now,
)
session.add(piece)

# 创建图片记录
img = ImageModel(
    piece_id=piece_id,
    file_path="/tmp/test.jpg",
    image_type="macro",
    width=800,
    height=600,
    file_size_bytes=12345,
)
session.add(img)

# 创建鉴定结果
auth = AuthResult(
    piece_id=piece_id,
    label_code="0_JY20260731000001_20260731100000_G_001",
    model_version="0.1.0",
    predicted_era="清",
    era_code="K",
    era_probabilities=json.dumps({"A": 0.01, "K": 0.85}, ensure_ascii=False),
    predicted_authenticity="真老",
    authenticity_confidence=0.85,
    macro_features_analyzed=3,
    micro_features_analyzed=2,
    inference_time_ms=1523,
)
session.add(auth)
session.commit()

# 查询验证
pieces = session.query(JadePiece).all()
assert len(pieces) == 1
assert pieces[0].product_name == "清和田玉三羊开泰摆件"
assert pieces[0].material == "和田白玉"

images = session.query(ImageModel).all()
assert len(images) == 1

results = session.query(AuthResult).all()
assert len(results) == 1
assert results[0].predicted_era == "清"

print(f"  ✓ 玉器记录: {len(pieces)} 条")
print(f"  ✓ 图片记录: {len(images)} 条")
print(f"  ✓ 鉴定记录: {len(results)} 条")
print(f"  ✓ 标签编码: {pieces[0].label_code}")
print(f"  ✓ 品名: {pieces[0].product_name}")
print()

# ═══════════════════════════════════════════════════════
# TEST 3: 标签编码本地生成
# ═══════════════════════════════════════════════════════
print("=" * 60)
print("TEST 3: 标签编码生成 (推理端)")
print("=" * 60)

from utils.label_code import generate_label_code, generate_login_number, parse_label_code

now = datetime.now()
login = generate_login_number(now, 42)
code = generate_label_code('1', 'C', now, seq=3, daily_seq=42)
parsed = parse_label_code(code)

assert parsed['auth_code'] == '1'
assert parsed['era_code'] == 'C'
assert parsed['sequence'] == '003'

print(f"  ✓ 新仿编码: {code}")
print(f"  ✓ 总登录号: {login}")
print(f"  ✓ 解析正确")
print()

# ═══════════════════════════════════════════════════════
# TEST 4: FastAPI 应用结构
# ═══════════════════════════════════════════════════════
print("=" * 60)
print("TEST 4: FastAPI 应用结构")
print("=" * 60)

from fastapi.testclient import TestClient

# 测试时不需要加载模型，直接测试路由结构
from api.server import app

client = TestClient(app)

# 健康检查
resp = client.get("/health")
assert resp.status_code == 200
data = resp.json()
assert data["status"] == "ok"
print(f"  ✓ /health: {data}")

# 列出标注 (空数据库)
resp = client.get("/annotations")
assert resp.status_code == 200
print(f"  ✓ /annotations: status={resp.status_code}")

print()
print("=" * 60)
print("🎉 推理引擎测试全部通过！")
print("=" * 60)
print()
print("模块验证清单:")
print("  ✅ 图片预处理 (加载/EXIF/tile切分)")
print("  ✅ 微距图自动检测")
print("  ✅ SQLite 数据库 CRUD")
print("  ✅ 标签编码生成 (推理端)")
print("  ✅ FastAPI 应用结构 (/health, /annotations)")
