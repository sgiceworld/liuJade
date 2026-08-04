"""
古玉鉴真 — 微距图加权采样器

实现微距图在训练中 10x 权重的核心机制:
通过调整采样频率，让含微距图的样本被采样 10 倍频次。
"""

from typing import Dict, List
import torch
from torch.utils.data import Sampler


class MicroWeightedSampler(Sampler):
    """
    加权采样器: 含微距图的样本权重 = 普通样本 × micro_weight。

    Args:
        dataset: JadeMultiViewDataset 实例
        micro_weight: 微距图权重倍数 (默认 10)
    """

    def __init__(
        self,
        dataset,
        micro_weight: float = 10.0,
        num_samples: int = None,
    ):
        self.dataset = dataset
        self.micro_weight = micro_weight

        # 计算每个样本的权重: 有微距图 → 10×, 无 → 1×
        self.weights = []
        for piece in dataset.pieces:
            if len(piece['micro_images']) > 0:
                self.weights.append(self.micro_weight)
            else:
                self.weights.append(1.0)

        self.total_weight = sum(self.weights)
        self.num_samples = num_samples or len(dataset)

    def __iter__(self):
        # 按权重随机采样
        indices = torch.multinomial(
            torch.tensor(self.weights),
            self.num_samples,
            replacement=True,
        )
        return iter(indices.tolist())

    def __len__(self):
        return self.num_samples


class StratifiedEraSampler(Sampler):
    """按年代分层采样，确保每个时代的样本均衡出现在 batch 中。"""

    def __init__(self, dataset, samples_per_era: int = 4):
        self.dataset = dataset
        self.samples_per_era = samples_per_era
        self.era_to_indices = dataset.era_to_indices
        self.num_eras = len(self.era_to_indices)
        self.num_samples = samples_per_era * self.num_eras

    def __iter__(self):
        indices = []
        for era, era_indices in self.era_to_indices.items():
            if len(era_indices) >= self.samples_per_era:
                sampled = torch.randperm(len(era_indices))[:self.samples_per_era]
                indices.extend([era_indices[i] for i in sampled])
            else:
                indices.extend(era_indices * (self.samples_per_era // len(era_indices) + 1))
                indices = indices[:self.num_samples]

        random.shuffle(indices)
        return iter(indices)

    def __len__(self):
        return self.num_samples


# 简单的模块级导入方便
import random
