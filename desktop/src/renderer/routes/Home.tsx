/**
 * 古玉鉴真 — 首页
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';

export function Home(): React.ReactElement {
  const navigate = useNavigate();

  return (
    <div className="page home-page">
      <div className="hero">
        <h1>古玉鉴真</h1>
        <p className="hero-subtitle">AI 驱动的古玉鉴定与数据标注系统</p>
        <p className="hero-desc">
          基于深度学习的多视角图像分析，识别沁色纹理与工痕特征，
          判定玉器年代与真伪。面向专业鉴定师与收藏家。
        </p>
        <div className="hero-actions">
          <button
            className="btn btn-primary btn-lg"
            onClick={() => navigate('/authenticate')}
          >
            🔍 开始鉴定
          </button>
          <button
            className="btn btn-secondary btn-lg"
            onClick={() => navigate('/annotate')}
          >
            ✏️ 数据标注
          </button>
        </div>
      </div>

      <div className="feature-grid">
        <div className="feature-card">
          <h3>🔬 多视角分析</h3>
          <p>支持同一玉器多角度图片同时分析，自动提取器型特征。</p>
        </div>
        <div className="feature-card">
          <h3>🔍 微距鉴定</h3>
          <p>高分辨率微距图分析沁色纹理和工痕细节，微距图 10× 权重。</p>
        </div>
        <div className="feature-card">
          <h3>📊 14 年代判定</h3>
          <p>覆盖文化期至现代完整谱系，分层识别混淆更少。</p>
        </div>
        <div className="feature-card">
          <h3>🏛️ 馆藏数据</h3>
          <p>88 家全球博物馆馆藏玉器数据支撑，中外出土与传世全覆盖。</p>
        </div>
      </div>

      <div className="era-reference">
        <h3>年代分类体系</h3>
        <div className="era-grid">
          {[
            'A: 文化期', 'B: 商代', 'C: 春秋', 'D: 战国',
            'E: 秦汉', 'F: 三国两晋南北朝', 'G: 唐', 'H: 宋',
            'I: 金元', 'J: 明', 'K: 清', 'L: 民国',
            'M: 出口创汇', 'N: 现代',
          ].map((era) => (
            <span key={era} className="era-tag">{era}</span>
          ))}
        </div>
      </div>
    </div>
  );
}
