"""
古玉鉴真 — MICRO 流 (微距图特征提取)

处理高分辨率微距图的 tile 切片 (224×224)，提取工痕微观特征。
每张微距图切分为多个重叠 tile → 分别提取特征 → 均值池化 → 得到该图特征。
"""

import torch
import torch.nn as nn

from .backbone import ConvNeXtV2Backbone


class MicroStream(nn.Module):
    """
    微距图特征提取器。

    处理流程:
        高分辨率微距图 → 切 tile (224×224, stride 112)
        → 每个 tile 通过轻量骨干 → 均值池化 → 得到该微距图的特征

    输入: List[Tensor(N_tiles_i, 3, 224, 224)] — 每张微距图的 tile 列表
    输出: (B, N_micro, D) — 每张微距图的特征向量
    """

    def __init__(
        self,
        backbone_variant: str = 'convnextv2_atto',
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
        tile_batches: list,  # List[Tensor(N_tiles_i, 3, 224, 224)]
    ) -> torch.Tensor:
        """
        Args:
            tile_batches: 长度 B 的列表，每个元素是该样本所有微距图的 tile batch
                         tile_batches[i] 是 List[Tensor]，每张微距图的 tile 集合

        Returns:
            features: (B, max_N_micro, D) —
                      每张微距图的池化特征，padding 位清零
        """
        B = len(tile_batches)
        all_piece_features = []

        # 确定最大微距图数
        max_n_micro = max(
            len(tiles_per_piece) for tiles_per_piece in tile_batches
        )

        for tiles_per_piece in tile_batches:
            if not tiles_per_piece:
                # 该样本没有微距图 → 零向量
                all_piece_features.append(
                    torch.zeros(max_n_micro, self.output_dim)
                )
                continue

            img_features = []
            for tiles in tiles_per_piece:
                # tiles: (N_tiles, 3, 224, 224) 或空
                if isinstance(tiles, torch.Tensor) and tiles.shape[0] > 0:
                    # 处理每张微距图的所有 tile
                    tile_feats = self.backbone(tiles)  # (N_tiles, D)
                    # 均值池化 → 该微距图的特征
                    img_feat = tile_feats.mean(dim=0, keepdim=True)  # (1, D)
                else:
                    img_feat = torch.zeros(1, self.output_dim)

                img_features.append(img_feat)

            # 拼接该件玉器所有微距图特征
            piece_feats = torch.cat(img_features, dim=0)  # (N_micro, D)

            # Padding 到 max_n_micro
            if piece_feats.shape[0] < max_n_micro:
                pad = torch.zeros(
                    max_n_micro - piece_feats.shape[0], self.output_dim
                )
                piece_feats = torch.cat([piece_feats, pad])

            all_piece_features.append(piece_feats)

        # Stack → (B, max_N_micro, D)
        return torch.stack(all_piece_features)
