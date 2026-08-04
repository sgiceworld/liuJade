/**
 * 古玉鉴真 — 年代预测结果组件
 *
 * 展示: 预测年代 + Top-3 概率条形图
 */

import React from 'react';

interface EraResultProps {
  predictedEra: string;
  eraCode: string;
  probabilities: Record<string, number>;
  top3: Array<{
    era_code: string;
    era_name: string;
    probability: number;
  }>;
}

export function EraResult({
  predictedEra,
  eraCode,
  probabilities,
  top3,
}: EraResultProps): React.ReactElement {
  return (
    <div className="era-result">
      <div className="result-header">
        <h3>年代判定</h3>
        <span className="result-badge era-badge">
          {predictedEra} ({eraCode})
        </span>
      </div>

      {/* 概率条形图 */}
      <div className="probability-chart">
        {top3.map((item) => (
          <div key={item.era_code} className="prob-bar-item">
            <div className="prob-label">
              <span className="era-name">{item.era_name}</span>
              <span className="era-prob">
                {(item.probability * 100).toFixed(1)}%
              </span>
            </div>
            <div className="prob-bar-track">
              <div
                className={`prob-bar-fill ${item.era_code === eraCode ? 'primary' : ''}`}
                style={{ width: `${item.probability * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* 年代代码参考 */}
      <details className="era-code-reference">
        <summary>年代代码对照表</summary>
        <div className="code-grid">
          {[
            ['A', '文化期'], ['B', '商代'], ['C', '春秋'],
            ['D', '战国'], ['E', '秦汉'], ['F', '三国两晋南北朝'],
            ['G', '唐'], ['H', '宋'], ['I', '金元'],
            ['J', '明'], ['K', '清'], ['L', '民国'],
            ['M', '出口创汇'], ['N', '现代'],
          ].map(([code, name]) => (
            <span
              key={code}
              className={`code-chip ${code === eraCode ? 'highlight' : ''}`}
            >
              {code}: {name}
            </span>
          ))}
        </div>
      </details>
    </div>
  );
}
