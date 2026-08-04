"""
古玉鉴真 — 评估指标

- EraAccuracy: 年代分类 Top-1 / Top-3 准确率
- GroupAccuracy: 粗粒度分组准确率
- AuthMetrics: 真伪分类 Precision / Recall / F1
- PerEraMetrics: 每个年代的分类准确率
"""

import torch
import torch.nn.functional as F
from typing import Dict, List, Tuple
from collections import defaultdict


def compute_era_accuracy(
    era_logits: torch.Tensor,  # (B, 14)
    era_targets: torch.Tensor, # (B,)
) -> Dict[str, float]:
    """计算年代分类准确率。"""
    preds = era_logits.argmax(dim=1)
    top1 = (preds == era_targets).float().mean().item()

    # Top-3 accuracy
    top3_preds = era_logits.topk(3, dim=1).indices
    top3 = top3_preds.eq(era_targets.unsqueeze(1)).any(dim=1).float().mean().item()

    return {'era_top1': top1, 'era_top3': top3}


def compute_group_accuracy(
    coarse_logits: torch.Tensor,  # (B, 5)
    coarse_targets: torch.Tensor, # (B,)
) -> float:
    """计算粗粒度分组准确率。"""
    preds = coarse_logits.argmax(dim=1)
    return (preds == coarse_targets).float().mean().item()


def compute_auth_metrics(
    auth_logits: torch.Tensor,  # (B, 2)
    auth_targets: torch.Tensor, # (B,)
) -> Dict[str, float]:
    """计算真伪分类指标。"""
    preds = auth_logits.argmax(dim=1)
    probs = F.softmax(auth_logits, dim=1)

    # 真老 = 0, 新仿 = 1
    tp = ((preds == 1) & (auth_targets == 1)).sum().item()
    fp = ((preds == 1) & (auth_targets == 0)).sum().item()
    fn = ((preds == 0) & (auth_targets == 1)).sum().item()
    tn = ((preds == 0) & (auth_targets == 0)).sum().item()

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0 else 0.0
    )
    accuracy = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) > 0 else 0.0

    return {
        'auth_accuracy': accuracy,
        'auth_precision': precision,
        'auth_recall': recall,
        'auth_f1': f1,
    }


def compute_per_era_accuracy(
    era_logits: torch.Tensor,
    era_targets: torch.Tensor,
    num_classes: int = 14,
) -> Dict[int, float]:
    """计算每个年代的分类准确率。"""
    preds = era_logits.argmax(dim=1)
    per_era = {}

    for cls in range(num_classes):
        mask = era_targets == cls
        if mask.sum() > 0:
            acc = (preds[mask] == cls).float().mean().item()
            per_era[cls] = acc

    return per_era


def compute_era_confusion_matrix(
    era_logits: torch.Tensor,
    era_targets: torch.Tensor,
    num_classes: int = 14,
) -> torch.Tensor:
    """计算年代混淆矩阵。"""
    preds = era_logits.argmax(dim=1)
    cm = torch.zeros(num_classes, num_classes)

    for t, p in zip(era_targets, preds):
        cm[t, p] += 1

    # 行归一化 (recall per class)
    cm_norm = cm / cm.sum(dim=1, keepdim=True).clamp(min=1)
    return cm_norm


def aggregate_metrics(all_metrics: List[Dict]) -> Dict[str, float]:
    """聚合多个 batch 的指标。"""
    aggregated = defaultdict(float)
    count = len(all_metrics)

    for m in all_metrics:
        for k, v in m.items():
            aggregated[k] += v

    return {k: v / count for k, v in aggregated.items()}
