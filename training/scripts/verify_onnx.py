#!/usr/bin/env python3
"""
古玉鉴真 — ONNX 模型端到端验证

1. 用 JadeInferenceEngine 加载 models/jade_model 三子模型
2. 对真实裁剪图执行鉴定
3. 与 PyTorch 模型 (同一 checkpoint) 输出对比, 验证一致性

用法:
    cd training
    python scripts/verify_onnx.py [图片路径 ...]
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / 'inference' / 'src'))
sys.path.insert(0, str(REPO / 'training' / 'src'))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from engine.inference import JadeInferenceEngine  # noqa: E402
from engine.preprocessing import load_and_preprocess  # noqa: E402


def main():
    candidates = (
        list((REPO / 'training' / 'data' / 'images').glob('*.png'))
        or list((REPO / 'training_data' / 'D_战国').glob('*.png'))
    )
    imgs = [str(p) for p in candidates[:2]]
    if len(sys.argv) > 1:
        imgs = sys.argv[1:]

    print(f"测试图片: {imgs}")
    print(f"模型目录: {REPO / 'models'}")
    print()

    # ── 1. ONNX 推理引擎 ──
    engine = JadeInferenceEngine(str(REPO / 'models'))
    result = engine.authenticate(macro_image_paths=imgs, micro_image_paths=[])
    print("ONNX 推理引擎结果:")
    print(f"  预测年代: {result['predicted_era']} ({result['era_code']})")
    print(f"  Top-3: {[(t['era_name'], round(t['probability'], 3)) for t in result['top3_eras']]}")
    print(f"  真伪: {result['predicted_authenticity']} "
          f"(置信度 {result['authenticity_confidence']:.3f})")
    print(f"  耗时: {result['inference_time_ms']} ms")
    print()

    # ── 2. PyTorch 模型 (同一 checkpoint) 一致性对比 ──
    ckpt = REPO / 'models' / 'checkpoints' / 'jade_v0.1_stage4_last.ckpt'
    if not ckpt.exists():
        print(f"checkpoint 不存在: {ckpt}, 跳过一致性对比")
        return

    from models import JadeAuthModel
    model = JadeAuthModel(
        macro_backbone='convnextv2_atto',
        micro_backbone='convnextv2_atto',
        feature_dim=512,
        dropout=0.3,
    )
    model.load_state_dict(
        torch.load(ckpt, map_location='cpu', weights_only=True)['state_dict']
    )
    model.eval()

    # 构造与推理引擎一致的输入: 模块级复现引擎流程
    # (引擎: macro 特征 → fusion + heads; micro 用零特征向量, N_u=1)
    macro_list = [load_and_preprocess(p, 512) for p in imgs]
    macro_t = torch.from_numpy(np.stack(macro_list)).unsqueeze(0)  # (1,N,3,512,512)
    macro_mask = torch.ones(1, len(macro_list))

    with torch.no_grad():
        macro_feats = model.macro_stream(macro_t, macro_mask)  # (1, N, D)
        micro_feats = torch.zeros(1, 1, model.feature_dim)     # 引擎的零特征
        fused = model.fusion(macro_feats, micro_feats,
                             macro_mask, torch.ones(1, 1))
        era_out = model.era_head(fused)
        auth_out = model.auth_head(fused)

    era_probs_t = torch.softmax(era_out['fine'][0], dim=-1).numpy()
    auth_probs_t = torch.softmax(auth_out[0], dim=-1).numpy()

    era_probs_o = np.array([result['era_probabilities'][c]
                            for c in 'ABCDEFGHIJKLMN'])
    auth_conf_o = result['authenticity_confidence'] \
        if result['predicted_authenticity'] == '真老' else 1 - result['authenticity_confidence']

    diff_era = float(np.max(np.abs(era_probs_t - era_probs_o)))
    diff_auth = float(np.abs(auth_probs_t[0] - auth_conf_o))

    print("PyTorch vs ONNX 一致性:")
    print(f"  年代概率最大偏差: {diff_era:.6f}")
    print(f"  真老置信度偏差:   {diff_auth:.6f}")
    print()
    if diff_era < 1e-4 and diff_auth < 1e-4:
        print("✓ 端到端一致性验证通过")
    else:
        print("⚠ 输出存在偏差, 需检查")


if __name__ == '__main__':
    main()
