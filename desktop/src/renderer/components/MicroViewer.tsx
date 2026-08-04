/**
 * 古玉鉴真 — 微距图深度查看组件
 *
 * 支持:
 * - 鼠标滚轮缩放
 * - 拖拽平移
 * - 局部高分辨率显示
 * - 切换微距图源
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';

interface MicroViewerProps {
  imagePaths: string[];
}

export function MicroViewer({ imagePaths }: MicroViewerProps): React.ReactElement {
  const [activeIndex, setActiveIndex] = useState(0);
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const canvasRef = useRef<HTMLDivElement>(null);

  const activeImage = imagePaths[activeIndex] || null;

  // 缩放
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.15 : 0.15;
    setScale((prev) => Math.max(0.3, Math.min(8, prev + delta)));
  }, []);

  // 拖拽
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
  }, [position]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging) return;
    setPosition({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  }, [isDragging, dragStart]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // 恢复
  const resetView = useCallback(() => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  }, []);

  // 缩放按钮
  const zoomIn = () => setScale((s) => Math.min(8, s + 0.3));
  const zoomOut = () => setScale((s) => Math.max(0.3, s - 0.3));
  const zoomFit = () => {
    if (!canvasRef.current) return;
    const containerW = canvasRef.current.clientWidth;
    const containerH = canvasRef.current.clientHeight;
    const img = new Image();
    img.src = `file://${activeImage}`;
    img.onload = () => {
      const fitScale = Math.min(
        containerW / img.naturalWidth,
        containerH / img.naturalHeight,
        3
      );
      setScale(fitScale);
      setPosition({ x: 0, y: 0 });
    };
  };

  if (!activeImage) {
    return (
      <div className="micro-viewer">
        <div className="micro-viewer-toolbar">
          <span style={{ color: '#888', fontSize: '0.78rem' }}>微距查看器 — 请上传微距图</span>
        </div>
        <div className="micro-canvas" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ color: '#555' }}>暂无微距图</span>
        </div>
      </div>
    );
  }

  return (
    <div className="micro-viewer">
      {/* 工具栏 */}
      <div className="micro-viewer-toolbar">
        <button onClick={zoomIn} title="放大">🔍+</button>
        <button onClick={zoomOut} title="缩小">🔍−</button>
        <button onClick={zoomFit} title="适合窗口">⊞</button>
        <button onClick={resetView} title="1:1">1:1</button>
        <span style={{ color: '#888', fontSize: '0.7rem', marginLeft: 'auto' }}>
          {(scale * 100).toFixed(0)}% | {activeIndex + 1}/{imagePaths.length}
        </span>
      </div>

      {/* 画布 */}
      <div
        ref={canvasRef}
        className="micro-canvas"
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <img
          src={`file://${activeImage}`}
          alt={`微距图 ${activeIndex + 1}`}
          draggable={false}
          style={{
            transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
            cursor: isDragging ? 'grabbing' : 'grab',
          }}
        />
      </div>

      {/* 缩略图导航 */}
      {imagePaths.length > 1 && (
        <div style={{
          display: 'flex', gap: 6, padding: '8px 10px',
          background: '#222', overflowX: 'auto',
        }}>
          {imagePaths.map((path, i) => (
            <div
              key={i}
              onClick={() => setActiveIndex(i)}
              style={{
                width: 48, height: 48, flexShrink: 0,
                borderRadius: 4, overflow: 'hidden',
                cursor: 'pointer',
                border: i === activeIndex ? '2px solid #5aa36b' : '2px solid #444',
                opacity: i === activeIndex ? 1 : 0.5,
              }}
            >
              <img
                src={`file://${path}`}
                alt={`缩略图 ${i + 1}`}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
