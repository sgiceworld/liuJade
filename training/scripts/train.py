#!/usr/bin/env python3
"""
古玉鉴真 — 训练入口

四阶段训练:
  阶段2: 宏观图 → 年代头 (冻结微距流)
  阶段3: 微距图 → 微距流 + 年代头 (冻结宏观流)
  阶段4: 多视角联合 → 全部模块

用法:
    cd training
    python scripts/train.py --config configs/base.yaml [--stage 4] [--epochs 40]

或直接命令行覆盖:
    python scripts/train.py --stage 2 --epochs 50 --batch-size 8 --lr 0.0001
"""

import argparse
import sys
import warnings
from pathlib import Path

import yaml
import torch

# training/src 加入 path (对齐 smoke_test 的导入方式)
SRC = Path(__file__).resolve().parent.parent / 'src'
sys.path.insert(0, str(SRC))

import pytorch_lightning as pl  # noqa: E402

from models import JadeAuthModel  # noqa: E402
from training.trainer import JadeAuthTrainer  # noqa: E402
from data.dataset import JadeMultiViewDataset, collate_multiview_batch  # noqa: E402
from data.transforms import (  # noqa: E402
    get_train_transforms, get_val_transforms,
    get_micro_train_transforms, get_micro_val_transforms,
)


def load_config(path: Path) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def build_model(cfg: dict, no_pretrained: bool) -> JadeAuthModel:
    """实例化双流模型; 预训练权重下载失败时自动回退随机初始化。"""
    if not no_pretrained:
        try:
            return JadeAuthModel(
                macro_backbone=cfg['model']['macro_backbone'],
                micro_backbone=cfg['model']['micro_backbone'],
                feature_dim=cfg['model']['feature_dim'],
                dropout=cfg['model']['dropout'],
            )
        except Exception as e:
            warnings.warn(f"预训练权重加载失败 ({e}); 回退随机初始化")
    return _build_from_scratch(cfg)


def _build_from_scratch(cfg: dict) -> JadeAuthModel:
    """随机初始化组装 JadeAuthModel (不触发 timm 权重下载)。"""
    from models.jade_model import JadeAuthModel as JAM
    from models.macro_stream import MacroStream
    from models.micro_stream import MicroStream
    from models.fusion import ViewCrossAttention
    from models.heads import EraHead, AuthHead

    model = JAM.__new__(JAM)  # 跳过 __init__ (避免 pretrained 下载)
    D = cfg['model']['feature_dim']
    model.feature_dim = D
    model.macro_stream = MacroStream(
        backbone_variant=cfg['model']['macro_backbone'],
        pretrained=False, output_dim=D,
    )
    model.micro_stream = MicroStream(
        backbone_variant=cfg['model']['micro_backbone'],
        pretrained=False, output_dim=D,
    )
    model.fusion = ViewCrossAttention(feature_dim=D, num_heads=8,
                                      dropout=cfg['model']['dropout'])
    model.era_head = EraHead(input_dim=D, hidden_dim=256,
                             num_fine=14, num_coarse=5,
                             dropout=cfg['model']['dropout'])
    model.auth_head = AuthHead(input_dim=D, hidden_dim=128,
                               dropout=cfg['model']['dropout'])
    return model


