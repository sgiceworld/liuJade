"""
古玉鉴真 — ONNX Runtime 推理引擎

协调三个 ONNX 子模型的推理流程:
1. MACRO 流: 提取宏观图特征
2. MICRO 流: 提取微距 tile 特征 → 池化
3. Fusion+Heads: 融合特征 → 年代/真伪预测
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np

from .preprocessing import load_and_preprocess, load_and_tile_micro
from .model_manager import ModelManager


class JadeInferenceEngine:
    """古玉鉴真推理引擎。

    使用 ONNX Runtime 在边缘端执行推理。
    支持 GPU (CUDA/DirectML/CoreML) 和 CPU 回退。

    Usage:
        engine = JadeInferenceEngine(model_dir='models/')
        result = engine.authenticate(
            macro_images=['img1.jpg', 'img2.jpg'],
            micro_images=['micro1.jpg'],
        )
    """

    def __init__(self, model_dir: str):
        self.model_dir = Path(model_dir)
        self.model_manager = ModelManager(str(model_dir))

        # 加载元数据
        meta_path = self.model_dir / 'jade_model_metadata.json'
        with open(meta_path, 'r') as f:
            self.metadata = json.load(f)

    def authenticate(
        self,
        macro_image_paths: List[str],
        micro_image_paths: List[str],
    ) -> Dict[str, Any]:
        """
        对一件玉器执行完整鉴定。

        Args:
            macro_image_paths: 宏观图路径列表 (3-5张推荐)
            micro_image_paths: 微距图路径列表 (1-3张推荐)

        Returns:
            dict with predicted_era, era_probabilities, authenticity, etc.
        """
        import time
        start_time = time.time()

        # ── 1. 预处理宏观图 ──
        macro_tensors = []
        for path in macro_image_paths:
            tensor = load_and_preprocess(path, target_size=512)
            macro_tensors.append(tensor)
        macro_batch = np.stack(macro_tensors)  # (N_m, 3, 512, 512)

        # ── 2. 预处理微距图 ──
        all_micro_tiles = []  # List[List[np.ndarray]]
        for path in micro_image_paths:
            tiles = load_and_tile_micro(path)
            all_micro_tiles.append(tiles)

        # ── 3. MACRO 流推理 ──
        macro_features = []  # List of (D,)
        for i in range(macro_batch.shape[0]):
            feat = self.model_manager.run_macro(macro_batch[i:i+1])
            macro_features.append(feat)
        macro_features = np.stack(macro_features, axis=0)  # (N_m, D)

        # ── 4. MICRO 流推理 ──
        micro_features = []  # List of (D,)
        for tiles in all_micro_tiles:
            tile_features = []
            for tile in tiles:
                feat = self.model_manager.run_micro(tile[np.newaxis, ...])
                tile_features.append(feat)
            if tile_features:
                # 均值池化 → 该微距图的特征
                img_feat = np.mean(np.concatenate(tile_features, axis=0), axis=0)
            else:
                img_feat = np.zeros(self.metadata['output_specs']['feature_dim'], dtype=np.float32)
            micro_features.append(img_feat)

        if micro_features:
            micro_features = np.stack(micro_features, axis=0)  # (N_u, D)
        else:
            micro_features = np.zeros((1, self.metadata['output_specs']['feature_dim']), dtype=np.float32)

        # ── 5. 融合 + 分类头推理 ──
        N_m = macro_features.shape[0]
        N_u = micro_features.shape[0]
        D = macro_features.shape[1]

        macro_features_batch = macro_features[np.newaxis, ...]  # (1, N_m, D)
        micro_features_batch = micro_features[np.newaxis, ...]  # (1, N_u, D)
        macro_mask = np.ones((1, N_m), dtype=np.float32)
        micro_mask = np.ones((1, N_u), dtype=np.float32)

        era_fine, era_coarse, auth_logits = self.model_manager.run_fusion(
            macro_features_batch, micro_features_batch,
            macro_mask, micro_mask,
        )

        # ── 6. 后处理 ──
        # Softmax
        era_probs = self._softmax(era_fine[0])
        auth_probs = self._softmax(auth_logits[0])

        predicted_era_idx = int(np.argmax(era_probs))
        predicted_auth_idx = int(np.argmax(auth_probs))

        era_code_list = ['A','B','C','D','E','F','G','H','I','J','K','L','M','N']
        era_names_list = [
            '文化期','商代','春秋','战国','秦汉',
            '三国两晋南北朝','唐','宋','金元','明',
            '清','民国','出口创汇','现代',
        ]

        inference_time_ms = int((time.time() - start_time) * 1000)

        return {
            'predicted_era': era_names_list[predicted_era_idx],
            'era_code': era_code_list[predicted_era_idx],
            'era_probabilities': {
                era_code_list[i]: float(era_probs[i])
                for i in range(len(era_code_list))
            },
            'predicted_authenticity': '真老' if predicted_auth_idx == 0 else '新仿',
            'authenticity_confidence': float(max(auth_probs)),
            'macro_features_analyzed': N_m,
            'micro_features_analyzed': N_u,
            'inference_time_ms': inference_time_ms,
            'top3_eras': self._top_k(era_probs, era_code_list, era_names_list, k=3),
        }

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        e_x = np.exp(x - np.max(x))
        return e_x / e_x.sum()

    @staticmethod
    def _top_k(
        probs: np.ndarray,
        codes: List[str],
        names: List[str],
        k: int = 3,
    ) -> List[Dict]:
        indices = np.argsort(probs)[::-1][:k]
        return [
            {
                'era_code': codes[i],
                'era_name': names[i],
                'probability': float(probs[i]),
            }
            for i in indices
        ]
