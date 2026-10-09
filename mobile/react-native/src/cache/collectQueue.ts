/**
 * 古玉鉴真 — 样品采集离线队列
 * 无网时采集记录 (含本地图片 URI) 入队, 恢复网络后 flush: 上传 → 提交 → 出队。
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { serverClient } from '../services/serverClient';
import type { AnnotationSavePayload } from '../services/serverClient';

const KEY = 'collect_queue';

export interface QueuedCollection {
  id: string;
  payload: AnnotationSavePayload;
  photoUris: string[];
  createdAt: string;
}

export async function enqueue(
  payload: AnnotationSavePayload,
  photoUris: string[],
): Promise<void> {
  const queue = await loadQueue();
  queue.push({
    id: `${Date.now()}_${Math.random().toString(36).slice(2)}`,
    payload,
    photoUris,
    createdAt: new Date().toISOString(),
  });
  await AsyncStorage.setItem(KEY, JSON.stringify(queue));
}

export async function loadQueue(): Promise<QueuedCollection[]> {
  const raw = await AsyncStorage.getItem(KEY);
  return raw ? JSON.parse(raw) : [];
}

export async function removeFromQueue(id: string): Promise<void> {
  const queue = await loadQueue();
  await AsyncStorage.setItem(
    KEY,
    JSON.stringify(queue.filter(q => q.id !== id)),
  );
}

export async function queueLength(): Promise<number> {
  return (await loadQueue()).length;
}

/** 逐条 flush: 上传图片 → POST /annotations → 出队。失败保留并返回错误。 */
export async function flushQueue(base: string): Promise<{ ok: number; failed: number }> {
  const queue = await loadQueue();
  let ok = 0;
  let failed = 0;
  for (const item of queue) {
    try {
      const uploaded = await serverClient.uploadImages(
        base,
        item.photoUris.map(uri => ({ uri, type: 'macro' as const })),
      );
      await serverClient.saveAnnotation(base, {
        ...item.payload,
        image_paths: uploaded.map(u => u.path),
      });
      await removeFromQueue(item.id);
      ok += 1;
    } catch {
      failed += 1;
    }
  }
  return { ok, failed };
}
