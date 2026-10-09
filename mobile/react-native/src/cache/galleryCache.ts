/**
 * 古玉鉴真 — 图鉴离线缓存
 * AsyncStorage 存最近一次同步快照 (列表 JSON + 时间), 离线时展示并提示。
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import type { AnnotationRecord } from '../services/serverClient';

const KEY = 'gallery_snapshot';

export interface GallerySnapshot {
  updatedAt: string;
  items: AnnotationRecord[];
  total: number;
}

export async function saveSnapshot(snap: GallerySnapshot): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(snap));
}

export async function loadSnapshot(): Promise<GallerySnapshot | null> {
  const raw = await AsyncStorage.getItem(KEY);
  return raw ? JSON.parse(raw) : null;
}
