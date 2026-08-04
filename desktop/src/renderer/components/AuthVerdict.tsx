/**
 * 古玉鉴真 — 真伪判定结果组件
 */

import React from 'react';

interface AuthVerdictProps {
  authenticity: '真老' | '新仿';
  confidence: number;
}

export function AuthVerdict({
  authenticity,
  confidence,
}: AuthVerdictProps): React.ReactElement {
  const isGenuine = authenticity === '真老';
  const confidencePct = (confidence * 100).toFixed(1);

  return (
    <div className={`auth-verdict ${isGenuine ? 'genuine' : 'fake'}`}>
      <div className="result-header">
        <h3>真伪判定</h3>
      </div>

      <div className="verdict-display">
        <div className={`verdict-icon ${isGenuine ? 'genuine' : 'fake'}`}>
          {isGenuine ? '✅' : '⚠️'}
        </div>
        <div className="verdict-text">
          <span className={`verdict-label ${isGenuine ? 'genuine' : 'fake'}`}>
            {authenticity}
          </span>
        </div>
        <div className="verdict-confidence">
          <div className="confidence-ring">
            <svg viewBox="0 0 36 36">
              <path
                className="ring-bg"
                d="M18 2.0845
                  a 15.9155 15.9155 0 0 1 0 31.831
                  a 15.9155 15.9155 0 0 1 0 -31.831"
                fill="none"
                stroke="#e0e0e0"
                strokeWidth="3"
              />
              <path
                className={`ring-fill ${isGenuine ? 'genuine' : 'fake'}`}
                d="M18 2.0845
                  a 15.9155 15.9155 0 0 1 0 31.831
                  a 15.9155 15.9155 0 0 1 0 -31.831"
                fill="none"
                strokeWidth="3"
                strokeDasharray={`${confidence * 100}, 100`}
              />
            </svg>
            <span className="confidence-value">{confidencePct}%</span>
          </div>
          <span className="confidence-label">置信度</span>
        </div>
      </div>

      {isGenuine ? (
        <p className="verdict-note">
          模型判断此玉器为<strong>真老</strong>，具有较高的历史年代特征。
        </p>
      ) : (
        <p className="verdict-note">
          模型判断此玉器为<strong>新仿</strong>，沁色/工痕与现代工艺特征吻合度较高。
        </p>
      )}
    </div>
  );
}
