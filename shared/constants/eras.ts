/**
 * 古玉鉴真 — 年代枚举与元数据
 * 鉴定与标注共用
 */

/** 年代代码 A-N */
export const ERA_CODE = [
  'A', 'B', 'C', 'D', 'E', 'F', 'G',
  'H', 'I', 'J', 'K', 'L', 'M', 'N',
] as const;

export type EraCode = (typeof ERA_CODE)[number];

/** 年代完整名称 */
export const ERA_NAMES: Record<EraCode, string> = {
  A: '文化期',
  B: '商代',
  C: '春秋',
  D: '战国',
  E: '秦汉',
  F: '三国两晋南北朝',
  G: '唐',
  H: '宋',
  I: '金元',
  J: '明',
  K: '清',
  L: '民国',
  M: '出口创汇',
  N: '现代',
};

/** 年代粗粒度分组（用于分层损失） */
export const ERA_GROUPS: Record<string, { label: string; eras: EraCode[] }> = {
  high_antiquity: { label: '远古', eras: ['A', 'B'] },
  classical: { label: '古典', eras: ['C', 'D', 'E'] },
  medieval: { label: '中古', eras: ['F', 'G', 'H'] },
  late_imperial: { label: '近古', eras: ['I', 'J', 'K'] },
  modern: { label: '近现代', eras: ['L', 'M', 'N'] },
};

/** 年代代码 → 分组索引 */
export const ERA_TO_GROUP_IDX: Record<EraCode, number> = {
  A: 0, B: 0,           // 远古
  C: 1, D: 1, E: 1,     // 古典
  F: 2, G: 2, H: 2,     // 中古
  I: 3, J: 3, K: 3,     // 近古
  L: 4, M: 4, N: 4,     // 近现代
};

export const NUM_ERA_CLASSES = 14;
export const NUM_ERA_GROUPS = 5;

/** 真伪代码 */
export const AUTH_CODE = {
  GENUINE: '0',
  FAKE: '1',
} as const;

export const AUTH_LABELS = {
  '0': '真老',
  '1': '新仿',
} as const;

export type AuthCode = keyof typeof AUTH_LABELS;
