/**
 * 古玉鉴真 — 端侧三阶段推理引擎
 * 编排逐行对照 inference/src/engine/inference.py::authenticate
 *
 * 张量契约 (model_manager.py):
 *   macro:  macro_image [1,3,512,512] → macro_features [1,512]
 *   micro:  micro_tile  [1,3,224,224] → tile_features  [1,512]
 *   fusion: macro_features [1,N,512] + micro_features [1,M,512]
 *           + 全 1 masks → era_fine(14) / era_coarse(5) / authenticity(2)
 *
 * 注意: ORT RN 的 Tensor 只接受 TypedArray。
 */

import { InferenceSession, Tensor } from 'onnxruntime-react-native';
import { ERA_CODE, ERA_NAMES, AUTH_LABELS } from '../../../../shared/constants/eras';
import { FEATURE_DIM } from '../../../../shared/constants/modelConfig';
import { MODELS_DIR } from './modelStore';
import { preprocessMacro, preprocessMicro } from './preprocess';
import type { ServerAuthResult } from '../services/serverClient';

type SessionName = 'macro' | 'micro' | 'fusion';

const SESSION_FILES: Record<SessionName, string> = {
  macro: 'jade_model_macro.int8.onnx',
  micro: 'jade_model_micro.int8.onnx',
  fusion: 'jade_model_fusion.int8.onnx',
};

/** 会话缓存 + 双 provider 探测 (NNAPI → CPU 回退) */
class SessionManager {
  private sessions = new Map<SessionName, InferenceSession>();

  async get(name: SessionName): Promise<InferenceSession> {
    const cached = this.sessions.get(name);
    if (cached) return cached;
    const path = `${MODELS_DIR}/${SESSION_FILES[name]}`;
    let session: InferenceSession;
    try {
      // NNAPI 运行时探测 (API 27+/机型差异大), 失败回退 CPU (XNNPACK)
      session = await InferenceSession.create(path, {
        executionProviders: ['nnapi', 'cpu'],
      });
    } catch {
      session = await InferenceSession.create(path, {
        executionProviders: ['cpu'],
      });
    }
    this.sessions.set(name, session);
    return session;
  }

  release() {
    for (const s of this.sessions.values()) s.release();
    this.sessions.clear();
  }
}

export const sessionManager = new SessionManager();

function softmax(logits: Float32Array): number[] {
  const max = Math.max(...logits);
  const exps = Array.from(logits, v => Math.exp(v - max));
  const sum = exps.reduce((a, b) => a + b, 0);
  return exps.map(v => v / sum);
}

function argmax(values: number[]): number {
  let best = 0;
  for (let i = 1; i < values.length; i++) if (values[i] > values[best]) best = i;
  return best;
}

function topK(
  probs: number[],
  k: number,
): Array<{ code: string; name: string; prob: number }> {
  return probs
    .map((prob, i) => ({
      code: ERA_CODE[i],
      name: ERA_NAMES[ERA_CODE[i]],
      prob,
    }))
    .sort((a, b) => b.prob - a.prob)
    .slice(0, k);
}

function meanPoolFeatures(features: Float32Array[]): Float32Array {
  // 每张微距图的 tile 特征取均值池化 (对齐 inference.py)
  const n = features.length;
  const out = new Float32Array(FEATURE_DIM);
  for (const f of features) {
    for (let i = 0; i < FEATURE_DIM; i++) out[i] += f[i];
  }
  if (n > 0) for (let i = 0; i < FEATURE_DIM; i++) out[i] /= n;
  return out;
}

export interface LocalAuthResult {
  predicted_era: string;
  era_code: string;
  era_probabilities: Record<string, number>;
  predicted_authenticity: '真老' | '新仿';
  authenticity_confidence: number;
  macro_features_analyzed: number;
  micro_features_analyzed: number;
  inference_time_ms: number;
  top3_eras: Array<{ code: string; name: string; prob: number }>;
}

/** 端侧完整鉴定: 宏观图 + 微距图 → 融合 → 年代/真伪 */
export async function authenticateLocal(
  macroUri: string,
  microUri: string,
): Promise<LocalAuthResult> {
  const start = Date.now();

  // ── 预处理 (与服务端数值一致) ──
  const macroTensor = await preprocessMacro(macroUri);
  const microTiles = await preprocessMicro(microUri);

  // ── 宏观流: 1 张 → (1,512) ──
  const macroSession = await sessionManager.get('macro');
  const macroOut = await macroSession.run({
    macro_image: new Tensor('float32', macroTensor, [1, 3, 512, 512]),
  });
  const macroFeatures = macroOut.macro_features.data as Float32Array; // (1,512)

  // ── 微距流: 逐 tile → 均值池化 (无 tile → 零向量) ──
  const microSession = await sessionManager.get('micro');
  let microFeatures = new Float32Array(FEATURE_DIM);
  if (microTiles.length > 0) {
    const perTile: Float32Array[] = [];
    for (const tile of microTiles) {
      const out = await microSession.run({
        micro_tile: new Tensor('float32', tile, [1, 3, 224, 224]),
      });
      perTile.push(out.tile_features.data as Float32Array);
    }
    microFeatures = meanPoolFeatures(perTile);
  }

  // ── 融合头 (batch 恒 1, mask 恒全 1) ──
  const fusionSession = await sessionManager.get('fusion');
  const ones = (n: number) => new Float32Array(n).fill(1);
  const fusionOut = await fusionSession.run({
    macro_features: new Tensor('float32', macroFeatures, [1, 1, FEATURE_DIM]),
    micro_features: new Tensor('float32', microFeatures, [1, 1, FEATURE_DIM]),
    macro_mask: new Tensor('float32', ones(1), [1, 1]),
    micro_mask: new Tensor('float32', ones(1), [1, 1]),
  });

  const eraProbs = softmax(fusionOut.era_fine.data as Float32Array);
  const authProbs = softmax(fusionOut.authenticity.data as Float32Array);
  const eraIdx = argmax(eraProbs);
  const authIdx = argmax(authProbs);

  const eraProbabilities: Record<string, number> = {};
  ERA_CODE.forEach((code, i) => {
    eraProbabilities[code] = eraProbs[i];
  });

  return {
    predicted_era: ERA_NAMES[ERA_CODE[eraIdx]],
    era_code: ERA_CODE[eraIdx],
    era_probabilities: eraProbabilities,
    predicted_authenticity: AUTH_LABELS[(authIdx === 0 ? '0' : '1') as '0' | '1'],
    authenticity_confidence: authProbs[authIdx],
    macro_features_analyzed: 1,
    micro_features_analyzed: microTiles.length,
    inference_time_ms: Date.now() - start,
    top3_eras: topK(eraProbs, 3),
  };
}

/** 兼容 ServerAuthResult 形状 (不含 piece_id/label_code, 本地结果未落库) */
export function toPendingResultShape(
  local: LocalAuthResult,
): ServerAuthResult {
  return { ...local, piece_id: '', label_code: '本地' };
}
