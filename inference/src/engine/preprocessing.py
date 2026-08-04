"""
古玉鉴真 — 推理预处理管线

处理步骤:
1. 图片加载与格式校验
2. EXIF 方向校正
3. 色彩空间归一化到 sRGB
4. MACRO: resize 512×512, normalize
5. MICRO: tile 224×224 (stride 112), normalize per tile
"""

import io
from pathlib import Path
from typing import List, Tuple, Optional
import numpy as np
from PIL import Image, ImageOps


# ImageNet standard normalization
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def load_and_preprocess(
    image_path: str,
    target_size: int = 512,
) -> np.ndarray:
    """
    加载单张图片并预处理 (用于宏观图)。

    Returns:
        numpy array: (3, H, W) float32, RGB, ImageNet normalized
    """
    img = Image.open(image_path).convert('RGB')

    # EXIF 方向校正
    img = ImageOps.exif_transpose(img)

    # Resize
    img = img.resize((target_size, target_size), Image.BILINEAR)

    # To numpy: (H, W, 3) → (3, H, W)
    arr = np.array(img, dtype=np.float32) / 255.0
    arr = arr.transpose(2, 0, 1)  # CHW

    # Normalize
    arr = (arr - MEAN[:, None, None]) / STD[:, None, None]

    return arr.astype(np.float32)


def load_and_tile_micro(
    image_path: str,
    tile_size: int = 224,
    stride: int = 112,
) -> List[np.ndarray]:
    """
    加载微距图并切分为重叠 tile。

    Returns:
        List of tiles: 每个 tile (3, 224, 224) float32, normalized
    """
    img = Image.open(image_path).convert('RGB')
    img = ImageOps.exif_transpose(img)

    w, h = img.size
    tiles = []

    for y in range(0, h - tile_size + 1, stride):
        for x in range(0, w - tile_size + 1, stride):
            tile = img.crop((x, y, x + tile_size, y + tile_size))

            # To numpy
            arr = np.array(tile, dtype=np.float32) / 255.0
            arr = arr.transpose(2, 0, 1)

            # Normalize
            arr = (arr - MEAN[:, None, None]) / STD[:, None, None]
            tiles.append(arr.astype(np.float32))

    # 如果图片太小，直接 resize
    if not tiles:
        img_resized = img.resize((tile_size, tile_size), Image.BILINEAR)
        arr = np.array(img_resized, dtype=np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)
        arr = (arr - MEAN[:, None, None]) / STD[:, None, None]
        tiles.append(arr.astype(np.float32))

    return tiles


def validate_image(image_path: str) -> Tuple[bool, str]:
    """
    校验图片文件。

    Returns:
        (valid, error_message)
    """
    try:
        img = Image.open(image_path)
        w, h = img.size

        if w < 300 or h < 300:
            return False, f"图片分辨率过低: {w}×{h} (最低 300×300)"

        if img.format not in ('JPEG', 'PNG', 'HEIC', 'HEIF', 'BMP', 'TIFF'):
            return False, f"不支持的图片格式: {img.format}"

        return True, ""
    except Exception as e:
        return False, f"无法读取图片: {str(e)}"


def detect_is_micro(image_path: str, threshold_mp: float = 8.0) -> bool:
    """
    自动检测是否为微距图 (基于分辨率阈值)。

    微距图通常分辨率较高 (> 8MP)，或图片中细节占比大。
    """
    try:
        img = Image.open(image_path)
        w, h = img.size
        megapixels = (w * h) / 1_000_000
        return megapixels >= threshold_mp
    except Exception:
        return False
