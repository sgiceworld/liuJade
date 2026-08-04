"""
古玉鉴真 — MACRO 流 (宏观图特征提取)

处理整帧玉器图片 (512×512)，提取器形、沁色等全局特征。
同一件玉器多个视角的宏观图共享权重。
"""

import torch
import torch.nn as nn

from .backbone import ConvNeXtV2Backbone


class MacroStream(nn.Module):
    """
    宏观图特征提取器。

    输入: (B, N_macro, 3, 512, 512) — 批量多视角宏观图
    输出: (B, N_macro, D) — 每张宏观图的特征向量
    """

    def __init__(
        self,
        backbone_variant: str = 'convnextv2_femto',
        pretrained: bool = True,
        output_dim: int = 512,
    ):
        super().__init__()
        self.backbone = ConvNeXtV2Backbone(
            variant=backbone_variant,
            pretrained=pretrained,
            output_dim=output_dim,
        )
        self.output_dim = output_dim

    def forward(
        self,
        images: torch.Tensor,
        mask: torch.Tensor = None,
    ) -> torch.Tensor:
        """
        Args:
            images: (B, N, 3, 512, 512) — 批量多视角图片
            mask: (B, N) — 有效图片 mask (1=有效, 0=padding)

        Returns:
            features: (B, N, D) — 特征向量
        """
        B, N, C, H, W = images.shape

        # 合并 B,N 维度 → (B*N, C, H, W)
        images_flat = images.view(B * N, C, H, W)

        # 通过骨干网络
        features_flat = self.backbone(images_flat)  # (B*N, D)

        # 恢复维度 → (B, N, D)
        features = features_flat.view(B, N, -1)

        # 如果提供了 mask，将 padding 位置清零
        if mask is not None:
            features = features * mask.unsqueeze(-1)

        return features
