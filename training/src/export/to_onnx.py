"""
古玉鉴真 — ONNX 模型导出

将训练好的 JadeAuthModel 导出为 ONNX 格式，用于边缘端推理部署。
使用 torch.onnx + onnx-simplifier。
"""

import torch
from pathlib import Path
from typing import Optional, Dict, Any
import json

try:
    from ..models.jade_model import JadeAuthModel
except ImportError:
    from models.jade_model import JadeAuthModel


def export_to_onnx(
    model: JadeAuthModel,
    output_path: str,
    input_shapes: Optional[Dict[str, Any]] = None,
    opset_version: int = 17,
    simplify: bool = True,
) -> str:
    """
    导出 JadeAuthModel 为 ONNX 文件。

    Args:
        model: 训练好的 JadeAuthModel
        output_path: 输出 ONNX 文件路径
        input_shapes: 自定义输入形状
        opset_version: ONNX opset 版本
        simplify: 是否运行 onnx-simplifier

    Returns:
        onnx 文件路径
    """
    model.eval()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if input_shapes is None:
        input_shapes = {
            'macro_images': (1, 3, 3, 512, 512),  # (B, N_macro, C, H, W)
            'macro_mask': (1, 3),                   # (B, N_macro)
        }

    # 创建示例输入
    device = next(model.parameters()).device
    dummy_macro = torch.randn(input_shapes['macro_images'], device=device)
    dummy_macro_mask = torch.ones(input_shapes['macro_mask'], device=device)

    # 微距图 tile: 用 List 类型
    dummy_micro_tiles = [
        [torch.randn(4, 3, 224, 224, device=device)]  # 1张微距图, 4个tiles
    ]

    # ── 方案: 分别导出各子模块，推理时手动组装 ──
    # 因为 ONNX 不擅长处理嵌套 List 输入

    # 1. 导出 MACRO 流
    macro_onnx_path = output_path.parent / f"{output_path.stem}_macro.onnx"
    _export_macro_stream(model, str(macro_onnx_path), opset_version, simplify)

    # 2. 导出 MICRO 流 (单 tile 处理)
    micro_onnx_path = output_path.parent / f"{output_path.stem}_micro.onnx"
    _export_micro_stream(model, str(micro_onnx_path), opset_version, simplify)

    # 3. 导出融合 + 分类头
    fusion_onnx_path = output_path.parent / f"{output_path.stem}_fusion.onnx"
    _export_fusion_and_heads(model, str(fusion_onnx_path), opset_version, simplify)

    # 写入模型元数据
    meta_path = output_path.parent / f"{output_path.stem}_metadata.json"
    metadata = {
        'model_type': 'JadeAuthModel',
        'macro_onnx': f"{output_path.stem}_macro.onnx",
        'micro_onnx': f"{output_path.stem}_micro.onnx",
        'fusion_onnx': f"{output_path.stem}_fusion.onnx",
        'input_specs': {
            'macro': {'shape': [3, 512, 512], 'mean': [0.485, 0.456, 0.406], 'std': [0.229, 0.224, 0.225]},
            'micro_tile': {'shape': [3, 224, 224], 'mean': [0.485, 0.456, 0.406], 'std': [0.229, 0.224, 0.225], 'tile_size': 224, 'tile_stride': 112},
        },
        'output_specs': {
            'era_classes': 14,
            'auth_classes': 2,
            'feature_dim': 512,
        },
    }
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    return str(output_path)


def _export_macro_stream(
    model: JadeAuthModel,
    output_path: str,
    opset: int = 17,
    simplify: bool = True,
):
    """导出宏观流为 ONNX。"""
    macro_stream = model.macro_stream
    macro_stream.eval()

    dummy_input = torch.randn(1, 3, 512, 512)

    torch.onnx.export(
        macro_stream,
        (dummy_input, None),  # (images, mask)
        output_path,
        input_names=['macro_image'],
        output_names=['macro_features'],
        dynamic_axes={
            'macro_image': {0: 'batch'},
            'macro_features': {0: 'batch'},
        },
        opset_version=opset,
        do_constant_folding=True,
    )

    if simplify:
        _simplify_onnx(output_path)


def _export_micro_stream(
    model: JadeAuthModel,
    output_path: str,
    opset: int = 17,
    simplify: bool = True,
):
    """导出微距流为 ONNX (单 tile 处理)。"""
    micro_backbone = model.micro_stream.backbone
    micro_backbone.eval()

    dummy_tile = torch.randn(1, 3, 224, 224)

    torch.onnx.export(
        micro_backbone,
        dummy_tile,
        output_path,
        input_names=['micro_tile'],
        output_names=['tile_features'],
        dynamic_axes={
            'micro_tile': {0: 'batch'},
            'tile_features': {0: 'batch'},
        },
        opset_version=opset,
        do_constant_folding=True,
    )

    if simplify:
        _simplify_onnx(output_path)


def _export_fusion_and_heads(
    model: JadeAuthModel,
    output_path: str,
    opset: int = 17,
    simplify: bool = True,
):
    """导出融合模块 + 分类头为 ONNX。"""
    # 构建一个包含 fusion + heads 的联合模块
    class FusionHeadsModule(torch.nn.Module):
        def __init__(self, fusion, era_head, auth_head):
            super().__init__()
            self.fusion = fusion
            self.era_head = era_head
            self.auth_head = auth_head

        def forward(self, macro_features, micro_features, macro_mask, micro_mask):
            fused = self.fusion(macro_features, micro_features, macro_mask, micro_mask)
            era = self.era_head(fused)
            auth = self.auth_head(fused)
            return era['fine'], era['coarse'], auth

    fusion_module = FusionHeadsModule(
        model.fusion, model.era_head, model.auth_head
    )
    fusion_module.eval()

    D = model.feature_dim
    dummy_macro = torch.randn(1, 3, D)
    dummy_micro = torch.randn(1, 2, D)
    dummy_macro_mask = torch.ones(1, 3)
    dummy_micro_mask = torch.ones(1, 2)

    torch.onnx.export(
        fusion_module,
        (dummy_macro, dummy_micro, dummy_macro_mask, dummy_micro_mask),
        output_path,
        input_names=[
            'macro_features', 'micro_features',
            'macro_mask', 'micro_mask',
        ],
        output_names=['era_fine', 'era_coarse', 'authenticity'],
        dynamic_axes={
            'macro_features': {0: 'batch', 1: 'num_macro'},
            'micro_features': {0: 'batch', 1: 'num_micro'},
            'macro_mask': {0: 'batch', 1: 'num_macro'},
            'micro_mask': {0: 'batch', 1: 'num_micro'},
        },
        opset_version=opset,
        do_constant_folding=True,
    )

    if simplify:
        _simplify_onnx(output_path)


def _simplify_onnx(path: str):
    """运行 onnx-simplifier。"""
    try:
        import onnx
        from onnxsim import simplify as onnx_simplify

        model = onnx.load(path)
        model_simp, check = onnx_simplify(model)
        if check:
            onnx.save(model_simp, path)
            print(f"✓ ONNX simplified: {path}")
        else:
            print(f"⚠ ONNX simplify check failed for {path}, keeping original")
    except ImportError:
        print(f"⚠ onnx-simplifier not installed, skipping simplification for {path}")
    except Exception as e:
        print(f"⚠ ONNX simplification error: {e}")
