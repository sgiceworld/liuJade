/**
 * 古玉鉴真 — 材质枚举
 */

export const MATERIALS = [
  '和田白玉',
  '和田青玉',
  '和田碧玉',
  '和田青花',
  '翡翠（翠玉）',
  '岫玉',
  '玛瑙',
  '水晶',
  '独山玉',
  '绿松石',
  '琥珀',
  '其他',
] as const;

export type Material = (typeof MATERIALS)[number];

export const MATERIAL_ALIASES: Record<string, string[]> = {
  '和田白玉': ['羊脂白玉', '白玉'],
  '和田青玉': ['青玉'],
  '和田碧玉': ['碧玉'],
  '和田青花': ['青花玉'],
  '翡翠（翠玉）': ['翡翠', '翠玉'],
  '岫玉': ['岫岩玉', '蛇纹石玉'],
  '玛瑙': ['红玛瑙', '缠丝玛瑙'],
  '水晶': ['白水晶', '紫水晶', '黄水晶'],
  '独山玉': ['南阳玉'],
  '绿松石': ['松石'],
  '琥珀': ['琥珀', '蜜蜡'],
  '其他': [],
};

export const SOURCE_TYPES = ['馆藏', '拍卖', '著录'] as const;

export type SourceType = (typeof SOURCE_TYPES)[number];
