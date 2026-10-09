/**
 * 古玉鉴真 — 端侧预处理
 * 数值基准: inference/src/engine/preprocessing.py (PIL BILINEAR + EXIF 校正)
 * 流程: 原生 resize (stretch) → jpeg-js 解码 RGBA → 单遍循环 NCHW 归一化
 * 常数取自 shared/constants/modelConfig.ts
 *
 * 与服务器的有意偏差: 微距 tile 上限 64 个 (长边最多 1008px),
 * 服务器全分辨率无上限 — 手机上 700+ tiles 不可行。
 */

import RNFS from '@dr.pogodin/react-native-fs';
import ImageResizer from '@bam.tech/react-native-image-resizer';
import { decode as decodeJpeg, BufferRet } from 'jpeg-js';
import {
  IMAGENET_MEAN,
  IMAGENET_STD,
  MACRO_INPUT_SIZE,
  MICRO_TILE_SIZE,
  MICRO_TILE_STRIDE,
} from '../../../../shared/constants/modelConfig';

const [MEAN_R, MEAN_G, MEAN_B] = IMAGENET_MEAN;
const [STD_R, STD_G, STD_B] = IMAGENET_STD;

/** 微距判定阈值 (≥8MP, 对齐 preprocessing.py detect_is_micro) */
export const MICRO_PIXEL_THRESHOLD = 8_000_000;
/** 微距最长边上限: 224 + 7*112 = 1008 → 最多 8×8=64 tiles */
export const MICRO_MAX_LONG_EDGE = 1008;

/** 原生 resize 到 JPEG 文件 (EXIF 方向由 resizer 解码时应用) */
async function resizeToFile(
  uri: string,
  width: number,
  height: number,
  mode: 'stretch' | 'contain' = 'stretch',
): Promise<string> {
  const res = await ImageResizer.createResizedImage(
    uri,
    width,
    height,
    'JPEG',
    92,
    undefined,
    undefined,
    false,
    { mode, onlyScaleDown: false },
  );
  return res.path;
}

async function readBytes(path: string): Promise<Uint8Array> {
  const b64 = await RNFS.readFile(path, 'base64');
  const binary = (globalThis as any).atob?.(b64) ?? atobFallback(b64);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
  return out;
}

function atobFallback(b64: string): string {
  const chars =
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  let binary = '';
  for (let i = 0; i < b64.length; i += 4) {
    const c0 = chars.indexOf(b64[i] ?? '=');
    const c1 = chars.indexOf(b64[i + 1] ?? '=');
    const c2 = chars.indexOf(b64[i + 2] ?? '=');
    const c3 = chars.indexOf(b64[i + 3] ?? '=');
    const n = (c0 << 18) | (c1 << 12) | ((c2 & 63) << 6) | (c3 & 63);
    binary += String.fromCharCode((n >> 16) & 255);
    if (b64[i + 2] !== '=') binary += String.fromCharCode((n >> 8) & 255);
    if (b64[i + 3] !== '=') binary += String.fromCharCode(n & 255);
  }
  return binary;
}

/** RGBA → 归一化 NCHW Float32Array (单遍循环, O(w*h)) */
function rgbaToNchw(data: Uint8Array, width: number, height: number): Float32Array {
  const n = width * height;
  const out = new Float32Array(3 * n);
  for (let p = 0; p < n; p++) {
    const i = 4 * p;
    out[p] = (data[i] / 255 - MEAN_R) / STD_R;
    out[n + p] = (data[i + 1] / 255 - MEAN_G) / STD_G;
    out[2 * n + p] = (data[i + 2] / 255 - MEAN_B) / STD_B;
  }
  return out;
}

/** 宏观预处理: stretch 512×512 → (3,512,512) NCHW */
export async function preprocessMacro(uri: string): Promise<Float32Array> {
  const path = await resizeToFile(uri, MACRO_INPUT_SIZE, MACRO_INPUT_SIZE, 'stretch');
  const bytes = await readBytes(path);
  const img: BufferRet = decodeJpeg(bytes, { useTArray: true, formatAsRGBA: true });
  if (img.width !== MACRO_INPUT_SIZE || img.height !== MACRO_INPUT_SIZE) {
    throw new Error(`宏观 resize 结果异常: ${img.width}x${img.height}`);
  }
  return rgbaToNchw(img.data, img.width, img.height);
}

