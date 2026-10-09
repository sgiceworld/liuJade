/**
 * 古玉鉴真 — 移动端配置
 */

/** PC 服务器地址:
 * - Android 模拟器: 10.0.2.2 映射宿主机回环
 * - 真机 (USB): adb reverse tcp:8720 tcp:8720 后可用 localhost
 * - 真机 (LAN): PC 局域网 IP (服务器需 JADE_HOST=0.0.0.0 启动)
 * 可在设置页覆盖。
 */
export const DEFAULT_SERVER_BASE = 'http://10.0.2.2:8720';

/** 混合推理阈值 (低置信时提示送服务器复核) */
export const ERA_CONF_THRESHOLD = 0.5;
export const AUTH_CONF_THRESHOLD = 0.6;

/** 移动端 INT8 模型清单 (与服务器 /models/status 一致) */
export const MOBILE_MODEL_FILES = [
  'jade_model_macro.int8.onnx',
  'jade_model_micro.int8.onnx',
  'jade_model_fusion.int8.onnx',
] as const;
