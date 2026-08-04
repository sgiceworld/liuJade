"""古玉鉴真 — 训练模块"""
from .losses import MultiTaskLoss, FocalLoss, HierarchicalCrossEntropyLoss
from .metrics import (
    compute_era_accuracy, compute_auth_metrics, compute_per_era_accuracy,
)

# trainer 依赖 pytorch_lightning，延迟导入避免循环依赖
def get_trainer(*args, **kwargs):
    from .trainer import JadeAuthTrainer
    return JadeAuthTrainer(*args, **kwargs)

__all__ = [
    "MultiTaskLoss", "FocalLoss", "HierarchicalCrossEntropyLoss",
    "compute_era_accuracy", "compute_auth_metrics", "compute_per_era_accuracy",
    "get_trainer",
]
