/**
 * 古玉鉴真 — Python 推理后端桥接
 *
 * 管理 Python FastAPI 推理服务的生命周期:
 * - 启动时 spawn Python 子进程
 * - 通过 localhost HTTP 通信
 * - 关闭时优雅终止进程
 */

import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as http from 'http';

const PYTHON_PORT = 8720;
const PYTHON_HOST = '127.0.0.1';
const MAX_STARTUP_WAIT_MS = 30000;

export class PythonBridge {
  private process: ChildProcess | null = null;
  private baseUrl: string;

  constructor() {
    this.baseUrl = `http://${PYTHON_HOST}:${PYTHON_PORT}`;
  }

  async start(): Promise<void> {
    return new Promise((resolve, reject) => {
      const isPackaged = process.env.NODE_ENV !== 'development';

      // 获取 Python 可执行文件路径
      let pythonExe: string;
      let serverScript: string;

      if (isPackaged) {
        // PyInstaller 打包后的 exe
        pythonExe = path.join(
          process.resourcesPath, 'inference', 'jade-inference.exe'
        );
        serverScript = '';
      } else {
        // 开发模式: 直接运行 Python
        pythonExe = 'python';
        serverScript = path.join(
          __dirname, '..', '..', '..', 'inference', 'src', 'api', 'server.py'
        );
      }

      const args = isPackaged ? [] : ['-m', 'uvicorn', 'inference.src.api.server:app'];
      if (serverScript) {
        args.push(serverScript);
      }
      args.push('--host', PYTHON_HOST, '--port', String(PYTHON_PORT));

      this.process = spawn(pythonExe, args, {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: { ...process.env },
      });

      this.process.stdout?.on('data', (data) => {
        console.log(`[Python] ${data}`);
      });

      this.process.stderr?.on('data', (data) => {
        console.error(`[Python Error] ${data}`);
      });

      this.process.on('error', (err) => {
        reject(new Error(`Failed to start Python: ${err.message}`));
      });

      this.process.on('exit', (code) => {
        console.log(`Python process exited with code ${code}`);
        this.process = null;
      });

      // 等待服务就绪
      this._waitForReady(MAX_STARTUP_WAIT_MS)
        .then(resolve)
        .catch(reject);
    });
  }

  private async _waitForReady(timeoutMs: number): Promise<void> {
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      try {
        const response = await this._httpGet('/health');
        if (response.status === 'ok') {
          console.log('Python backend is ready');
          return;
        }
      } catch {
        // 服务尚未就绪，等待重试
      }
      await this._sleep(500);
    }

    throw new Error('Python backend failed to start within timeout');
  }

  async callApi(
    endpoint: string,
    method: string = 'GET',
    body?: any
  ): Promise<any> {
    return new Promise((resolve, reject) => {
      const url = new URL(endpoint, this.baseUrl);
      const options: http.RequestOptions = {
        hostname: PYTHON_HOST,
        port: PYTHON_PORT,
        path: url.pathname + url.search,
        method: method,
        headers: {
          'Content-Type': 'application/json',
        },
      };

      const req = http.request(options, (res) => {
        let data = '';
        res.on('data', (chunk) => (data += chunk));
        res.on('end', () => {
          try {
            resolve(JSON.parse(data));
          } catch {
            resolve(data);
          }
        });
      });

      req.on('error', reject);

      if (body) {
        req.write(JSON.stringify(body));
      }

      req.end();
    });
  }

  async stop(): Promise<void> {
    if (this.process) {
      this.process.kill('SIGTERM');
      // 给进程一些时间优雅退出
      await this._sleep(2000);
      if (this.process) {
        this.process.kill('SIGKILL');
      }
    }
  }

  private _httpGet(path: string): Promise<any> {
    return new Promise((resolve, reject) => {
      http.get(`${this.baseUrl}${path}`, (res) => {
        let data = '';
        res.on('data', (chunk) => (data += chunk));
        res.on('end', () => {
          try {
            resolve(JSON.parse(data));
          } catch {
            resolve(data);
          }
        });
      }).on('error', reject);
    });
  }

  private _sleep(ms: number): Promise<void> {
    return new Promise((r) => setTimeout(r, ms));
  }
}
