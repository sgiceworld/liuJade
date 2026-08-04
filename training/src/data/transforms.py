"""
古玉鉴真 — 图像变换管线
训练与验证数据增强（基于 Albumentations / torchvision）

设计原则:
- 沁色需要色彩抖动模拟不同光照
- 工痕特征不能加模糊/锐化（会破坏微痕）
- 微距 tile 不加旋转（方向敏感）
"""

import torch
from torchvision import transforms


def get_train_transforms() -> transforms.Compose:
    """训练时宏观图增强管线。

    策略: 色彩抖动 (沁色) + 翻转 (方向无关) + 缩放裁剪 + 归一化
          不施加模糊/锐化 (保护工痕纹理)
    """
    return transforms.Compose([
        transforms.RandomResizedCrop(
            512, scale=(0.7, 1.0), ratio=(0.9, 1.1)
        ),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.3),
        # 色彩抖动 — 模拟不同光照条件观察沁色
        transforms.ColorJitter(
            brightness=0.2,
            contrast=0.2,
            saturation=0.15,
            hue=0.05,
        ),
        # 轻微随机旋转 (微距 tile 不用)
        transforms.RandomRotation(degrees=5),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])


def get_val_transforms() -> transforms.Compose:
    """验证/推理时宏观图预处理管线。"""
    return transforms.Compose([
        transforms.Resize((512, 512)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])


def get_micro_train_transforms() -> transforms.Compose:
    """训练时微距 tile 增强管线。

    策略: 微距图不旋转 (工痕方向有意义), 仅色彩抖动 + 翻转。
    """
    return transforms.Compose([
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.3),
        # 色彩抖动 — 沁色纹理
        transforms.ColorJitter(
            brightness=0.15,
            contrast=0.15,
            saturation=0.10,
            hue=0.03,
        ),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])


def get_micro_val_transforms() -> transforms.Compose:
    """验证时微距 tile 预处理。"""
    return transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])


def micro_tile_transform(tile: torch.Tensor) -> torch.Tensor:
    """单张微距 tile 的预处理 (推理时使用, NumPy → Tensor)。"""
    import numpy as np
    if isinstance(tile, np.ndarray):
        tile = torch.from_numpy(tile).permute(2, 0, 1).float() / 255.0
    normalize = transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    )
    return normalize(tile)
