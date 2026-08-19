#!/usr/bin/env bash
# 古玉鉴真 — 训练入口 (阶段化训练)
#
# 用法:
#   bash scripts/train.sh            # 使用 configs/base.yaml 默认配置
#   bash scripts/train.sh 2 50       # 阶段2, 50 epochs
#   bash scripts/train.sh 4 40 "--export-onnx"   # 阶段4 + ONNX 导出
#
# 前置: python scripts/prepare_data.py 已生成 training/data/annotations.json

set -e
cd "$(dirname "$0")/.."

STAGE="${1:-4}"
EPOCHS="${2:-40}"
EXTRA="${3:-}"

echo "== 古玉鉴真训练: stage=$STAGE epochs=$EPOCHS $EXTRA =="
python scripts/train.py \
  --config configs/base.yaml \
  --stage "$STAGE" \
  --epochs "$EPOCHS" \
  $EXTRA
