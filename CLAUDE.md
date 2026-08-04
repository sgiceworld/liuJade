# 古玉鉴真 (Ancient Jade Authentication)

AI-powered ancient Chinese jade authentication and data annotation system.

## Architecture

- **Model**: Multi-view two-stream ConvNeXt-V2 (MACRO 512×512 + MICRO 224×224 tiles) with View-Level Cross-Attention fusion
- **Era classification**: 14 classes (文化期 A → 现代 N) + 5 coarse groups
- **Authenticity**: Binary (真老 genuine / 新仿 fake)
- **Deployment**: ONNX Runtime for edge inference (GPU/CUDA → CPU fallback → INT8 mobile)

## Project Structure

```
liuJade/
├── training/       # Server-side PyTorch training pipeline
├── inference/      # Edge-side ONNX Runtime inference engine + FastAPI
├── desktop/        # Electron + React desktop application
├── shared/         # Shared TypeScript types and constants
├── models/         # ONNX model weights (git-lfs)
├── docs/           # Documentation
└── infrastructure/ # Docker/k8s deployment configs
```

## Key Conventions

### Label Code Format
```
{authenticity}_{login_number}_{datetime}_{era_code}_{sequence}
Example: 0_JY20260802000001_20260802143025_G_001
```
- authenticity: `0`=真老, `1`=新仿
- login_number: JY + YYYYMMDD + 6-digit sequence
- era_code: A=文化期, B=商代, ..., N=现代

### Annotation Fields
1. Product name: era + material + type (e.g., 清和田玉三羊开泰摆件)
2. Material: 12 enumerated types
3. Dimensions: JSON {长, 宽, 高, 厚, 直径} in mm
4. Source: 馆藏 / 拍卖 / 著录 + detail

### Annotation Files
- `genuine.jsonl` — 真老 records, appended continuously
- `fake.jsonl` — 新仿 records, appended continuously

### Training Pipeline (4 Stages)
1. ImageNet-22K pretrained weights
2. Macro images → Era head (50 epochs)
3. Micro tile images at 10× weight → Micro stream (30 epochs)
4. Multi-view joint → All modules (40 epochs)

### Scraping Ethics
- Identify as academic research (JadeResearchBot/1.0)
- Random delay 3-8s between requests
- No concurrency, no proxy rotation, single thread
- Max 500 requests/day per domain
- Respect robots.txt

## Setup

### Training
```bash
cd training
pip install -e ".[dev]"
python scripts/train.sh  # Stage-based training
```

### Inference
```bash
cd inference
pip install onnxruntime Pillow fastapi uvicorn
python src/api/server.py  # Start at localhost:8720
```

### Desktop
```bash
cd desktop
npm install
npm run dev   # Dev mode with Vite + Electron
```
