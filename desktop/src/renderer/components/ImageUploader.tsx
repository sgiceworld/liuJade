/**
 * 古玉鉴真 — 图片上传组件
 *
 * 支持拖拽上传 + 点击选择 + 多文件
 */

import React, { useCallback, useRef } from 'react';

interface ImageUploaderProps {
  images: string[];
  onImagesChange: (images: string[]) => void;
  maxImages: number;
  label: string;
}

export function ImageUploader({
  images,
  onImagesChange,
  maxImages,
  label,
}: ImageUploaderProps): React.ReactElement {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const files = Array.from(e.dataTransfer.files);
      const imageFiles = files.filter((f) => f.type.startsWith('image/'));
      const newPaths = imageFiles.map((f) => f.path);
      const combined = [...images, ...newPaths].slice(0, maxImages);
      onImagesChange(combined);
    },
    [images, maxImages, onImagesChange]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || []);
      const newPaths = files.map((f) => f.path);
      const combined = [...images, ...newPaths].slice(0, maxImages);
      onImagesChange(combined);
    },
    [images, maxImages, onImagesChange]
  );

  const removeImage = useCallback(
    (index: number) => {
      const updated = images.filter((_, i) => i !== index);
      onImagesChange(updated);
    },
    [images, onImagesChange]
  );

  return (
    <div className="image-uploader">
      {/* 拖拽区域 */}
      <div
        className="drop-zone"
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <div className="drop-zone-content">
          <span className="drop-icon">📁</span>
          <p>{label}</p>
          <p className="hint">
            已选择 {images.length}/{maxImages} 张
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />
      </div>

      {/* 缩略图预览 */}
      {images.length > 0 && (
        <div className="image-preview-grid">
          {images.map((path, index) => (
            <div key={index} className="image-preview-item">
              <img
                src={`file://${path}`}
                alt={`图片 ${index + 1}`}
                className="preview-thumb"
              />
              <button
                className="btn-remove"
                onClick={(e) => {
                  e.stopPropagation();
                  removeImage(index);
                }}
              >
                ✕
              </button>
              <span className="image-index">{index + 1}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
