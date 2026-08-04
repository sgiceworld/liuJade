/**
 * 古玉鉴真 — 共享类型定义
 */

import type { EraCode, AuthCode } from '../constants/eras';
import type { Material, SourceType } from '../constants/materials';

/** 标签编码结构 */
export interface LabelCode {
  authCode: AuthCode;          // '0' | '1'
  loginNumber: string;         // JY + YYYYMMDD + 6位流水
  dateTime: string;            // YYYYMMDDHHmmss
  eraCode: EraCode;            // A-N
  sequence: number;            // 同日同年代流水号 (1-999)
}

/** 尺寸信息 */
export interface Dimensions {
  length?: number;   // 长 (mm)
  width?: number;    // 宽 (mm)
  height?: number;   // 高 (mm)
  thickness?: number; // 厚 (mm)
  diameter?: number; // 直径 (mm)
}

/** 玉器记录（标注/鉴定统一） */
export interface JadePiece {
  id: string;                    // UUID
  labelCode: string;             // 标签编码字符串
  loginNumber: string;           // 总登录号
  productName: string;           // 品名（标准定名）
  material: Material;            // 材质
  dimensions?: Dimensions;       // 尺寸
  sourceType: SourceType;        // 来源类型
  sourceDetail?: string;         // 来源详情
  authenticity: '真老' | '新仿';
  era: string;                   // 年代名称
  eraCode: EraCode;              // 年代代码
  annotatedBy?: string;          // 标注人
  annotationConfidence?: number; // 标注置信度 1-5
  createdAt: string;             // ISO 8601
  updatedAt: string;
}

/** 图片信息 */
export interface JadeImage {
  id: string;
  pieceId: string;
  filePath: string;
  imageType: 'macro' | 'micro';
  cameraAngle?: 'front' | 'back' | 'left' | 'right' | 'top' | 'bottom';
  width: number;
  height: number;
  fileSizeBytes: number;
  createdAt: string;
}

/** AI 鉴定请求 */
export interface AuthRequest {
  pieceId?: string;              // 可选（新鉴定时为 null）
  macroImages: string[];         // 宏观图片 base64 或文件路径
  microImages: string[];         // 微距图片
}

/** AI 鉴定结果 */
export interface AuthResult {
  id: string;
  pieceId: string;
  labelCode: string;
  modelVersion: string;
  predictedEra: string;
  eraCode: EraCode;
  eraProbabilities: Record<EraCode, number>;
  predictedAuthenticity: '真老' | '新仿';
  authenticityConfidence: number;
  macroFeaturesAnalyzed: number;
  microFeaturesAnalyzed: number;
  inferenceTimeMs: number;
  createdAt: string;
}

/** 标注保存请求 */
export interface AnnotationSaveRequest {
  pieceId: string;
  authenticity: '真老' | '新仿';
  eraCode: EraCode;
  productName: string;
  material: Material;
  dimensions?: Dimensions;
  sourceType: SourceType;
  sourceDetail?: string;
  annotatedBy?: string;
  annotationConfidence?: number;
  imagePaths: string[];
}
