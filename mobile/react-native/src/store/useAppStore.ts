/**
 * 古玉鉴真 — 应用状态 (zustand)
 */

import { create } from 'zustand';
import { DEFAULT_SERVER_BASE } from '../config';

export type IdentifyMode = 'auto' | 'local' | 'server';

interface AppState {
  serverBase: string;
  setServerBase: (base: string) => void;
  identifyMode: IdentifyMode;
  setIdentifyMode: (m: IdentifyMode) => void;
  serverHealthy: boolean;
  setServerHealthy: (ok: boolean) => void;
}

export const useAppStore = create<AppState>(set => ({
  serverBase: DEFAULT_SERVER_BASE,
  setServerBase: base => set({ serverBase: base.replace(/\/+$/, '') }),
  identifyMode: 'auto',
  setIdentifyMode: m => set({ identifyMode: m }),
  serverHealthy: false,
  setServerHealthy: ok => set({ serverHealthy: ok }),
}));
