/**
 * 古玉鉴真 — 鉴定页面
 *
 * 用户上传玉器图片 → AI 鉴定 → 展示结果
 * 重点提示用户上传微距图
 */

import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ImageUploader } from '../components/ImageUploader';
import { MicroViewer } from '../components/MicroViewer';
import { useInference } from '../hooks/useInference';

export function Authenticate(): React.ReactElement {
  const navigate = useNavigate();
  const { authenticate, isLoading, error } = useInference();

  const [macroImages, setMacroImages] = useState<string[]>([]);
  const [microImages, setMicroImages] = useState<string[]>([]);
  const [activeStep, setActiveStep] = useState<'upload' | 'confirm' | 'running'>('upload');

  // 处理开始鉴定
  const handleStartAuth = useCallback(async () => {
    if (macroImages.length === 0) {
      alert('请至少上传一张宏观图片');
      return;
    }

    setActiveStep('running');
    try {
      const result = await authenticate(macroImages, microImages);
      if (result?.piece_id) {
        navigate(`/results/${result.piece_id}`);
      }
    } catch (err) {
      console.error('Authentication failed:', err);
      setActiveStep('confirm');
    }
  }, [macroImages, microImages, authenticate, navigate]);

  return (
    <div className="page authenticate-page">
      <h2>古玉鉴定</h2>

      {/* 微距图提示 */}
      <div className="tips-box">
        <h3>📸 上传提示</h3>
        <ul>
          <li>请上传同一件玉器<strong>不同视角</strong>的图片（3-5张）</li>
          <li>
            尤其请上传<strong>微距图</strong>，表现玉器的
            <em>沁色</em>纹理和<em>工痕</em>细节
          </li>
          <li>不同年代的沁色表现不同，南北方土质出土的受沁情况也有差异</li>
          <li>不同时期加工工具留下的微距痕迹各不相同，微距图是鉴定关键</li>
        </ul>
      </div>

      {/* 宏观图上传 */}
      <section className="upload-section">
        <h3>
          宏观图片 <span className="hint">（器型、沁色整体面）</span>
        </h3>
        <ImageUploader
          images={macroImages}
          onImagesChange={setMacroImages}
          maxImages={5}
          label="拖拽或点击上传宏观图"
        />
      </section>

      {/* 微距图上传 */}
      <section className="upload-section">
        <h3>
          微距图片 <span className="hint">（沁色纹理、工痕细节）</span>
        </h3>
        <ImageUploader
          images={microImages}
          onImagesChange={setMicroImages}
          maxImages={3}
          label="拖拽或点击上传微距图 (高分辨率)"
        />
        {microImages.length > 0 && (
          <MicroViewer imagePaths={microImages} />
        )}
      </section>

      {/* 操作按钮 */}
      <div className="action-bar">
        <button
          className="btn btn-primary btn-lg"
          onClick={handleStartAuth}
          disabled={isLoading || macroImages.length === 0}
        >
          {isLoading ? '鉴定中...' : '🔍 开始鉴定'}
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => {
            setMacroImages([]);
            setMicroImages([]);
          }}
        >
          清空重选
        </button>
      </div>

      {error && (
        <div className="error-message">
          鉴定失败: {error}
        </div>
      )}
    </div>
  );
}
