"""
古玉鉴真 — 顶层多视角玉器鉴定模型

JadeAuthModel 整合:
- MacroStream: 宏观图特征提取
- MicroStream: 微距图 tile 特征提取
- ViewCrossAttention: 视角融合
- EraHead: 年代分类
- AuthHead: 真伪分类
"""

import torch
import torch.nn as nn
from typing import Dict, Any, Optional

from .macro_stream import MacroStream
from .micro_stream import MicroStream
from .fusion import ViewCrossAttention
from .heads import EraHead, AuthHead


class JadeAuthModel(nn.Module):
    """古玉鉴真多视角鉴定模型。

    完整的端到端模型，用于训练和推理。

    Args:
        macro_backbone: 宏观流骨干变体
        micro_backbone: 微距流骨干变体
        feature_dim: 特征维度
        num_era_classes: 年代类别数 (14)
        num_era_groups: 年代分组数 (5)
    """

    def __init__(
        self,
        macro_backbone: str = 'convnextv2_femto',
        micro_backbone: str = 'convnextv2_atto',
        feature_dim: int = 512,
        num_era_classes: int = 14,
        num_era_groups: int = 5,
        dropout: float = 0.3,
    ):
        super().__init__()

        self.feature_dim = feature_dim

        # 双流特征提取
        self.macro_stream = MacroStream(
            backbone_variant=macro_backbone,
            pretrained=True,
            output_dim=feature_dim,
        )
        self.micro_stream = MicroStream(
            backbone_variant=micro_backbone,
            pretrained=True,
            output_dim=feature_dim,
        )

        # 视角交叉注意力融合
        self.fusion = ViewCrossAttention(
            feature_dim=feature_dim,
            num_heads=8,
            dropout=dropout,
        )

        # 分类头
        self.era_head = EraHead(
            input_dim=feature_dim,
            hidden_dim=256,
            num_fine=num_era_classes,
            num_coarse=num_era_groups,
            dropout=dropout,
        )
        self.auth_head = AuthHead(
            input_dim=feature_dim,
            hidden_dim=128,
            dropout=dropout,
        )

    def forward(
        self,
        macro_images: torch.Tensor,
        micro_tiles: list,
        macro_mask: Optional[torch.Tensor] = None,
        micro_mask: Optional[torch.Tensor] = None,
    ) -> Dict[str, Any]:
        """
        前向传播。

        Args:
            macro_images: (B, N_macro, 3, 512, 512) 宏观图 batch
            micro_tiles: List[List[Tensor]] 微距图 tile 嵌套列表
            macro_mask: (B, N_macro) 有效宏观图 mask
            micro_mask: (B, N_micro) 有效微距图 mask

        Returns:
            dict:
                'era_fine': (B, 14) 年代 logits
                'era_coarse': (B, 5) 年代分组 logits
                'authenticity': (B, 2) 真伪 logits
                'macro_features': (B, N_macro, D) 宏观图特征
                'micro_features': (B, N_micro, D) 微距图特征
                'fused': (B, D) 融合特征
                'attention_weights': (B, N_macro+N_micro) 各视角注意力权重
        """
        B = macro_images.shape[0]

        # ── MACRO 流 ──
        macro_features = self.macro_stream(macro_images, macro_mask)

        # ── MICRO 流 ──
        micro_features = self.micro_stream(micro_tiles)

        # 生成微距 mask
        if micro_mask is None:
            # 根据实际微距图数量推断 mask
            N_micro = micro_features.shape[1]
            micro_mask = torch.zeros(B, N_micro, device=macro_images.device)
            for i, tiles in enumerate(micro_tiles):
                n_valid = len(tiles)
                micro_mask[i, :n_valid] = 1.0

        # ── 融合 ──
        fused = self.fusion(
            macro_features, micro_features,
            macro_mask, micro_mask,
        )

        # ── 注意力权重 (用于可解释性) ──
        attn_weights = self.fusion.get_attention_weights(
            macro_features, micro_features,
            macro_mask, micro_mask,
        )

        # ── 分类预测 ──
        era_preds = self.era_head(fused)
        auth_preds = self.auth_head(fused)

        return {
            'era_fine': era_preds['fine'],
            'era_coarse': era_preds['coarse'],
            'authenticity': auth_preds,
            'macro_features': macro_features,
            'micro_features': micro_features,
            'fused': fused,
            'attention_weights': attn_weights,
        }

    def freeze_streams(self, macro_stages: int = 0, micro_stages: int = 0):
        """冻结骨干网络 (用于分阶段训练)。"""
        if macro_stages > 0:
            self.macro_stream.backbone._freeze_stages(macro_stages)
        if micro_stages > 0:
            self.micro_stream.backbone._freeze_stages(micro_stages)

    def get_num_params(self) -> Dict[str, int]:
        """获取各模块参数量统计。"""
        def count(module):
            return sum(p.numel() for p in module.parameters())

        return {
            'macro_stream': count(self.macro_stream),
            'micro_stream': count(self.micro_stream),
            'fusion': count(self.fusion),
            'era_head': count(self.era_head),
            'auth_head': count(self.auth_head),
            'total': count(self),
        }