/** 微距预处理: 长边限 1008 → stride 112 滑窗 tile → (N,3,224,224) */
export async function preprocessMicro(uri: string): Promise<Float32Array[]> {
  const info = await getImageSize(uri);
  const { width, height } = info;
  const longEdge = Math.max(width, height);

  let resizedPath: string;
  let rw: number;
  let rh: number;
  if (longEdge > MICRO_MAX_LONG_EDGE) {
    const ratio = MICRO_MAX_LONG_EDGE / longEdge;
    rw = Math.round(width * ratio);
    rh = Math.round(height * ratio);
    resizedPath = await resizeToFile(uri, rw, rh, 'contain');
  } else {
    resizedPath = uri;
    rw = width;
    rh = height;
  }

  const bytes = await readBytes(resizedPath);
  const img: BufferRet = decodeJpeg(bytes, { useTArray: true, formatAsRGBA: true });
  const data = img.data;

  const tiles: Float32Array[] = [];
  const T = MICRO_TILE_SIZE;
  const S = MICRO_TILE_STRIDE;

  if (img.width < T || img.height < T) {
    // 小于 224 的图整张 resize 成 1 个 tile (与服务器兜底一致)
    const small = await resizeToFile(resizedPath, T, T, 'stretch');
    const sb = decodeJpeg(await readBytes(small), {
      useTArray: true,
      formatAsRGBA: true,
    });
    tiles.push(rgbaToNchw(sb.data, T, T));
    return tiles;
  }

  for (let y = 0; y + T <= img.height; y += S) {
    for (let x = 0; x + T <= img.width; x += S) {
      // 从 RGBA 大图中跨行拷贝 tile 像素 (先转 NCHW 再拷)
      const tile = new Float32Array(3 * T * T);
      const tn = T * T;
      for (let ty = 0; ty < T; ty++) {
        const rowBase = (y + ty) * img.width + x;
        for (let tx = 0; tx < T; tx++) {
          const src = 4 * (rowBase + tx);
          const dst = ty * T + tx;
          tile[dst] = (data[src] / 255 - MEAN_R) / STD_R;
          tile[tn + dst] = (data[src + 1] / 255 - MEAN_G) / STD_G;
          tile[2 * tn + dst] = (data[src + 2] / 255 - MEAN_B) / STD_B;
        }
      }
      tiles.push(tile);
    }
  }
  if (tiles.length === 0) {
    const small = await resizeToFile(resizedPath, T, T, 'stretch');
    const sb = decodeJpeg(await readBytes(small), {
      useTArray: true,
      formatAsRGBA: true,
    });
    tiles.push(rgbaToNchw(sb.data, T, T));
  }
  return tiles;
}

/** 读取原图尺寸 (判定微距/宏观) — 只解析 JPEG SOF 头, 不全量解码 */
export async function getImageSize(
  uri: string,
): Promise<{ width: number; height: number }> {
  const b64 = await RNFS.readFile(uri, 'base64');
  const binary = (globalThis as any).atob?.(b64) ?? atobFallback(b64);
  const bytes = new Uint8Array(Math.min(binary.length, 64 * 1024));
  for (let i = 0; i < bytes.length; i++) bytes[i] = binary.charCodeAt(i);
  if (bytes[0] !== 0xff || bytes[1] !== 0xd8) {
    throw new Error('不是 JPEG 文件');
  }
  let offset = 2;
  while (offset + 9 < bytes.length) {
    if (bytes[offset] !== 0xff) {
      offset += 1;
      continue;
    }
    const marker = bytes[offset + 1];
    const len = (bytes[offset + 2] << 8) | bytes[offset + 3];
    if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc) {
      // SOF0-SOF15 (排除 DHT/JPG/AC): 高度在 [5,6], 宽度在 [7,8]
      const height = (bytes[offset + 5] << 8) | bytes[offset + 6];
      const width = (bytes[offset + 7] << 8) | bytes[offset + 8];
      if (width > 0 && height > 0) return { width, height };
    }
    if (marker === 0xd9) break; // EOI
    offset += 2 + len;
  }
  // SOF 未命中 (渐进式首段前有长头部) → 回退全量解码
  const img = decodeJpeg(bytes, { useTArray: true, formatAsRGBA: false });
  return { width: img.width, height: img.height };
}

/** 判定是否为微距 (≥8MP, 对齐服务器 detect_is_micro) */
export function isMicroByPixels(width: number, height: number): boolean {
  return width * height >= MICRO_PIXEL_THRESHOLD;
}
