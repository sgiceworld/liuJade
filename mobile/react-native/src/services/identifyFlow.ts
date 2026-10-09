/**
 * 古玉鉴真 — 混合鉴定流程
 *
 * 模式 (设置页可切):
 * - auto (默认): 本地 INT8 就绪 → 本地推理; 低置信 → 标低置信 + UI 提示复核;
 *   本地失败 (无模型/异常) → 上传图片 → 服务器 FP32 鉴定 (落库)
 * - local: 仅本地; - server: 仅服务器
 */

import {
  AUTH_CONF_THRESHOLD,
  ERA_CONF_THRESHOLD,
} from '../config';
import { modelStore } from '../localInference/modelStore';
import { authenticateLocal } from '../localInference/engine';
import { serverClient, ServerAuthResult } from './serverClient';
import type { IdentifyMode } from '../store/useAppStore';

export interface IdentifyOutcome {
  source: 'server' | 'local';
  result: ServerAuthResult;
  lowConfidence: boolean;
  /** 本地成功后自动送服务器复核落库 (auto 模式默认开) */
  serverPersistDone?: boolean;
}

export async function identify(
  base: string,
  photoUri: string,
  mode: IdentifyMode,
): Promise<IdentifyOutcome> {
  const serverFlow = async (): Promise<IdentifyOutcome> => {
    const uploaded = await serverClient.uploadImages(base, [
      { uri: photoUri, type: 'macro' },
      { uri: photoUri, type: 'micro' },
    ]);
    const macroPath = uploaded.find(i => i.type === 'macro')!.path;
    const microPath = uploaded.find(i => i.type === 'micro')!.path;
    const result = await serverClient.authenticate(base, [macroPath], [microPath]);
    return { source: 'server', result, lowConfidence: false };
  };

  if (mode === 'server') return serverFlow();

  const localReady = await modelStore.isReady();
  if (!localReady && mode === 'local') {
    throw new Error('本地模型未下载 (请先在设置页同步模型)');
  }

  if (!localReady) {
    // auto + 无本地模型 → 直接服务器
    return serverFlow();
  }

  try {
    const local = await authenticateLocal(photoUri, photoUri);
    const shaped = {
      ...local,
      piece_id: '',
      label_code: '本地',
    } as ServerAuthResult;
    const lowConfidence =
      (local.era_probabilities[local.era_code] ?? 0) < ERA_CONF_THRESHOLD ||
      local.authenticity_confidence < AUTH_CONF_THRESHOLD;
    return { source: 'local', result: shaped, lowConfidence };
  } catch (e) {
    if (mode === 'local') {
      throw new Error(`本地推理失败: ${(e as Error).message}`);
    }
    // auto: 本地失败回退服务器
    return serverFlow();
  }
}

/** 低置信复核: 上传 → 服务器 FP32 复算并落库 */
export async function recheckOnServer(
  base: string,
  photoUri: string,
): Promise<ServerAuthResult> {
  const uploaded = await serverClient.uploadImages(base, [
    { uri: photoUri, type: 'macro' },
    { uri: photoUri, type: 'micro' },
  ]);
  const macroPath = uploaded.find(i => i.type === 'macro')!.path;
  const microPath = uploaded.find(i => i.type === 'micro')!.path;
  return serverClient.authenticate(base, [macroPath], [microPath]);
}
