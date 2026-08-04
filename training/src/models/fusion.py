"""
古玉鉴真 — 视角级交叉注意力融合

将来自不同视角的宏观图和微距图的特征向量融合为一个统一的表示。
采用 View-Level Cross-Attention: 学习一个查询 token，对所有视角特征做注意力。

输入: macro_features (B, N_m, D) + micro_features (B, N_u, D)
输出: fused_feature (B, D)
"""

import torch
import torch.nn as nn
import math


class ViewCrossAttention(nn.Module):
    """视角级交叉注意力融合。

    学习一个可训练的 view_query token，
    对所有视角 (macro + micro) 的特征做多头交叉注意力，
    产生全局融合特征。
    """

    def __init__(
        self,
        feature_dim: int = 512,
        num_heads: int = 8,
        dropout: float = 0.1,
    ):
        super().__init__()
        assert feature_dim % num_heads == 0, "feature_dim must be divisible by num_heads"

        self.feature_dim = feature_dim
        self.num_heads = num_heads
        self.head_dim = feature_dim // num_heads
        self.scale = math.sqrt(self.head_dim)

        # 学习的查询 token
        self.view_query = nn.Parameter(torch.randn(1, 1, feature_dim) * 0.02)

        # 投影层
        self.q_proj = nn.Linear(feature_dim, feature_dim)
        self.k_proj = nn.Linear(feature_dim, feature_dim)
        self.v_proj = nn.Linear(feature_dim, feature_dim)
        self.out_proj = nn.Linear(feature_dim, feature_dim)

        self.dropout = nn.Dropout(dropout)

        # 层归一化
        self.norm = nn.LayerNorm(feature_dim)

    def forward(
        self,
        macro_features: torch.Tensor,   # (B, N_m, D)
        micro_features: torch.Tensor,   # (B, N_u, D)
        macro_mask: torch.Tensor = None,   # (B, N_m)
        micro_mask: torch.Tensor = None,   # (B, N_u)
    ) -> torch.Tensor:
        """
        Args:
            macro_features: 宏观图特征 (B, N_m, D)
            micro_features: 微距图特征 (B, N_u, D)
            macro_mask: 有效宏观图 mask
            micro_mask: 有效微距图 mask

        Returns:
            fused: (B, D) 融合后的全局特征
        """
        B, N_m, D = macro_features.shape
        N_u = micro_features.shape[1]

        # 拼接所有视角特征 → (B, N_m + N_u, D)
        all_features = torch.cat([macro_features, micro_features], dim=1)
        all_features = self.norm(all_features)

        # 构建 attention mask → (B, N_m + N_u)
        if macro_mask is not None and micro_mask is not None:
            attn_mask = torch.cat([macro_mask, micro_mask], dim=1)  # (B, N_v)
        else:
            attn_mask = torch.ones(B, N_m + N_u, device=all_features.device)

        # Query: 学习的 view token → (B, 1, D)
        query = self.view_query.expand(B, -1, -1)

        # Key, Value: 所有视角特征
        Q = self.q_proj(query)       # (B, 1, D)
        K = self.k_proj(all_features)  # (B, N_v, D)
        V = self.v_proj(all_features)  # (B, N_v, D)

        # 多头注意力
        Q = Q.view(B, 1, self.num_heads, self.head_dim).transpose(1, 2)  # (B, H, 1, d)
        K = K.view(B, -1, self.num_heads, self.head_dim).transpose(1, 2)  # (B, H, N_v, d)
        V = V.view(B, -1, self.num_heads, self.head_dim).transpose(1, 2)  # (B, H, N_v, d)

        # 计算注意力分数
        attn_scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale  # (B, H, 1, N_v)

        # 应用 mask
        attn_mask_expanded = attn_mask[:, None, None, :]  # (B, 1, 1, N_v)
        attn_scores = attn_scores.masked_fill(
            attn_mask_expanded == 0, float('-inf')
        )

        attn_weights = torch.softmax(attn_scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        # 加权求和
        attn_output = torch.matmul(attn_weights, V)  # (B, H, 1, d)
        attn_output = attn_output.transpose(1, 2).contiguous().view(B, 1, D)  # (B, 1, D)

        # 输出投影
        fused = self.out_proj(attn_output).squeeze(1)  # (B, D)

        return fused

    def get_attention_weights(
        self,
        macro_features: torch.Tensor,
        micro_features: torch.Tensor,
        macro_mask: torch.Tensor = None,
        micro_mask: torch.Tensor = None,
    ) -> torch.Tensor:
        """获取注意力权重 (用于可视化: 哪些视角最重要)。"""
        B, N_m, D = macro_features.shape
        N_u = micro_features.shape[1]

        all_features = torch.cat([macro_features, micro_features], dim=1)
        all_features = self.norm(all_features)

        if macro_mask is not None and micro_mask is not None:
            attn_mask = torch.cat([macro_mask, micro_mask], dim=1)
        else:
            attn_mask = torch.ones(B, N_m + N_u, device=all_features.device)

        query = self.view_query.expand(B, -1, -1)
        Q = self.q_proj(query).view(B, 1, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(all_features).view(B, -1, self.num_heads, self.head_dim).transpose(1, 2)

        attn_scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale
        attn_mask_expanded = attn_mask[:, None, None, :]
        attn_scores = attn_scores.masked_fill(attn_mask_expanded == 0, float('-inf'))
        attn_weights = torch.softmax(attn_scores, dim=-1)

        # 平均多头权重 → (B, N_v)
        return attn_weights.mean(dim=1).squeeze(1)
