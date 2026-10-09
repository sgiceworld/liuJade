#!/usr/bin/env python3
"""
古玉鉴真 — 移动端 API 回归测试 (沙箱隔离, 不动真实数据)

验证 Phase 0 新增端点:
1. POST /images/upload → 绝对路径落盘, 可直接喂 /authenticate
2. upload → authenticate 全链路 (真实引擎)
3. GET /annotations 过滤 (era_code/authenticity/source_type/q)
4. GET /images ?w= 缩略图 + 路径逃逸 403
5. GET /models/download 白名单 + /models/status 清单

运行: cd inference && python -m pytest tests/test_mobile_api.py -v
"""

import io
import os
import sys
import tempfile
from pathlib import Path

import pytest
from PIL import Image as PILImage

REPO_ROOT = Path(__file__).resolve().parents[2]  # d:\liuJade
sys.path.insert(0, str(REPO_ROOT / 'inference' / 'src'))

import api.server as server  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(server.app)


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """沙箱: 临时 IMAGE_ROOT + 临时 DB, 测试后重置全局会话。"""
    monkeypatch.setattr(server, 'IMAGE_ROOT', tmp_path)
    monkeypatch.setattr(server, 'MOBILE_MODEL_DIR',
                        tmp_path / 'models' / 'mobile' / 'quantized')
    monkeypatch.setattr(server, 'DB_PATH', tmp_path / 'test.db')
    server.db_session = None  # 重置缓存会话
    yield tmp_path
    server.db_session = None


def _make_image(width=640, height=800, ext='jpg') -> bytes:
    img = PILImage.new('RGB', (width, height), (120, 160, 90))
    buf = io.BytesIO()
    fmt = 'PNG' if ext == 'png' else 'JPEG'
    img.save(buf, format=fmt)
    return buf.getvalue()


# ── 1. 上传 ──

def test_upload_and_authenticate(sandbox):
    files = [
        ('files', ('macro1.jpg', _make_image(), 'image/jpeg')),
        ('files', ('macro2.jpg', _make_image(), 'image/jpeg')),
    ]
    resp = client.post('/images/upload', files=files, data={'types': 'macro,macro'})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data['success']
    paths = [i['path'] for i in data['data']['images']]
    assert len(paths) == 2
    for p in paths:
        assert Path(p).exists(), f'上传文件未落盘: {p}'
        assert Path(p).is_absolute()
        assert 'mobile_uploads' in p

    # 全链路: 上传路径直接喂 /authenticate (真实引擎)
    resp = client.post('/authenticate', json={
        'macro_images': paths, 'micro_images': []})
    assert resp.status_code == 200, resp.text
    auth = resp.json()
    assert auth['success']
    assert auth['data']['era_code'] in 'ABCDEFGHIJKLMN'
    assert auth['data']['predicted_authenticity'] in ('真老', '新仿')
    print(f"  ✓ upload→authenticate: {auth['data']['label_code']} "
          f"era={auth['data']['era_code']} {auth['data']['predicted_authenticity']}")


def test_upload_rejects(sandbox):
    # types 数量不一致
    resp = client.post('/images/upload',
                       files=[('files', ('a.jpg', _make_image(), 'image/jpeg'))],
                       data={'types': 'macro,micro'})
    assert resp.status_code == 400
    # 非法扩展名
    resp = client.post('/images/upload',
                       files=[('files', ('a.gif', b'GIF89a', 'image/gif'))],
                       data={'types': 'macro'})
    assert resp.status_code == 400
    # 内容魔数不符
    resp = client.post('/images/upload',
                       files=[('files', ('a.jpg', b'not-an-image', 'image/jpeg'))],
                       data={'types': 'macro'})
    assert resp.status_code == 400


# ── 2. 过滤 ──

def test_annotations_filters(sandbox):
    # save_annotation 的 JSONL 用 CWD 相对路径 → 切到沙箱目录避免污染
    cwd = os.getcwd()
    os.chdir(sandbox)
    try:
        def make(source_type, era, name, auth='真老'):
            resp = client.post('/annotations', json={
                'authenticity': auth, 'era_code': era,
                'product_name': name, 'material': '和田白玉',
                'source_type': source_type,
                'source_detail': '移动端测试', 'annotated_by': 'pytest',
                'annotation_confidence': 1,
            })
            assert resp.status_code == 200, resp.text
            return resp.json()['data']

        c1 = make('采集', 'G', '测试唐玉璧')
        c2 = make('馆藏', 'G', '测试唐玉佩')
        c3 = make('采集', 'H', '测试宋玉杯')

        def get(**params):
            r = client.get('/annotations', params={'limit': 100, **params})
            assert r.status_code == 200
            return r.json()

        assert get(source_type='采集')['total'] == 2
        assert get(era_code='H')['total'] == 1
        assert get(source_type='采集', era_code='G')['total'] == 1
        assert get(authenticity='新仿')['total'] == 0
        assert get(q='宋玉')['total'] == 1
        # q 按 label_code 也可命中
        assert get(q=c1['label_code'])['total'] == 1
    finally:
        os.chdir(cwd)


# ── 3. 图片服务 ──

def test_image_thumb_and_traversal(sandbox):
    img = PILImage.new('RGB', (800, 600), (200, 90, 90))
    rel = Path('scraped_data/test_thumb.jpg')
    (sandbox / rel).parent.mkdir(parents=True, exist_ok=True)
    img.save(sandbox / rel)

    # 缩略图
    resp = client.get(f'/images/{rel.as_posix()}?w=200')
    assert resp.status_code == 200
    assert resp.headers['content-type'] == 'image/jpeg'
    from PIL import Image
    import io as _io
    w = Image.open(_io.BytesIO(resp.content)).width
    assert w == 200
    assert (sandbox / '.thumb_cache' / '200').exists()

    # 原图 (无 w)
    resp = client.get(f'/images/{rel.as_posix()}')
    assert resp.status_code == 200

    # 路径逃逸 → 403 (secret 在沙箱外)
    secret = sandbox.parent / f'{sandbox.name}_secret.jpg'
    img.save(secret)
    from fastapi import HTTPException
    escape = f'../{secret.name}'
    with pytest.raises(HTTPException) as ei:
        server.serve_image(escape)
    assert ei.value.status_code == 403
    # 不存在的文件 → 404
    with pytest.raises(HTTPException) as ei:
        server.serve_image('no/such/file.jpg')
    assert ei.value.status_code == 404


# ── 4. 模型分发 ──

def test_model_download_and_status(sandbox):
    meta_dir = server.MOBILE_MODEL_DIR
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / 'jade_model_metadata.json').write_text('{"version": "test"}')

    resp = client.get('/models/download/jade_model_metadata.json')
    assert resp.status_code == 200
    assert resp.json() == {'version': 'test'}

    resp = client.get('/models/download/evil.exe')
    assert resp.status_code == 403
    resp = client.get('/models/download/jade_model_macro.int8.onnx')
    assert resp.status_code == 404

    resp = client.get('/models/status')
    body = resp.json()
    assert body['success']
    names = [m['name'] for m in body['data'].get('mobile_models', [])]
    assert 'jade_model_metadata.json' in names
