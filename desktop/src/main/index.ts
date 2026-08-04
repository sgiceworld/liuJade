/**
 * 古玉鉴真 — Electron 主进程入口
 *
 * 职责:
 * 1. 创建应用窗口
 * 2. 管理 Python 推理后端进程
 * 3. 处理模型自动更新
 * 4. 本地文件系统访问
 */

import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import * as path from 'path';
import { PythonBridge } from './python-bridge';

let mainWindow: BrowserWindow | null = null;
let pythonBridge: PythonBridge | null = null;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: '古玉鉴真',
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload', 'index.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    // 生产环境加载 React build
    // 开发环境连接 Vite dev server
  });

  // 开发模式
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(
      path.join(__dirname, '..', 'renderer', 'index.html')
    );
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

async function startBackend(): Promise<void> {
  pythonBridge = new PythonBridge();

  try {
    await pythonBridge.start();
    console.log('Python inference backend started');
  } catch (err) {
    console.error('Failed to start Python backend:', err);
    dialog.showErrorBox(
      '启动失败',
      '无法启动推理引擎。请确认已安装 Python 环境和依赖。'
    );
  }
}

function registerIpcHandlers(): void {
  // 文件选择对话框
  ipcMain.handle('dialog:openImages', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openFile', 'multiSelections'],
      filters: [
        { name: '图片文件', extensions: ['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'heic'] },
        { name: '所有文件', extensions: ['*'] },
      ],
    });
    return result.canceled ? [] : result.filePaths;
  });

  // 向后端发送 API 请求
  ipcMain.handle('api:authenticate', async (_event, payload) => {
    if (!pythonBridge) throw new Error('Backend not started');
    return pythonBridge.callApi('/authenticate', 'POST', payload);
  });

  ipcMain.handle('api:saveAnnotation', async (_event, payload) => {
    if (!pythonBridge) throw new Error('Backend not started');
    return pythonBridge.callApi('/annotations', 'POST', payload);
  });

  ipcMain.handle('api:listAnnotations', async () => {
    if (!pythonBridge) throw new Error('Backend not started');
    return pythonBridge.callApi('/annotations', 'GET');
  });

  ipcMain.handle('api:modelStatus', async () => {
    if (!pythonBridge) throw new Error('Backend not started');
    return pythonBridge.callApi('/models/status', 'GET');
  });

  // 获取应用数据路径
  ipcMain.handle('app:getDataPath', () => {
    return app.getPath('userData');
  });
}

app.whenReady().then(async () => {
  registerIpcHandlers();
  await startBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  // 关闭 Python 后端
  if (pythonBridge) {
    pythonBridge.stop();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
