#!/usr/bin/env python3
"""
古玉鉴真 — 移动端 ONNX INT8 量化 (Pico 变体)

- macro/micro (纯 Conv 主干): 静态 QDQ 量化, 校准数据取 training_data 各年代目录
- fusion (attention+Linear): 动态量化 (输入为特征向量, 无校准意义)
- 输出: models/mobile/quantized/jade_model_{macro,micro,fusion}.int8.onnx
        + jade_model_metadata.json (macr_onxx → int8 文件名, 含量化参数块)

用法:
    cd inference
    python scripts/quantize_models.py                # 默认: 每模型 120 张校准样本
    python scripts/quantize_models.py --samples 200  # 更多校准样本
    python scripts/quantize_models.py --act-type QUInt8   # NNAPI 兼容性回退开关
"""

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # scripts → inference → 仓库根
sys.path.insert(0, str(REPO_ROOT / 'inference' / 'src'))

import numpy as np  # noqa: E402
from onnxruntime.quantization import (  # noqa: E402
    CalibrationDataReader, QuantFormat, QuantType,
    quantize_dynamic, quantize_static,
)
from engine.preprocessing import (  # noqa: E402
    load_and_preprocess, load_and_tile_micro,
)

MODEL_DIR = REPO_ROOT / 'models' / 'mobile'
OUT_DIR = MODEL_DIR / 'quantized'
# 校准数据目录 (排除 A_待OCR确认 — 未确认年代)
CALIB_DIRS = ['A_文化期', 'B_商代', 'D_战国', 'E_秦汉',
              'G_唐', 'H_宋', 'I_金元', 'J_明']

MACRO_INPUT = 'macro_image'
MICRO_INPUT = 'micro_tile'


def collect_calib_paths(data_root: Path, samples: int) -> list:
    paths = []
    for d in CALIB_DIRS:
        dir_path = data_root / d
        if not dir_path.exists():
            continue
        paths.extend(sorted(dir_path.glob('*.png')) + sorted(dir_path.glob('*.jpg')))
    if len(paths) > samples:
        rng = random.Random(42)  # 固定种子, 可复现
        paths = rng.sample(paths, samples)
    return paths


class MacroCalibrationReader(CalibrationDataReader):
    """宏观流校准: 每张图 1 条 (3,512,512) 样本。"""

    def __init__(self, paths: list):
        self.paths = paths
        self.iter = iter(self._gen())

    def _gen(self):
        for p in self.paths:
            try:
                arr = load_and_preprocess(str(p), 512)
            except Exception:
                continue
            yield {MACRO_INPUT: arr[None].astype(np.float32)}

    def get_next(self):
        return next(self.iter, None)

    def rewind(self):
        self.iter = iter(self._gen())