def main():
    ap = argparse.ArgumentParser(description='古玉鉴真训练')
    ap.add_argument('--config', type=Path, default=SRC.parent / 'configs' / 'base.yaml')
    ap.add_argument('--data-root', type=Path, default=None,
                    help='数据目录 (含 annotations.json + images/), 默认 config 中 data.data_root')
    ap.add_argument('--ann-file', type=str, default=None,
                    help='标注文件名 (默认 annotations.json)')
    ap.add_argument('--stage', type=int, default=None,
                    choices=[2, 3, 4], help='训练阶段 2/3/4')
    ap.add_argument('--epochs', type=int, default=None)
    ap.add_argument('--batch-size', type=int, default=None)
    ap.add_argument('--lr', type=float, default=None)
    ap.add_argument('--num-workers', type=int, default=0)
    ap.add_argument('--no-pretrained', action='store_true',
                    help='不加载 ImageNet 预训练权重')
    ap.add_argument('--smoke', action='store_true',
                    help='冒烟模式: 1 epoch / 2 batch, 快速验证管线')
    ap.add_argument('--export-onnx', action='store_true',
                    help='训练完成后导出 ONNX 到 models/jade_model')
    ap.add_argument('--export-only', type=Path, default=None,
                    help='不训练, 直接从 checkpoint 导出 ONNX 后退出')
    ap.add_argument('--output-dir', type=Path, default=None,
                    help='checkpoint 输出目录 (默认 models/checkpoints)')
    ap.add_argument('--seed', type=int, default=42)
    args = ap.parse_args()

    cfg = load_config(args.config)

    # 合并 CLI 覆盖
    stage = args.stage or cfg['training']['stage']
    epochs = 1 if args.smoke else (args.epochs or cfg['training']['epochs'])
    batch_size = args.batch_size or cfg['training']['batch_size']
    lr = args.lr if args.lr is not None else cfg['training']['learning_rate']
    data_root = args.data_root or Path(cfg['data']['data_root'])
    ann_file = args.ann_file or 'annotations.json'

    pl.seed_everything(args.seed)
    torch.set_num_threads(max(1, (torch.get_num_threads() or 8)))

    print(f"配置: stage={stage}, epochs={epochs}, batch={batch_size}, lr={lr}")
    print(f"数据: {data_root}/{ann_file}")
    print(f"后端: {'CUDA' if torch.cuda.is_available() else 'CPU'} "
          f"(线程 {torch.get_num_threads()})")

    # ── 数据 ──
    macro_tf = get_train_transforms()
    micro_tf = get_micro_train_transforms()

    if not (data_root / ann_file).exists():
        raise SystemExit(
            f"标注文件不存在: {data_root / ann_file}\n"
            f"请先运行: python scripts/prepare_data.py"
        )

    train_ds = JadeMultiViewDataset(
        data_root=str(data_root),
        annotation_file=ann_file,
        transform_macro=macro_tf,
        transform_micro=micro_tf,
        is_train=True,
        micro_weight=cfg['data']['micro_weight'],
        num_macro_views=cfg['data']['num_macro_views'],
        num_micro_views=cfg['data']['num_micro_views'],
    )
    print(f"训练样本 (件): {len(train_ds)}")

    train_loader = torch.utils.data.DataLoader(
        train_ds,
        batch_size=batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        collate_fn=collate_multiview_batch,
        drop_last=len(train_ds) > batch_size,
    )

    val_loader = None
    val_ann = data_root / 'annotations_val.json'
    if val_ann.exists():
        val_ds = JadeMultiViewDataset(
            data_root=str(data_root),
            annotation_file='annotations_val.json',
            transform_macro=get_val_transforms(),
            transform_micro=get_micro_val_transforms(),
            is_train=False,
            num_macro_views=cfg['data']['num_macro_views'],
            num_micro_views=cfg['data']['num_micro_views'],
        )
        val_loader = torch.utils.data.DataLoader(
            val_ds, batch_size=batch_size, shuffle=False,
            num_workers=args.num_workers,
            collate_fn=collate_multiview_batch,
        )
        print(f"验证样本 (件): {len(val_ds)}")

    # ── 模型 + Lightning ──
    model = build_model(cfg, args.no_pretrained)
    print("参数量:", {k: f"{v:,}" for k, v in model.get_num_params().items()})

    # ── 仅导出模式: 加载 checkpoint 权重 → ONNX → 退出 ──
    if args.export_only:
        from export import export_to_onnx
        state = torch.load(args.export_only, map_location='cpu',
                           weights_only=True)
        model.load_state_dict(state.get('state_dict', state))
        model.eval()
        export_dir = Path(__file__).resolve().parent.parent.parent / 'models'
        export_to_onnx(
            model,
            str(export_dir / 'jade_model'),
            opset_version=cfg['export']['opset_version'],
            simplify=cfg['export']['simplify'],
        )
        print(f"✓ ONNX 导出完成: {export_dir / 'jade_model'}")
        return

    warmup = 0 if (args.smoke or epochs <= 10) else cfg['training']['warmup_epochs']
    module = JadeAuthTrainer(
        model=model,
        learning_rate=lr,
        weight_decay=cfg['training']['weight_decay'],
        lr_scheduler='cosine',
        warmup_epochs=warmup,
        max_epochs=epochs,
        stage=stage,
        **cfg['loss'],
    )

    out_dir = args.output_dir or (Path(__file__).resolve().parent.parent.parent
                                  / 'models' / 'checkpoints')
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_name = f"jade_v0.1_stage{stage}" + ("_smoke" if args.smoke else "")

    checkpoint_cb = pl.callbacks.ModelCheckpoint(
        dirpath=str(out_dir),
        filename=ckpt_name,
        monitor='val/era_top1_epoch' if val_loader else 'train/era_top1',
        mode='max',
        save_top_k=1,
    )

    trainer = pl.Trainer(
        max_epochs=epochs,
        accelerator='cpu',
        logger=pl.loggers.CSVLogger(
            save_dir=str(Path(__file__).resolve().parent.parent / 'logs'),
            name='jade',
        ),
        callbacks=[checkpoint_cb],
        enable_progress_bar=True,
        log_every_n_steps=1,
        limit_train_batches=2 if args.smoke else None,
        limit_val_batches=2 if args.smoke else None,
        check_val_every_n_epoch=1 if val_loader else None,
        num_sanity_val_steps=0,
    )

    # ── 训练 ──
    trainer.fit(
        module,
        train_dataloaders=train_loader,
        val_dataloaders=val_loader,
    )

    # 手动保存最终权重 (ModelCheckpoint 无验证集时不落盘)
    final_ckpt = out_dir / f"{ckpt_name}_last.ckpt"
    torch.save({'state_dict': module.model.state_dict()}, final_ckpt)
    print(f"\n✓ 训练完成, 权重已保存: {final_ckpt}")

    # ── ONNX 导出 ──
    if args.export_onnx:
        from export import export_to_onnx

        module.model.eval()

        export_dir = Path(__file__).resolve().parent.parent.parent / 'models'
        export_to_onnx(
            module.model,
            str(export_dir / 'jade_model'),
            opset_version=cfg['export']['opset_version'],
            simplify=cfg['export']['simplify'],
        )
        print(f"✓ ONNX 导出完成: {export_dir / 'jade_model'}")


if __name__ == '__main__':
    main()
