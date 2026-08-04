/**
 * 古玉鉴真 — API 类型定义
 */

import type { AuthRequest, AuthResult, AnnotationSaveRequest, JadePiece, JadeImage } from './jade';

/** API 响应包装 */
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

/** POST /authenticate */
export type AuthenticateRequest = AuthRequest;
export type AuthenticateResponse = ApiResponse<AuthResult>;

/** GET /piece/:id */
export type GetPieceResponse = ApiResponse<JadePiece>;

/** GET /piece/:id/images */
export type GetPieceImagesResponse = ApiResponse<JadeImage[]>;

/** POST /annotations */
export type CreateAnnotationRequest = AnnotationSaveRequest;
export type CreateAnnotationResponse = ApiResponse<JadePiece>;

/** GET /annotations — 列出所有标注 */
export type ListAnnotationsResponse = ApiResponse<JadePiece[]>;

/** GET /models/status */
export interface ModelStatus {
  version: string;
  onnxPath: string;
  downloadedAt: string;
  modelSizeBytes: number;
  checksum: string;
  latestVersion: string;
  updateAvailable: boolean;
}
export type GetModelStatusResponse = ApiResponse<ModelStatus>;
