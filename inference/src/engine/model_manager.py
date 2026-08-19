"""
古玉鉴真 — 模型管理器

管理 ONNX 模型的加载、缓存、切换和版本管理。
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime

import numpy as np
import onnxruntime as ort


class ModelManager:
    """ONNX 模型管理器。

    加载和缓存三个 ONNX 子模型:
    - MACRO 流: 宏观图特征提取
    - MICRO 流: 微距 tile 特征提取
    - Fusion+Heads: 特征融合与分类
    """

    def __init__(self, model_dir: str):
        self.model_dir = Path(model_dir)

        # 加载元数据
        meta_path = self.model_dir / 'jade_model_metadata.json'
        with open(meta_path, 'r') as f:
            self.metadata = json.load(f)

        # 创建 ONNX Runtime Session (自动选择最佳 provider)
        self.providers = self._get_providers()

        # 加载三个子模型
        self.macro_session = self._load_session(
            self.model_dir / self.metadata['macro_onnx']
        )
        self.micro_session = self._load_session(
            self.model_dir / self.metadata['micro_onnx']
        )
        self.fusion_session = self._load_session(
            self.model_dir / self.metadata['fusion_onnx']
        )

    @staticmethod
    def _get_providers() -> list:
        """按优先级获取可用的执行 provider。"""
        available = ort.get_available_providers()
        priority = [
            'CUDAExecutionProvider',
            'DmlExecutionProvider',      # DirectML (Windows GPU)
            'CoreMLExecutionProvider',    # Apple Silicon
            'CPUExecutionProvider',
        ]
        selected = [p for p in priority if p in available]
        return selected

    def _load_session(self, path: Path) -> ort.InferenceSession:
        """加载 ONNX 模型 session。"""
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )
        # 使用多线程加速
        sess_options.intra_op_num_threads = 4

        return ort.InferenceSession(
            str(path),
            sess_options=sess_options,
            providers=self.providers,
        )

    def run_macro(self, image: np.ndarray) -> np.ndarray:
        """
        运行 MACRO 流推理。

        Args:
            image: (1, 3, 512, 512) float32

        Returns:
            features: (D,) float32 (单图特征向量, 已压缩 batch 维)
        """
        outputs = self.macro_session.run(
            ['macro_features'],
            {'macro_image': image},
        )
        return outputs[0][0]

    def run_micro(self, tile: np.ndarray) -> np.ndarray:
        """
        运行 MICRO 流推理 (单个 tile)。

        Args:
            tile: (1, 3, 224, 224) float32

        Returns:
            features: (1, D) float32
        """
        outputs = self.micro_session.run(
            ['tile_features'],
            {'micro_tile': tile},
        )
        return outputs[0]

    def run_fusion(
        self,
        macro_features: np.ndarray,
        micro_features: np.ndarray,
        macro_mask: np.ndarray,
        micro_mask: np.ndarray,
    ) -> tuple:
        """
        运行融合 + 分类头。

        Args:
            macro_features: (B, N_m, D)
            micro_features: (B, N_u, D)
            macro_mask: (B, N_m)
            micro_mask: (B, N_u)

        Returns:
            (era_fine, era_coarse, authenticity) — 三个 logits 数组
        """
        outputs = self.fusion_session.run(
            ['era_fine', 'era_coarse', 'authenticity'],
            {
                'macro_features': macro_features.astype(np.float32),
                'micro_features': micro_features.astype(np.float32),
                'macro_mask': macro_mask.astype(np.float32),
                'micro_mask': micro_mask.astype(np.float32),
            },
        )
        return outputs[0], outputs[1], outputs[2]

    def get_version_info(self) -> Dict[str, Any]:
        """获取当前模型版本信息。"""
        # 检查 version file
        version_path = self.model_dir / 'version.json'
        if version_path.exists():
            with open(version_path) as f:
                return json.load(f)

        # 如果没有 version.json，用 checksum
        return {
            'version': 'unknow',
            'checksums': {
                'macro': self._compute_checksum(self.model_dir / self.metadata['macro_onnx']),
                'micro': self._compute_checksum(self.model_dir / self.metadata['micro_onnx']),
                'fusion': self._compute_checksum(self.model_dir / self.metadata['fusion_onnx']),
            },
        }

    @staticmethod
    def _compute_checksum(path: Path) -> str:
        """计算文件 SHA256。"""
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