class MicroCalibrationReader(CalibrationDataReader):
    """微距流校准: 每张图取前 N 个 tile, 逐 tile 一条 (3,224,224) 样本。"""

    def __init__(self, paths: list, tiles_per_image: int = 4,
                 max_total: int = 400):
        self.paths = paths
        self.tiles_per_image = tiles_per_image
        self.max_total = max_total
        self.iter = iter(self._gen())

    def _gen(self):
        count = 0
        for p in self.paths:
            try:
                tiles = load_and_tile_micro(str(p))[:self.tiles_per_image]
            except Exception:
                continue
            for t in tiles:
                yield {MICRO_INPUT: t[None].astype(np.float32)}
                count += 1
                if count >= self.max_total:
                    return

    def get_next(self):
        return next(self.iter, None)

    def rewind(self):
        self.iter = iter(self._gen())


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description='移动端 ONNX INT8 量化')
    ap.add_argument('--data-root', type=Path,
                    default=REPO_ROOT / 'training_data',
                    help='校准数据根目录 (training_data)')
    ap.add_argument('--samples', type=int, default=120,
                    help='宏观校准样本数 (跨年代抽样)')
    ap.add_argument('--tiles-per-image', type=int, default=4,
                    help='微距校准每图取 tile 数')
    ap.add_argument('--act-type', type=str, default='QInt8',
                    choices=['QInt8', 'QUInt8'], help='激活量化类型')
    ap.add_argument('--quant-format', type=str, default='QDQ',
                    choices=['QDQ', 'QOperator'], help='量化算子格式')
    args = ap.parse_args()

    act_type = getattr(QuantType, args.act_type)
    quant_format = getattr(QuantFormat, args.quant_format)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    calib_paths = collect_calib_paths(args.data_root, args.samples)
    if not calib_paths:
        raise SystemExit(f'校准数据为空: {args.data_root} (先准备 training_data)')
    print(f'校准样本: {len(calib_paths)} 张 (macro), '
          f'每张前 {args.tiles_per_image} tiles (micro)')

    # ── 宏观流: 静态 QDQ ──
    print('\n[1/3] 宏观流静态量化 (macro)...')
    quantize_static(
        str(MODEL_DIR / 'jade_model_macro.onnx'),
        str(OUT_DIR / 'jade_model_macro.int8.onnx'),
        MacroCalibrationReader(calib_paths),
        quant_format=quant_format,
        activation_type=act_type,
        weight_type=QuantType.QInt8,
    )
    print(f'  ✓ {OUT_DIR / "jade_model_macro.int8.onnx"}')

    # ── 微距流: 静态 QDQ ──
    print('[2/3] 微距流静态量化 (micro)...')
    quantize_static(
        str(MODEL_DIR / 'jade_model_micro.onnx'),
        str(OUT_DIR / 'jade_model_micro.int8.onnx'),
        MicroCalibrationReader(calib_paths, args.tiles_per_image),
        quant_format=quant_format,
        activation_type=act_type,
        weight_type=QuantType.QInt8,
    )
    print(f'  ✓ {OUT_DIR / "jade_model_micro.int8.onnx"}')

    # ── 融合头: 动态量化 ──
    print('[3/3] 融合头动态量化 (fusion)...')
    quantize_dynamic(
        str(MODEL_DIR / 'jade_model_fusion.onnx'),
        str(OUT_DIR / 'jade_model_fusion.int8.onnx'),
        weight_type=QuantType.QInt8,
    )
    print(f'  ✓ {OUT_DIR / "jade_model_fusion.int8.onnx"}')

    # ── 元数据 ──
    meta_path = MODEL_DIR / 'jade_model_metadata.json'
    with open(meta_path, encoding='utf-8') as f:
        metadata = json.load(f)
    metadata['macro_onnx'] = 'jade_model_macro.int8.onnx'
    metadata['micro_onnx'] = 'jade_model_micro.int8.onnx'
    metadata['fusion_onnx'] = 'jade_model_fusion.int8.onnx'
    metadata['quantization'] = {
        'method': 'macro/micro=static QDQ, fusion=dynamic',
        'quant_format': args.quant_format,
        'activation_type': args.act_type,
        'weight_type': 'QInt8',
        'calibration_samples': len(calib_paths),
        'calibration_tiles_per_image': args.tiles_per_image,
        'onnxruntime': __import__('onnxruntime').__version__,
        'quantized_at': datetime.now().isoformat(),
    }
    for name in ('macro', 'micro', 'fusion'):
        p = OUT_DIR / f'jade_model_{name}.int8.onnx'
        metadata['quantization'][f'{name}_sha256'] = sha256_file(p)
        metadata['quantization'][f'{name}_size_bytes'] = p.stat().st_size
    with open(OUT_DIR / 'jade_model_metadata.json', 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # 体积对比
    print('\n── 体积对比 ──')
    for name in ('macro', 'micro', 'fusion'):
        fp = (MODEL_DIR / f'jade_model_{name}.onnx').stat().st_size / 1e6
        q = (OUT_DIR / f'jade_model_{name}.int8.onnx').stat().st_size / 1e6
        print(f'  {name:7s} FP32 {fp:6.1f} MB → INT8 {q:6.1f} MB '
              f'({q / fp * 100:.0f}%)')
    print(f'\n✓ 量化完成, 元数据: {OUT_DIR / "jade_model_metadata.json"}')


if __name__ == '__main__':
    main()
