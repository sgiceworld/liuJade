/**
 * 古玉鉴真 — API 服务层
 *
 * 自动选择通信方式:
 * - Electron IPC (window.electronAPI) — 打包桌面应用
 * - HTTP fetch (localhost:8720) — 浏览器开发模式
 */

const API_BASE = 'http://localhost:8720';

function isElectron(): boolean {
  return typeof window !== 'undefined' && !!(window as any).electronAPI;
}

async function fetchApi(endpoint: string, method: string = 'GET', body?: any): Promise<any> {
  const url = `${API_BASE}${endpoint}`;
  const options: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) {
    options.body = JSON.stringify(body);
  }
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return response.json();
}

async function ipcApi(channel: string, payload?: any): Promise<any> {
  const api = (window as any).electronAPI;
  switch (channel) {
    case 'authenticate': return api.authenticate(payload);
    case 'saveAnnotation': return api.saveAnnotation(payload);
    case 'listAnnotations': return api.listAnnotations();
    case 'modelStatus': return api.modelStatus();
    default: throw new Error(`Unknown IPC channel: ${channel}`);
  }
}

// ── Public API ──

export async function apiListAnnotations(limit: number = 100, offset: number = 0): Promise<any> {
  if (isElectron()) {
    return ipcApi('listAnnotations');
  }
  return fetchApi(`/annotations?limit=${limit}&offset=${offset}`);
}

export async function apiSaveAnnotation(data: any): Promise<any> {
  if (isElectron()) {
    return ipcApi('saveAnnotation', data);
  }
  return fetchApi('/annotations', 'POST', data);
}

export async function apiAuthenticate(macroImages: string[], microImages: string[]): Promise<any> {
  if (isElectron()) {
    return ipcApi('authenticate', { macro_images: macroImages, micro_images: microImages });
  }
  return fetchApi('/authenticate', 'POST', { macro_images: macroImages, micro_images: microImages });
}

export async function apiModelStatus(): Promise<any> {
  if (isElectron()) {
    return ipcApi('modelStatus');
  }
  return fetchApi('/models/status');
}
