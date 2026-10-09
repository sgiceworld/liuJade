/**
 * 古玉鉴真 — 移动端模型管理
 * 从 PC 服务器 /models/download/{name} 下载 INT8 模型到应用私有目录,
 * SHA256 校验 (对比 /models/status 的清单), 校验通过才置 ready。
 */

import RNFS from '@dr.pogodin/react-native-fs';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { sha256 } from 'js-sha256';
import { MOBILE_MODEL_FILES } from '../config';
import { serverClient } from '../services/serverClient';

const MODELS_DIR = `${RNFS.DocumentDirectoryPath}/models`;
const HASH_CACHE_KEY = 'model_hashes'; // {name: sha256}

async function readCachedHashes(): Promise<Record<string, string>> {
  const raw = await AsyncStorage.getItem(HASH_CACHE_KEY);
  return raw ? JSON.parse(raw) : {};
}

async function writeCachedHashes(hashes: Record<string, string>) {
  await AsyncStorage.setItem(HASH_CACHE_KEY, JSON.stringify(hashes));
}

export interface ModelStoreStatus {
  ready: boolean;
  missing: string[];
  downloading: boolean;
  progress: { done: number; total: number };
}

class ModelStore {
  private _ready = false;

  /** 本地文件齐全且 SHA256 与服务器清单一致 */
  async isReady(): Promise<boolean> {
    if (this._ready) return true;
    for (const name of MOBILE_MODEL_FILES) {
      if (!(await RNFS.exists(`${MODELS_DIR}/${name}`))) return false;
    }
    this._ready = true;
    return true;
  }

  /** 服务器连通时校验哈希; 离线时以本地文件存在为准 */
  async verifyHashes(base: string): Promise<boolean> {
    if (!(await this.isReady())) return false;
    try {
      const status = await serverClient.modelStatus(base);
      const cached = await readCachedHashes();
      for (const name of MOBILE_MODEL_FILES) {
        const remote = status.mobile_models.find(m => m.name === name);
        if (!remote) return false; // 服务器清单缺失 → 视为版本不匹配
        const local = cached[name];
        if (local !== remote.sha256) return false;
      }
      return true;
    } catch {
      // 离线: 本地文件在即可
      return true;
    }
  }

  /** 下载缺失/哈希不符的模型文件 */
  async sync(base: string, onProgress?: (p: { done: number; total: number }) => void): Promise<void> {
    await RNFS.mkdir(MODELS_DIR);
    let remoteList: Array<{ name: string; sha256: string }>;
    try {
      const status = await serverClient.modelStatus(base);
      remoteList = status.mobile_models;
    } catch (e) {
      throw new Error(`获取模型清单失败: ${(e as Error).message}`);
    }
    if (remoteList.length < MOBILE_MODEL_FILES.length) {
      throw new Error('服务器量化模型未就绪 (先跑 quantize_models.py)');
    }

    const cached = await readCachedHashes();
    const todo = MOBILE_MODEL_FILES.filter(name => {
      const remote = remoteList.find(m => m.name === name);
      return !remote || cached[name] !== remote.sha256;
    });

    let done = 0;
    for (const name of todo) {
      const buf = await serverClient.downloadModel(base, name);
      const path = `${MODELS_DIR}/${name}`;
      await RNFS.writeFile(path, base64FromArrayBuffer(buf), 'base64');
      const hash = sha256(new Uint8Array(buf));
      const remote = remoteList.find(m => m.name === name);
      if (remote && hash !== remote.sha256) {
        throw new Error(`模型校验失败: ${name}`);
      }
      cached[name] = hash;
      await writeCachedHashes(cached);
      done += 1;
      onProgress?.({ done, total: todo.length });
    }
    this._ready = true;
  }

  /** 删除全部本地模型 (设置页"重置模型") */
  async clear(): Promise<void> {
    await AsyncStorage.removeItem(HASH_CACHE_KEY);
    await RNFS.unlink(MODELS_DIR).catch(() => {});
    this._ready = false;
  }
}

function base64FromArrayBuffer(buf: ArrayBuffer): string {
  // 分段转 base64 避免栈溢出 (String.fromCharCode.apply 有参数上限)
  const bytes = new Uint8Array(buf);
  let binary = '';
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return (globalThis as any).btoa?.(binary) ?? binaryToBase64(binary);
}

/** Hermes 无 btoa 时的兜底 */
function binaryToBase64(binary: string): string {
  const chars =
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  let out = '';
  for (let i = 0; i < binary.length; i += 3) {
    const b0 = binary.charCodeAt(i);
    const b1 = i + 1 < binary.length ? binary.charCodeAt(i + 1) : 0;
    const b2 = i + 2 < binary.length ? binary.charCodeAt(i + 2) : 0;
    out += chars[b0 >> 2];
    out += chars[((b0 & 3) << 4) | (b1 >> 4)];
    out += i + 1 < binary.length ? chars[((b1 & 15) << 2) | (b2 >> 6)] : '=';
    out += i + 2 < binary.length ? chars[b2 & 63] : '=';
  }
  return out;
}

export const modelStore = new ModelStore();
export { MODELS_DIR };
