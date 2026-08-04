/**
 * 古玉鉴真 — 推理 Hook
 */

import { useState, useCallback } from 'react';

const API = 'http://localhost:8720';

async function postApi(endpoint: string, body: any): Promise<any> {
  const r = await fetch(`${API}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

interface UseInferenceReturn {
  authenticate: (macroImages: string[], microImages: string[]) => Promise<any>;
  saveAnnotation: (data: any) => Promise<any>;
  isLoading: boolean;
  error: string | null;
}

export function useInference(): UseInferenceReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const authenticate = useCallback(async (macroImages: string[], microImages: string[]) => {
    setIsLoading(true); setError(null);
    try {
      const result = await postApi('/authenticate', { macro_images: macroImages, micro_images: microImages });
      if (!result.success) throw new Error(result.error || '鉴定失败');
      return result.data;
    } catch (err: any) {
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const saveAnnotation = useCallback(async (data: any) => {
    setIsLoading(true); setError(null);
    try {
      const result = await postApi('/annotations', data);
      if (!result.success) throw new Error(result.error || '保存失败');
      return result.data;
    } catch (err: any) {
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { authenticate, saveAnnotation, isLoading, error };
}
