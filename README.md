# 古玉鉴真

AI 驱动的古玉鉴定与数据标注系统。

## 核心功能

- 🔬 **多视角双流鉴定**：同时分析宏观图（器型、沁色）和微距图（工痕），微距图 10× 权重
- 📊 **完整年代谱系**：14 个年代分类（文化期 A → 现代 N）+ 5 粗粒度分组
- ✅ **真伪判定**：真老 / 新仿二分类，含置信度
- ✏️ **数据标注**：结构化标注工具，标注结果分真/伪写入独立文件
- 🏛️ **88 馆藏来源**：覆盖国内外主要博物馆玉器收藏

## 技术栈

| 层级 | 技术 |
|------|------|
| 模型架构 | ConvNeXt-V2 双流 + 视角交叉注意力 |
| 训练框架 | PyTorch + PyTorch Lightning + MLflow |
| 推理引擎 | ONNX Runtime (GPU/CUDA/DirectML/CoreML) |
| 桌面应用 | Electron + React + TypeScript |
| 推理后端 | FastAPI (打包: PyInstaller) |
| 数据库 | SQLite (边缘端) / PostgreSQL (服务端) |

## 快速开始

详见 [CLAUDE.md](CLAUDE.md)

## 目录结构

```
liuJade/
├── training/    # 服务端训练
├── inference/   # 边缘端推理引擎
├── desktop/     # 桌面应用 (Electron + React)
├── shared/      # 共享类型与常量
├── models/      # ONNX 模型权重
└── docs/        # 文档
```
