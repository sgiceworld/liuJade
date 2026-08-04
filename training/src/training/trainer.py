"""
古玉鉴真 — PyTorch Lightning 训练模块

支持四阶段训练:
  阶段2: 宏观图 → 年代头
  阶段3: 微距图 → 微距流 + 年代头 (微距 10x)
  阶段4: 多视角联合 → 全部模块
"""

import torch
import pytorch_lightning as pl
from torch import optim
from typing import Dict, Any, Optional

from ..models.jade_model import JadeAuthModel
from .losses import MultiTaskLoss
from .metrics import (
    compute_era_accuracy,
    compute_group_accuracy,
    compute_auth_metrics,
    compute_per_era_accuracy,
    aggregate_metrics,
)


class JadeAuthTrainer(pl.LightningModule):
    """古玉鉴真 Lightning 训练模块。"""

    def __init__(
        self,
        model: JadeAuthModel,
        learning_rate: float = 1e-4,
        weight_decay: float = 0.01,
        lr_scheduler: str = 'cosine',
        warmup_epochs: int = 5,
        max_epochs: int = 40,
        stage: int = 4,  # 训练阶段 2/3/4
        **loss_kwargs,
    ):
        super().__init__()
        self.save_hyperparameters(ignore=['model'])

        self.model = model
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.lr_scheduler_name = lr_scheduler
        self.warmup_epochs = warmup_epochs
        self.max_epochs = max_epochs
        self.stage = stage

        self.criterion = MultiTaskLoss(**loss_kwargs)

        # 记录验证集指标
        self.val_metrics = []

    def forward(self, macro_images, micro_tiles, macro_mask=None, micro_mask=None):
        return self.model(macro_images, micro_tiles, macro_mask, micro_mask)

    def training_step(self, batch, batch_idx):
        outputs = self._shared_step(batch)
        loss = outputs['loss']

        # 日志
        self.log('train/loss_total', loss['total'], prog_bar=True)
        self.log('train/loss_era', loss['era'])
        self.log('train/loss_auth', loss['auth'])

        # 准确率
        metrics = outputs['metrics']
        self.log('train/era_top1', metrics['era_top1'], prog_bar=True)
        self.log('train/auth_f1', metrics['auth_f1'])

        return loss['total']

    def validation_step(self, batch, batch_idx):
        outputs = self._shared_step(batch)
        loss = outputs['loss']

        self.log('val/loss_total', loss['total'], prog_bar=True)
        self.log('val/loss_era', loss['era'])
        self.log('val/loss_auth', loss['auth'])

        metrics = outputs['metrics']
        self.log('val/era_top1', metrics['era_top1'], prog_bar=True)
        self.log('val/era_top3', metrics['era_top3'])
        self.log('val/auth_f1', metrics['auth_f1'], prog_bar=True)
        self.log('val/auth_precision', metrics['auth_precision'])
        self.log('val/auth_recall', metrics['auth_recall'])

        self.val_metrics.append(metrics)

    def on_validation_epoch_end(self):
        if self.val_metrics:
            aggregated = aggregate_metrics(self.val_metrics)
            self.log('val/era_top1_epoch', aggregated['era_top1'])
            self.log('val/auth_f1_epoch', aggregated['auth_f1'])
            self.val_metrics = []

    def _shared_step(self, batch) -> Dict[str, Any]:
        macro_images = batch['macro_images']
        micro_tiles = batch['micro_tiles']
        macro_mask = batch.get('macro_mask')
        era_targets = batch['era_group']  # 此处实际是细粒度年代索引
        auth_targets = batch['authenticity']

        # 根据训练阶段选择性冻结
        if self.stage == 2:
            # 仅训练宏观流 + 年代头
            outputs = self.model(macro_images, micro_tiles, macro_mask)
            era_fine = outputs['era_fine']
            era_coarse = outputs['era_coarse']
            auth_preds = outputs['authenticity']

            # 微距流输出用 zeros (不参与 loss 计算)
            loss = self.criterion(
                era_fine, era_coarse, auth_preds,
                outputs['fused'],
                era_targets,
                torch.tensor([0] * len(era_targets)),  # coarse targets — 需从 batch 获取
                auth_targets,
            )
        elif self.stage == 3:
            # 训练微距流 + 年代头
            outputs = self.model(macro_images, micro_tiles, macro_mask)
            era_fine = outputs['era_fine']
            era_coarse = outputs['era_coarse']
            auth_preds = outputs['authenticity']

            loss = self.criterion(
                era_fine, era_coarse, auth_preds,
                outputs['fused'],
                era_targets,
                torch.tensor([0] * len(era_targets)),
                auth_targets,
            )
        else:
            # 阶段4: 全模块训练
            outputs = self.model(macro_images, micro_tiles, macro_mask)
            era_fine = outputs['era_fine']
            era_coarse = outputs['era_coarse']
            auth_preds = outputs['authenticity']

            loss = self.criterion(
                era_fine, era_coarse, auth_preds,
                outputs['fused'],
                era_targets,
                torch.tensor([0] * len(era_targets)),
                auth_targets,
            )

        metrics = {
            **compute_era_accuracy(era_fine, era_targets),
            **compute_auth_metrics(auth_preds, auth_targets),
        }

        return {'loss': loss, 'metrics': metrics, 'outputs': outputs}

    def configure_optimizers(self):
        # AdamW with weight decay
        optimizer = optim.AdamW(
            self.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay,
        )

        if self.lr_scheduler_name == 'cosine':
            scheduler = optim.lr_scheduler.CosineAnnealingLR(
                optimizer,
                T_max=self.max_epochs - self.warmup_epochs,
            )
        elif self.lr_scheduler_name == 'onecycle':
            scheduler = optim.lr_scheduler.OneCycleLR(
                optimizer,
                max_lr=self.learning_rate,
                total_steps=self.trainer.estimated_stepping_batches,
            )
        else:
            return optimizer

        # Warmup
        if self.warmup_epochs > 0:
            warmup = optim.lr_scheduler.LinearLR(
                optimizer,
                start_factor=0.1,
                total_iters=self.warmup_epochs,
            )
            scheduler = optim.lr_scheduler.SequentialLR(
                optimizer,
                schedulers=[warmup, scheduler],
                milestones=[self.warmup_epochs],
            )

        return {
            'optimizer': optimizer,
            'lr_scheduler': {
                'scheduler': scheduler,
                'interval': 'epoch',
            },
        }
