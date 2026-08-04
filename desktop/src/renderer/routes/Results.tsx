/**
 * 古玉鉴真 — 鉴定结果页面
 *
 * 展示:
 * - 年代预测 (Top-3 概率)
 * - 真伪判定 + 置信度
 * - AI 鉴定后提示是否保存入标注库
 */

import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { EraResult } from '../components/EraResult';
import { AuthVerdict } from '../components/AuthVerdict';
import { useInference } from '../hooks/useInference';

// Mock 结果展示 (实际从 API 获取)
const MOCK_RESULT = {
  predicted_era: '唐',
  era_code: 'G',
  era_probabilities: {
    A: 0.01, B: 0.02, C: 0.03, D: 0.05,
    E: 0.08, F: 0.10, G: 0.45, H: 0.15,
    I: 0.05, J: 0.03, K: 0.02, L: 0.01,
    M: 0.00, N: 0.00,
  },
  predicted_authenticity: '真老',
  authenticity_confidence: 0.87,
  inference_time_ms: 1523,
  top3_eras: [
    { era_code: 'G', era_name: '唐', probability: 0.45 },
    { era_code: 'H', era_name: '宋', probability: 0.15 },
    { era_code: 'F', era_name: '三国两晋南北朝', probability: 0.10 },
  ],
};

export function Results(): React.ReactElement {
  const { pieceId } = useParams<{ pieceId: string }>();
  const [showSavePrompt, setShowSavePrompt] = useState(true);

  // TODO: 从 API 获取实际结果
  const result = MOCK_RESULT;

  const handleSaveAnnotation = (authenticity: '真老' | '新仿') => {
    // 跳转到标注页面，携带鉴定结果
    console.log('Save annotation:', authenticity, pieceId);
    setShowSavePrompt(false);
  };

  return (
    <div className="page results-page">
      <h2>鉴定结果</h2>

      {/* 年代结果 */}
      <section className="result-card">
        <EraResult
          predictedEra={result.predicted_era}
          eraCode={result.era_code}
          probabilities={result.era_probabilities}
          top3={result.top3_eras}
        />
      </section>

      {/* 真伪判定 */}
      <section className="result-card">
        <AuthVerdict
          authenticity={result.predicted_authenticity as '真老' | '新仿'}
          confidence={result.authenticity_confidence}
        />
      </section>

      {/* 推理信息 */}
      <div className="inference-meta">
        <span>推理耗时: {result.inference_time_ms}ms</span>
      </div>

      {/* ── AI 鉴定后保存提示 ── */}
      {showSavePrompt && (
        <div className="save-prompt-overlay">
          <div className="save-prompt-card">
            <h3>是否将此鉴定结果保存入标注库？</h3>
            <p>保存后可作为训练数据，帮助提升模型精度。</p>
            <div className="save-prompt-buttons">
              <button
                className="btn btn-success"
                onClick={() => handleSaveAnnotation('真老')}
              >
                ✅ 是，保存为真老（0）
              </button>
              <button
                className="btn btn-danger"
                onClick={() => handleSaveAnnotation('新仿')}
              >
                ✅ 是，保存为新仿（1）
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => {
                  // 跳转到标注页并预填数据
                  navigate(`/annotate?pieceId=${pieceId}&correct=1`);
                }}
              >
                ✏️ 修正后保存
              </button>
              <button
                className="btn btn-ghost"
                onClick={() => setShowSavePrompt(false)}
              >
                ❌ 不保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import { useNavigate } from 'react-router-dom';
