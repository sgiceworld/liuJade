# 古玉鉴真 — 移动端 (React Native, Android)

现场拍照鉴定 + 藏品图鉴浏览 + 样品采集。混合推理:端侧 INT8 (NNAPI→CPU) 优先,
失败/低置信回退 PC 服务器 FP32 (FastAPI:8720)。

## 环境准备 (Windows, 本机已就绪)

1. Android SDK: `C:\Users\LiuCN\AppData\Local\Android\Sdk` (platform 35+36, build-tools 35/36, platform-tools)
2. **JDK 17**: `C:\Users\LiuCN\AppData\Local\Programs\jdk-17\jdk-17.0.2`
   (Android Studio 自带 jbr 25 超出 Gradle 支持; gradle.properties 已写死 org.gradle.java.home)
3. Node ≥18: `desktop/.nodeenv/Scripts/node.exe` 加入 PATH
4. **国内镜像** (已配好, 无需重复操作):
   - gradle 发行版: `gradle-wrapper.properties` → mirrors.cloud.tencent.com
   - Maven 仓库: `C:\Users\LiuCN\.gradle\init.gradle` (阿里云全局镜像) + `patches/` 固化 RN gradle-plugin 仓库补丁
   - npm: 走系统代理 (Clash) 或直连

## 依赖与运行

```bash
export PATH="/d/liuJade/desktop/.nodeenv/Scripts:$PATH"
cd mobile/react-native
npm install
npm run android        # 连接模拟器或真机 (USB 调试)
```

## 连接 PC 服务器

| 场景 | 服务器地址 (设置页) | 说明 |
|---|---|---|
| Android 模拟器 | `http://10.0.2.2:8720` (默认) | 10.0.2.2 映射宿主机回环 |
| 真机 USB | `http://localhost:8720` | 先 `adb reverse tcp:8720 tcp:8720` |
| 真机 LAN | `http://<PC局域网IP>:8720` | PC 端 `JADE_HOST=0.0.0.0 python -m uvicorn src.api.server:app` |

## 模型更新流程

1. 训练侧: `python scripts/train.py --config configs/mobile.yaml --name jade_v0.2_pico --export-only <ckpt>`
2. 量化: `cd inference && python scripts/quantize_models.py`
3. 验收: `python scripts/verify_quantized.py` (门禁全过才算合格)
4. 手机端: 设置页 →「下载/校验 INT8 模型」(SHA256 对比 `/models/status` 清单)

## 与服务器的预处理一致性

- 宏观: stretch resize 512×512 + EXIF 校正 + ImageNet 归一化 (常数来自 `shared/constants/modelConfig.ts`)
- 微距: 224 tile / stride 112 滑窗 + 均值池化
- **有意偏差**: 端侧微距 tile 上限 64 个 (长边 ≤1008px), 服务器全分辨率无上限
  (手机 700+ tiles 不可行)。低于 224px 的图整张 resize 成 1 个 tile, 两端一致。

## 目录结构

```
src/
├─ config.ts                 # 服务器地址/阈值/模型清单
├─ navigation/RootNavigator.tsx
├─ screens/                  # Identify/Gallery/PieceDetail/Collect/Settings/Result
├─ components/               # (预留)
├─ services/                 # serverClient.ts (ApiResponse 契约) + identifyFlow.ts (混合流程)
├─ localInference/           # modelStore (分发+SHA256) / preprocess / engine (三阶段)
├─ cache/                    # galleryCache (图鉴快照) + collectQueue (离线采集队列)
└─ store/                    # zustand
```

shared/ 常量经 Metro watchFolders 直接相对路径引用, 不内联重复。
