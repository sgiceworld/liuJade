/**
 * 古玉鉴真 — Electron Preload 脚本
 *
 * 通过 contextBridge 安全暴露 IPC 接口给渲染进程。
 */

import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  // 文件对话框
  openImages: () => ipcRenderer.invoke('dialog:openImages'),

  // API 调用
  authenticate: (payload: any) =>
    ipcRenderer.invoke('api:authenticate', payload),
  saveAnnotation: (payload: any) =>
    ipcRenderer.invoke('api:saveAnnotation', payload),
  listAnnotations: () =>
    ipcRenderer.invoke('api:listAnnotations'),
  modelStatus: () =>
    ipcRenderer.invoke('api:modelStatus'),

  // 应用
  getDataPath: () => ipcRenderer.invoke('app:getDataPath'),
});
