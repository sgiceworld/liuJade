"""
古玉鉴真 — ConvNeXt-V2 骨干网络封装

支持的变体: femto, atto, pico (通过 timm 加载)
输出维度: 512 (ConvNeXt-V2 标准)
"""

import torch
import torch.nn as nn
import timm


class ConvNeXtV2Backbone(nn.Module):
    """ConvNeXt-V2 骨干网络，输出全局特征向量。

    Args:
        variant: 'convnextv2_femto' | 'convnextv2_atto' | 'convnextv2_pico'
        pretrained: 是否加载 ImageNet 预训练权重
        freeze_stages: 冻结前 N 个 stage (0=全部可训练, 4=全部冻结)
        output_dim: 输出特征维度
    """

    VARIANTS = {
        'femto': 'convnextv2_femto.fcmae_ft_in22k_in1k',
        'atto': 'convnextv2_atto.fcmae_ft_in22k_in1k',
        'pico': 'convnextv2_pico.fcmae_ft_in22k_in1k',
    }

    def __init__(
        self,
        variant: str = 'convnextv2_femto',
        pretrained: bool = True,
        freeze_stages: int = 0,
        output_dim: int = 512,
    ):
        super().__init__()

        # 解析 variant 名称
        model_name = self.VARIANTS.get(variant, variant)

        # 加载 timm 模型
        self.backbone = timm.create_model(
            model_name,
            pretrained=pretrained,
            num_classes=0,  # 去掉分类头，取 feature
            global_pool='avg',
        )

        # 获取输出维度
        if hasattr(self.backbone, 'num_features'):
            feat_dim = self.backbone.num_features
        else:
            feat_dim = output_dim

        # 投影到统一维度
        if feat_dim != output_dim:
            self.proj = nn.Linear(feat_dim, output_dim)
        else:
            self.proj = nn.Identity()

        self.output_dim = output_dim

        # 冻结策略
        if freeze_stages > 0:
            self._freeze_stages(freeze_stages)

    def _freeze_stages(self, n_stages: int):
        """冻结前 n 个 stage 的参数。"""
        stage_names = ['stem', 'stages.0', 'stages.1', 'stages.2', 'stages.3']
        freeze_count = 0

        for name, param in self.backbone.named_parameters():
            should_freeze = False
            for i in range(min(n_stages, len(stage_names))):
                if stage_names[i] in name:
                    should_freeze = True
                    break
            if should_freeze:
                param.requires_grad = False
                freeze_count += 1

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, 3, H, W) 输入图片

        Returns:
            features: (B, output_dim) 全局特征向量
        """
        features = self.backbone(x)
        features = self.proj(features)
        return features

    def get_output_dim(self) -> int:
        return self.output_dim
