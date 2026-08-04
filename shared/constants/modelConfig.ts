/**
 * 古玉鉴真 — 模型配置常量
 * 训练和推理共用
 */

/** 输入尺寸 */
export const MACRO_INPUT_SIZE = 512;   // 宏观图输入尺寸
export const MICRO_TILE_SIZE = 224;    // 微距图 tile 尺寸
export const MICRO_TILE_STRIDE = 112;  // tile 滑动步长（50% overlap）

/** 归一化参数（ImageNet 标准，ConvNeXt-V2 预训练） */
export const IMAGENET_MEAN = [0.485, 0.456, 0.406];
export const IMAGENET_STD = [0.229, 0.224, 0.225];

/** 特征维度 */
export const FEATURE_DIM = 512;        // ConvNeXt-V2 输出特征维度
export const FUSION_DIM = 512;         // 融合后特征维度

/** 模型变体配置 */
export const MODEL_VARIANTS = {
  femto: { params_m: 78, id: 'convnextv2_femto' },
  atto: { params_m: 28, id: 'convnextv2_atto' },
  pico: { params_m: 9, id: 'convnextv2_pico' },
} as const;

/** 推理性能目标 */
export const PERF_TARGETS = {
  desktop_gpu_ms: 2000,  // GPU 推理 < 2s
  desktop_cpu_ms: 8000,  // CPU 推理 < 8s
  mobile_ms: 5000,       // 移动端 < 5s
};
