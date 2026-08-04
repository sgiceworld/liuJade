"""
古玉鉴真 — 多视角玉器数据集

核心设计:
- 按件分组 (piece-level grouping): 同一件玉器的所有图片视为一个样本
- 宏观图 (macro) + 微距图 (micro) 分两个流送入模型
- 微距图切分为 224x224 tile, 支持 10x 权重采样
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import torch
from torch.utils.data import Dataset
from PIL import Image


class JadeMultiViewDataset(Dataset):
    """
    多视角玉器数据集。

    数据目录结构:
        data_root/
        ├── annotations.json      # 标注清单
        │   [{
        │       "label_code": "0_JY..._G_001",
        │       "era": "唐", "era_code": "G",
        │       "authenticity": "真老",
        │       "images": ["img_001.jpg", "img_002.jpg"],
        │       "image_types": ["macro", "macro", "micro", ...],
        │       ...
        │   }]
        └── images/               # 图片文件
    """

    def __init__(
        self,
        data_root: str,
        annotation_file: str = "annotations.json",
        transform_macro=None,
        transform_micro=None,
        is_train: bool = True,
        micro_weight: float = 10.0,
        num_macro_views: int = 3,
        num_micro_views: int = 2,
    ):
        self.data_root = Path(data_root)
        self.transform_macro = transform_macro
        self.transform_micro = transform_micro
        self.is_train = is_train
        self.micro_weight = micro_weight
        self.num_macro_views = num_macro_views
        self.num_micro_views = num_micro_views

        # 加载标注
        ann_path = self.data_root / annotation_file
        with open(ann_path, 'r', encoding='utf-8') as f:
            self.annotations = json.load(f)

        # 按件分组，区分 macro/micro 图片
        self.pieces: List[Dict[str, Any]] = []
        for ann in self.annotations:
            macro_imgs = []
            micro_imgs = []
            for img_path, img_type in zip(ann['images'], ann['image_types']):
                if img_type == 'micro':
                    micro_imgs.append(str(self.data_root / 'images' / img_path))
                else:
                    macro_imgs.append(str(self.data_root / 'images' / img_path))

            self.pieces.append({
                'label_code': ann['label_code'],
                'era_code': ann['era_code'],
                'era_group': ann.get('era_group', 0),
                'authenticity': 0 if ann['authenticity'] == '真老' else 1,
                'macro_images': macro_imgs,
                'micro_images': micro_imgs,
            })

        # 年代索引 —> 列表索引映射 (用于分层采样)
        self.era_to_indices: Dict[str, List[int]] = {}
        for i, piece in enumerate(self.pieces):
            era = piece['era_code']
            if era not in self.era_to_indices:
                self.era_to_indices[era] = []
            self.era_to_indices[era].append(i)

    def __len__(self) -> int:
        return len(self.pieces)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        piece = self.pieces[idx]

        # ── 采样宏观图 ──
        macro_paths = self._sample_images(
            piece['macro_images'], self.num_macro_views
        )
        macro_tensors = []
        for path in macro_paths:
            img = Image.open(path).convert('RGB')
            if self.transform_macro:
                img = self.transform_macro(img)
            macro_tensors.append(img)

        # ── 采样微距图并切 tile ──
        micro_paths = self._sample_images(
            piece['micro_images'], self.num_micro_views
        )
        micro_tensors = []
        for path in micro_paths:
            img = Image.open(path).convert('RGB')
            tiles = self._tile_image(img)  # List[PIL.Image]
            tile_tensors = []
            for tile in tiles:
                if self.transform_micro:
                    tile = self.transform_micro(tile)
                tile_tensors.append(tile)
            # 每张微距图的所有 tile
            if tile_tensors:
                micro_tensors.append(torch.stack(tile_tensors))
            else:
                # fallback: transform directly
                micro_tensors.append(
                    self.transform_micro(img).unsqueeze(0)
                    if self.transform_micro
                    else torch.zeros(1, 3, 224, 224)
                )

        return {
            'era_code': piece['era_code'],
            'era_group': piece['era_group'],
            'authenticity': piece['authenticity'],
            'macro_images': torch.stack(macro_tensors) if macro_tensors else torch.zeros(0, 3, 512, 512),
            'micro_tiles': micro_tensors,  # List[Tensor(N_tiles, C, H, W)]
        }

    def _sample_images(self, images: List[str], n: int) -> List[str]:
        """从图片列表中采样 n 张。训练时随机，验证时取前 n 张。"""
        if not images:
            return []
        if self.is_train:
            if len(images) <= n:
                return images
            return random.sample(images, n)
        else:
            return images[:n]

    @staticmethod
    def _tile_image(img: Image.Image, tile_size: int = 224, stride: int = 112) -> List[Image.Image]:
        """将高分辨率微距图切分为重叠 tile。"""
        w, h = img.size
        tiles = []
        for y in range(0, h - tile_size + 1, stride):
            for x in range(0, w - tile_size + 1, stride):
                tile = img.crop((x, y, x + tile_size, y + tile_size))
                tiles.append(tile)
        # 如果图片太小无法切 tile，直接 resize
        if not tiles:
            tiles = [img.resize((tile_size, tile_size))]
        return tiles


def collate_multiview_batch(batch: List[Dict]) -> Dict[str, Any]:
    """
    自定义 batch collate 函数。
    处理变长 macro 图片数和变长 micro tile 数。

    Returns:
        dict with:
            era_code: List[str], era_group: Tensor(N,), authenticity: Tensor(N,),
            macro_images: Tensor(N, max_m, 3, 512, 512)  (padded)
            micro_tiles: List[List[Tensor]]  (嵌套列表)
            macro_mask: Tensor(N, max_m)  (有效 macro 图 mask)
    """
    N = len(batch)

    era_codes = [b['era_code'] for b in batch]
    era_groups = torch.tensor([b['era_group'] for b in batch], dtype=torch.long)
    authenticity = torch.tensor([b['authenticity'] for b in batch], dtype=torch.long)

    # 宏观图: pad 到相同数量
    max_macro = max(b['macro_images'].shape[0] for b in batch)
    macro_padded = []
    macro_mask = []
    for b in batch:
        m = b['macro_images']
        if m.shape[0] > 0:
            pad = torch.zeros(max_macro - m.shape[0], *m.shape[1:])
            macro_padded.append(torch.cat([m, pad]))
            mask = torch.cat([torch.ones(m.shape[0]), torch.zeros(max_macro - m.shape[0])])
        else:
            macro_padded.append(torch.zeros(max_macro, 3, 512, 512))
            mask = torch.zeros(max_macro)
        macro_mask.append(mask)

    macro_images = torch.stack(macro_padded)
    macro_mask = torch.stack(macro_mask)

    # 微距图: 保留嵌套结构（各张微距图 tile 数不同）
    micro_tiles = [b['micro_tiles'] for b in batch]

    return {
        'era_code': era_codes,
        'era_group': era_groups,
        'authenticity': authenticity,
        'macro_images': macro_images,
        'macro_mask': macro_mask,
        'micro_tiles': micro_tiles,
    }
