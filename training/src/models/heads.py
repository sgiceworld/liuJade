"""
古玉鉴真 — 分类头

- EraHead: 14类年代分类 + 5类粗粒度分组
- AuthHead: 2类真伪分类 (Focal Loss)
"""

import torch
import torch.nn as nn


class EraHead(nn.Module):
    """年代分类头。

    输出两个层级:
    - fine: 14类细粒度年代 (A-N)
    - coarse: 5类粗粒度分组 (远古/古典/中古/近古/近现代)
    """

    def __init__(
        self,
        input_dim: int = 512,
        hidden_dim: int = 256,
        num_fine: int = 14,
        num_coarse: int = 5,
        dropout: float = 0.3,
    ):
        super().__init__()

        self.mlp = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
        )

        self.fine_head = nn.Linear(hidden_dim, num_fine)
        self.coarse_head = nn.Linear(hidden_dim, num_coarse)

    def forward(self, x: torch.Tensor) -> dict:
        """
        Args:
            x: (B, D) 融合特征

        Returns:
            dict with:
                'fine': (B, 14) 细粒度 logits
                'coarse': (B, 5) 粗粒度 logits
        """
        h = self.mlp(x)
        return {
            'fine': self.fine_head(h),
            'coarse': self.coarse_head(h),
        }


class AuthHead(nn.Module):
    """真伪分类头。

    输出: 2类 (真老/新仿) logits
    """

    def __init__(
        self,
        input_dim: int = 512,
        hidden_dim: int = 128,
        dropout: float = 0.3,
    ):
        super().__init__()

        self.mlp = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
        )

        self.classifier = nn.Linear(hidden_dim, 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, D) 融合特征

        Returns:
            logits: (B, 2)
        """
        h = self.mlp(x)
        return self.classifier(h)
