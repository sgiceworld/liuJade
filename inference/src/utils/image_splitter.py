"""
古玉鉴真 — 页面图片分割器

将扫描页面分割为:
1. 黑底玉器照片区域
2. 文字描述区域

《中国出土玉器全集》典型布局:
- 左侧/上方: 玉器照片 (黑底)
- 右侧/下方: 文字描述 (白底)
"""

import numpy as np
from PIL import Image
from pathlib import Path
from typing import Tuple, Optional


def split_page(image_path: str) -> dict:
    """
    分割页面为玉器照片区域和文字区域。

    Returns:
        dict with:
            - has_artifact: bool
            - artifact_bbox: (x0,y0,x1,y1) or None
            - artifact_path: cropped artifact image path or None
            - text_path: cropped text image path or None
            - layout: 'left-right' | 'top-bottom' | 'unknown'
    """
    img = Image.open(image_path).convert('RGB')
    arr = np.array(img)
    h, w = arr.shape[:2]

    # Detect if page has artifact photo (significant black region)
    black = (arr[:,:,0] < 30) & (arr[:,:,1] < 30) & (arr[:,:,2] < 30)
    black_pct = black.mean()

    if black_pct < 0.001:  # < 0.1% black pixels — likely text-only page
        return {'has_artifact': False, 'artifact_bbox': None,
                'artifact_path': None, 'text_path': image_path,
                'layout': 'text-only'}

    # Try left-right split (artifact on left, text on right)
    left = black[:, :w//2]
    right = black[:, w//2:]
    left_dark = left.mean()
    right_dark = right.mean()

    # Try top-bottom split (artifact on top, text on bottom)
    top = black[:h//2, :]
    bot = black[h//2:, :]
    top_dark = top.mean()
    bot_dark = bot.mean()

    # Determine layout
    if left_dark > right_dark * 1.5:
        layout = 'left-right'
        # Find the dividing column between dark and light
        col_profile = black.mean(axis=0)
        # Find where darkness drops off (transition from photo to text)
        mid = w // 3
        right_half = col_profile[mid:]
        if len(right_half) > 0 and right_half.max() > 0.001:
            drop_pt = mid + np.argmax(right_half < col_profile[mid:].max() * 0.2)
            if drop_pt > mid + 50:
                split_x = drop_pt
            else:
                split_x = w // 2  # default: center split
        else:
            split_x = w // 2

        artifact_bbox = (0, 0, min(split_x + 20, w), h)
        text_bbox = (max(0, split_x - 20), 0, w, h)

    elif top_dark > bot_dark * 1.5:
        layout = 'top-bottom'
        row_profile = black.mean(axis=1)
        mid = h // 3
        bot_half = row_profile[mid:]
        if len(bot_half) > 0 and bot_half.max() > 0.001:
            drop_pt = mid + np.argmax(bot_half < row_profile[mid:].max() * 0.2)
            if drop_pt > mid + 50:
                split_y = drop_pt
            else:
                split_y = h // 2
        else:
            split_y = h // 2

        artifact_bbox = (0, 0, w, min(split_y + 20, h))
        text_bbox = (0, max(0, split_y - 20), w, h)

    else:
        # Mixed — try to find best rectangular dark region
        layout = 'unknown'
        # Find connected dark region by looking for largest cluster
        col_profile = black.mean(axis=0)
        row_profile = black.mean(axis=1)

        dark_cols = col_profile > 0.002
        dark_rows = row_profile > 0.002

        if dark_cols.any() and dark_rows.any():
            c0 = np.argmax(dark_cols)
            c1 = w - np.argmax(dark_cols[::-1]) - 1
            r0 = np.argmax(dark_rows)
            r1 = h - np.argmax(dark_rows[::-1]) - 1

            # Ensure minimum size
            if c1 - c0 > 100 and r1 - r0 > 100:
                artifact_bbox = (max(0,c0-20), max(0,r0-20), min(w,c1+20), min(h,r1+20))
                # Text is everything else
                text_bbox = (0, 0, w, h)  # full page for reference
            else:
                artifact_bbox = (0, 0, w//2, h)
                text_bbox = (w//2, 0, w, h)
        else:
            artifact_bbox = (0, 0, w//2, h)
            text_bbox = (w//2, 0, w, h)

    # Crop images
    artifact_img = img.crop(artifact_bbox)
    text_img = img.crop(text_bbox)

    # Generate output paths
    base = Path(image_path)
    artifact_path = str(base.parent / f"{base.stem}_artifact.png")
    text_path = str(base.parent / f"{base.stem}_text.png")

    artifact_img.save(artifact_path)
    text_img.save(text_path)

    return {
        'has_artifact': True,
        'artifact_bbox': artifact_bbox,
        'artifact_path': artifact_path,
        'text_path': text_path,
        'layout': layout,
    }


def crop_artifact_only(image_path: str, output_dir: str) -> Optional[str]:
    """
    Extract just the artifact photo from a page, save to output_dir.
    Returns path to cropped artifact image.
    """
    result = split_page(image_path)
    if result['has_artifact'] and result['artifact_path']:
        return result['artifact_path']
    return None
