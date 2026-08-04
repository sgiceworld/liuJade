"""
古玉鉴真 — 损失函数

- HierarchicalCrossEntropyLoss: 分层年代损失
- FocalLoss: 真伪分类 Focal Loss
- SupervisedContrastiveLoss: 监督对比损失
- MultiTaskLoss: 组合总损失
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class HierarchicalCrossEntropyLoss(nn.Module):
    """分层交叉熵损失。

    对年代细粒度预测 (14类) 和粗粒度分组 (5类) 同时计算 CE。
    混淆商代(B)和周代(D)的惩罚 < 混淆商代(B)和清代(K)。

    L = CE(fine, y_fine) + lambda * CE(coarse, y_coarse)
    """

    def __init__(
        self,
        coarse_weight: float = 0.3,
        label_smoothing: float = 0.05,
    ):
        super().__init__()
        self.coarse_weight = coarse_weight
        self.label_smoothing = label_smoothing

    def forward(
        self,
        fine_preds: torch.Tensor,    # (B, 14)
        coarse_preds: torch.Tensor,  # (B, 5)
        fine_targets: torch.Tensor,  # (B,)
        coarse_targets: torch.Tensor, # (B,)
    ) -> torch.Tensor:
        fine_loss = F.cross_entropy(
            fine_preds, fine_targets,
            label_smoothing=self.label_smoothing,
        )
        coarse_loss = F.cross_entropy(
            coarse_preds, coarse_targets,
            label_smoothing=self.label_smoothing,
        )
        return fine_loss + self.coarse_weight * coarse_loss


class FocalLoss(nn.Module):
    """Focal Loss — 处理真老/新仿类别不平衡。

    FL(pt) = -alpha_t * (1 - pt)^gamma * log(pt)
    """

    def __init__(
        self,
        gamma: float = 2.0,
        alpha: float = 0.25,
        reduction: str = 'mean',
    ):
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha
        self.reduction = reduction

    def forward(
        self,
        preds: torch.Tensor,   # (B, 2)
        targets: torch.Tensor, # (B,)
    ) -> torch.Tensor:
        ce_loss = F.cross_entropy(preds, targets, reduction='none')
        pt = torch.exp(-ce_loss)

        # alpha weighting
        alpha_t = self.alpha * targets + (1 - self.alpha) * (1 - targets)

        focal_loss = alpha_t * (1 - pt) ** self.gamma * ce_loss

        if self.reduction == 'mean':
            return focal_loss.mean()
        elif self.reduction == 'sum':
            return focal_loss.sum()
        return focal_loss


class SupervisedContrastiveLoss(nn.Module):
    """监督对比损失。

    拉近同类 (同年) 样本，推开异类样本。

    L = -1/|P(i)| * sum_{p in P(i)} log( exp(sim(z_i, z_p)/tau) / sum_{a} exp(sim(z_i, z_a)/tau) )
    """

    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature

    def forward(
        self,
        features: torch.Tensor,  # (B, D)
        labels: torch.Tensor,    # (B,) 年代标签
    ) -> torch.Tensor:
        B = features.shape[0]

        # 归一化
        features = F.normalize(features, dim=1)

        # 相似度矩阵
        sim = torch.matmul(features, features.T) / self.temperature  # (B, B)

        # 正样本 mask: 相同标签
        pos_mask = labels.unsqueeze(0) == labels.unsqueeze(1)  # (B, B)
        # 排除自身
        pos_mask = pos_mask.fill_diagonal_(False)

        # 负样本 mask
        neg_mask = ~pos_mask
        neg_mask = neg_mask.fill_diagonal_(True)

        # 计算 InfoNCE
        exp_sim = torch.exp(sim)
        pos_sum = (exp_sim * pos_mask.float()).sum(dim=1)
        neg_sum = (exp_sim * neg_mask.float()).sum(dim=1)

        # 避免除零
        pos_count = pos_mask.float().sum(dim=1)
        mask = pos_count > 0

        if mask.sum() == 0:
            return torch.tensor(0.0, device=features.device)

        loss = -torch.log(
            pos_sum[mask] / (pos_sum[mask] + neg_sum[mask] + 1e-8)
        ).mean()

        return loss


class MultiTaskLoss(nn.Module):
    """多任务组合损失。

    L_total = L_era + alpha * L_auth + beta * L_contrastive
    """

    def __init__(
        self,
        coarse_era_weight: float = 0.3,
        era_label_smoothing: float = 0.05,
        focal_gamma: float = 2.0,
        focal_alpha: float = 0.25,
        contrastive_temperature: float = 0.07,
        auth_weight: float = 0.5,
        contrastive_weight: float = 0.1,
    ):
        super().__init__()

        self.era_loss = HierarchicalCrossEntropyLoss(
            coarse_weight=coarse_era_weight,
            label_smoothing=era_label_smoothing,
        )
        self.auth_loss = FocalLoss(
            gamma=focal_gamma,
            alpha=focal_alpha,
        )
        self.contrastive_loss = SupervisedContrastiveLoss(
            temperature=contrastive_temperature,
        )

        self.auth_weight = auth_weight
        self.contrastive_weight = contrastive_weight

    def forward(
        self,
        era_fine: torch.Tensor,
        era_coarse: torch.Tensor,
        auth_preds: torch.Tensor,
        fused_features: torch.Tensor,
        era_targets: torch.Tensor,
        era_coarse_targets: torch.Tensor,
        auth_targets: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Returns:
            dict with 'total', 'era', 'auth', 'contrastive'
        """
        L_era = self.era_loss(era_fine, era_coarse, era_targets, era_coarse_targets)
        L_auth = self.auth_loss(auth_preds, auth_targets)
        L_contrast = self.contrastive_loss(fused_features, era_targets)

        total = (
            L_era
            + self.auth_weight * L_auth
            + self.contrastive_weight * L_contrast
        )

        return {
            'total': total,
            'era': L_era,
            'auth': L_auth,
            'contrastive': L_contrast,
        }
