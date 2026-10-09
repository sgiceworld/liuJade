/**
 * 古玉鉴真 — 服务器 API 客户端
 * 接口契约参照 desktop/src/renderer/services/api.ts (ApiResponse 包装)
 */

import type { ApiResponse } from '../../../../shared/types/api';

export interface ServerAuthResult {
  piece_id: string;
  label_code: string;
  predicted_era: string;
  era_code: string;
  era_probabilities: Record<string, number>; // era code → prob
  predicted_authenticity: '真老' | '新仿';
  authenticity_confidence: number;
  macro_features_analyzed: number;
  micro_features_analyzed: number;
  inference_time_ms: number;
  top3_eras: Array<{ code: string; name: string; prob: number }>;
}

export interface AnnotationRecord {
  id: string;
  label_code: string;
  product_name: string;
  material: string;
  era: string;
  era_code: string;
  authenticity: string;
  source_type: string;
  source_detail: string;
  annotated_by: string;
  annotation_confidence: number;
  notes: string | null;
  image_paths: string[];
  training_image: string;
  review_count: number;
  review_status: string;
  created_at: string | null;
}

export interface MobileModelInfo {
  name: string;
  size_bytes: number;
  sha256: string;
}

/** POST /annotations 载荷 (服务器 camelCase/snake_case 双兼容) */
export interface AnnotationSavePayload {
  authenticity: '真老' | '新仿';
  era_code?: string;
  product_name?: string;
  material?: string;
  dimensions?: Record<string, number>;
  source_type?: string;
  source_detail?: string;
  annotated_by?: string;
  annotation_confidence?: number;
  image_paths?: string[];
}

async function request<T>(
  base: string,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${base}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
    });
  } catch (e) {
    throw new Error(`无法连接服务器 ${base}: ${(e as Error).message}`);
  }
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok || body.success === false) {
    throw new Error(
      (body as { detail?: string; error?: string }).detail ||
        (body as { error?: string }).error ||
        `HTTP ${resp.status}`,
    );
  }
  return body as T;
}

/** 图鉴缩略图 URL (路径统一正斜杠 + ?w=) */
export function imageUrl(base: string, path: string, w?: number): string {
  const clean = path.replace(/\\/g, '/');
  return `${base}/images/${clean}${w ? `?w=${w}` : ''}`;
}

export const serverClient = {
  async health(base: string): Promise<{ status: string; model_loaded: boolean }> {
    return request(base, '/health');
  },

  /** 上传图片 → 服务器本地绝对路径 */
  async uploadImages(
    base: string,
    photos: Array<{ uri: string; type: 'macro' | 'micro' }>,
  ): Promise<Array<{ type: string; path: string }>> {
    const form = new FormData();
    photos.forEach(p => {
      const name = `${p.type}_${Date.now()}_${Math.random()
        .toString(36)
        .slice(2)}.jpg`;
      form.append('files', { uri: p.uri, name, type: 'image/jpeg' } as any);
    });
    form.append('types', photos.map(p => p.type).join(','));
    let resp: Response;
    try {
      resp = await fetch(`${base}/images/upload`, {
        method: 'POST',
        body: form,
        // 不设 Content-Type, fetch 自动带 multipart boundary
      });
    } catch (e) {
      throw new Error(`上传失败: ${(e as Error).message}`);
    }
    const body = await resp.json().catch(() => ({}));
    if (!resp.ok || body.success === false) {
      throw new Error(
        (body as { detail?: string }).detail || `上传失败 HTTP ${resp.status}`,
      );
    }
    return body.data.images;
  },

  /** 服务器端鉴定 (上传路径 → /authenticate) */
  async authenticate(
    base: string,
    macroPaths: string[],
    microPaths: string[],
  ): Promise<ServerAuthResult> {
    const body = await request<ApiResponse<ServerAuthResult>>(
      base,
      '/authenticate',
      {
        method: 'POST',
        body: JSON.stringify({ macro_images: macroPaths, micro_images: microPaths }),
      },
    );
    return body.data!;
  },

  async listAnnotations(
    base: string,
    params: {
      limit?: number;
      offset?: number;
      era_code?: string;
      authenticity?: string;
      source_type?: string;
      q?: string;
    } = {},
  ): Promise<{ data: AnnotationRecord[]; total: number }> {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== '') qs.append(k, String(v));
    });
    return request(base, `/annotations?${qs.toString()}`);
  },

  /** 保存标注 (样品采集复用, 服务器自动生成 label_code) */
  async saveAnnotation(
    base: string,
    payload: AnnotationSavePayload,
  ): Promise<{ piece_id: string; label_code: string }> {
    const body = await request<ApiResponse<{ piece_id: string; label_code: string }>>(
      base,
      '/annotations',
      { method: 'POST', body: JSON.stringify(payload) },
    );
    return body.data!;
  },

  async modelStatus(
    base: string,
  ): Promise<{
    loaded: boolean;
    version: string;
    providers: string[];
    mobile_models: MobileModelInfo[];
  }> {
    const body = await request<ApiResponse<any>>(base, '/models/status');
    return body.data;
  },

  /** 下载移动端模型二进制 */
  async downloadModel(base: string, filename: string): Promise<ArrayBuffer> {
    const resp = await fetch(`${base}/models/download/${filename}`);
    if (!resp.ok) throw new Error(`模型下载失败: HTTP ${resp.status}`);
    return resp.arrayBuffer();
  },
};
