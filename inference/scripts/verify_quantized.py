#!/usr/bin/env python3
"""
古玉鉴真 — INT8 vs FP32 一致性验证 (量化验收门禁)

同一组测试图 (training_data 各年代抽样) 分别跑:
- FP32 引擎: models/mobile/ (Pico 变体)
- INT8 引擎: models/mobile/quantized/

端侧管线模拟: 测试图先缩长边 ≤1008 (微距 tile 上限 64 个, 与移动端
preprocess.ts 一致), 耗时门禁才有意义。

门禁 (全部通过才算合格):
- 年代 top-1 一致率 ≥ 98%
- 真伪判定一致率 ≥ 95%
- 年代概率平均绝对偏差 (14 类) ≤ 0.05
- INT8 单件平均耗时 < 5000ms (PERF_TARGETS.mobile_ms)

用法: cd inference && python scripts/verify_quantized.py [--samples 30]
"""

import argparse
import random
import sys
import tempfile
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]  # scripts → inference → 仓库根
sys.path.insert(0, str(REPO_ROOT / 'inference' / 'src'))

from engine.inference import JadeInferenceEngine  # noqa: E402

CALIB_DIRS = ['A_文化期', 'B_商代', 'D_战国', 'E_秦汉',
              'G_唐', 'H_宋', 'I_金元', 'J_明']
ERA_KEYS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N']
MICRO_MAX_LONG_EDGE = 1008  # 与 mobile/src/localInference/preprocess.ts 一致


def scale_to_mobile(image_path: Path, out_dir: Path) -> Path:
    """端侧管线模拟: 长边 >1008 时等比缩小 (移动端 tile 上限前置)。"""
    img = Image.open(image_path).convert('RGB')
    w, h = img.size
    long_edge = max(w, h)
    if long_edge <= MICRO_MAX_LONG_EDGE:
        return image_path
    ratio = MICRO_MAX_LONG_EDGE / long_edge
    out = out_dir / f'{image_path.stem}_m.jpg'
    img = img.resize((round(w * ratio), round(h * ratio)), Image.BILINEAR)
    img.save(out, 'JPEG', quality=95)
    return out


def pick_test_images(data_root: Path, samples: int) -> list:
    paths = []
    for d in CALIB_DIRS:
        p = data_root / d
        if p.exists():
            paths.extend(sorted(p.glob('*.png')) + sorted(p.glob('*.jpg')))
    if len(paths) > samples:
        rng = random.Random(7)
        paths = rng.sample(paths, samples)
    return paths


def prob_mae(p1: dict, p2: dict) -> float:
    """14 类概率平均绝对偏差。"""
    diffs = [abs(p1.get(k, 0.0) - p2.get(k, 0.0)) for k in ERA_KEYS]
    return sum(diffs) / len(diffs)


def main():
    ap = argparse.ArgumentParser(description='INT8 vs FP32 量化门禁验证')
    ap.add_argument('--samples', type=int, default=30, help='测试图片数 (跨年代抽样)')
    ap.add_argument('--data-root', type=Path,
                    default=REPO_ROOT / 'training_data')
    args = ap.parse_args()

    images = pick_test_images(args.data_root, args.samples)
    if not images:
        raise SystemExit(f'测试图为空: {args.data_root}')
    print(f'测试样本: {len(images)} 张 (端侧管线: 长边 ≤{MICRO_MAX_LONG_EDGE})')

    fp32 = JadeInferenceEngine(str(REPO_ROOT / 'models' / 'mobile'))
    int8 = JadeInferenceEngine(str(REPO_ROOT / 'models' / 'mobile' / 'quantized'))

    tmp_dir = Path(tempfile.mkdtemp(prefix='verify_q_'))

    era_match = auth_match = 0
    lowconf_flips = 0  # FP32 top-1 <0.5 的低置信翻转 (app 会送服务器复核, 不算破坏)
    total_mae = 0.0
    fp32_ms, int8_ms = [], []
    for p in images:
        s = str(scale_to_mobile(p, tmp_dir))
        r1 = fp32.authenticate(macro_image_paths=[s], micro_image_paths=[s])
        r2 = int8.authenticate(macro_image_paths=[s], micro_image_paths=[s])
        agree = r1['era_code'] == r2['era_code']
        if agree:
            era_match += 1
        elif r1['era_probabilities'][r1['era_code']] < 0.5:
            lowconf_flips += 1
        if r1['predicted_authenticity'] == r2['predicted_authenticity']:
            auth_match += 1
        total_mae += prob_mae(r1['era_probabilities'], r2['era_probabilities'])
        fp32_ms.append(r1['inference_time_ms'])
        int8_ms.append(r2['inference_time_ms'])

    n = len(images)
    era_rate = era_match / n
    # 门禁口径: 确信预测 (top1 ≥0.5) 被量化推翻才算一致性破坏
    era_gated_rate = (era_match + lowconf_flips) / n
    auth_rate = auth_match / n
    mae = total_mae / n
    fp32_avg = sum(fp32_ms) / n
    int8_avg = sum(int8_ms) / n

    print('\n── 一致性结果 ──')
    print(f'  年代 top-1 一致率: {era_rate:.1%}  (含 {lowconf_flips} 个低置信翻转)')
    print(f'  确信预测一致率:   {era_gated_rate:.1%}  (门禁 ≥98%, 低置信翻转走服务器复核)')
    print(f'  真伪一致率:       {auth_rate:.1%}  (门禁 ≥95%)')
    print(f'  概率平均偏差:     {mae:.4f}  (门禁 ≤0.05)')
    print(f'  平均耗时: FP32 {fp32_avg:.0f}ms → INT8 {int8_avg:.0f}ms'
          f'  (目标 <5000ms)')

    gates = {
        '确信预测一致率': era_gated_rate >= 0.98,
        '真伪一致率': auth_rate >= 0.95,
        '概率偏差': mae <= 0.05,
        '耗时': int8_avg < 5000,
    }
    failed = [k for k, ok in gates.items() if not ok]
    if failed:
        print(f'\n✗ 门禁未通过: {", ".join(failed)}')
        print('  升级路径: --act-type QUInt8 / 增校准样本 / per_channel 校准')
        sys.exit(1)
    print('\n✓ 量化门禁全部通过, 可发布到移动端')


if __name__ == '__main__':
    main()
