/**
 * 古玉鉴真 — 标注页面
 */

import React, { useState, useCallback, useEffect } from 'react';
import { AnnotationForm, AnnotationData } from '../components/AnnotationForm';
import { useInference } from '../hooks/useInference';

type Mode = 'new' | 'preview';
const API = 'http://localhost:8720';
const ERA_NAMES_MAP: Record<string, string> = {
  'A':'文化期','B':'商代','C':'春秋','D':'战国','E':'秦汉',
  'F':'三国两晋南北朝','G':'唐','H':'宋','I':'金元','J':'明',
  'K':'清','L':'民国','M':'出口创汇','N':'现代',
};

interface JadeRecord {
  id: string; label_code: string; product_name: string;
  material: string; era: string; era_code: string; authenticity: string;
  source_type: string; source_detail: string; annotated_by: string;
  annotation_confidence: number; review_count: number; review_status: string;
  notes: string; image_paths: string[]; training_image: string; created_at: string;
}

export function Annotate(): React.ReactElement {
  const { saveAnnotation } = useInference();
  const [mode, setMode] = useState<Mode>('new');
  const [saved, setSaved] = useState(false);
  const [editRecord, setEditRecord] = useState<Partial<AnnotationData> | undefined>(undefined);
  const [editPieceId, setEditPieceId] = useState<string>('');
  const [editImage, setEditImage] = useState<string>('');
  const [imgVersion, setImgVersion] = useState(0);
  const [imgLoading, setImgLoading] = useState(false);
  const [imgError, setImgError] = useState(false);
  const imgTimer = React.useRef<ReturnType<typeof setTimeout>>();

  // Preview state
  const [records, setRecords] = useState<JadeRecord[]>([]);
  const [totalRecords, setTotalRecords] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(0);
  const [currentIndex, setCurrentIndex] = useState(0);
  const PER_PAGE = 20;

  // Load next record into edit form
  const loadNextRecord = useCallback((nextIdx: number) => {
    const next = records[nextIdx];
    if (!next) return;
    setEditPieceId(next.id);
    setEditRecord({
      authenticity: next.authenticity as '真老' | '新仿',
      eraCode: next.era_code,
      productName: next.product_name,
      material: next.material,
      sourceType: next.source_type,
      sourceDetail: next.source_detail,
      annotatedBy: next.annotated_by,
      annotationConfidence: next.annotation_confidence,
    });
    const page = next.image_paths?.[0] || '';
    // Only use artifact crop if reviewed (training_image exists); otherwise page image
    setEditImage(next.training_image || page);
    setImgVersion(v => v + 1);
    setImgError(false);
    setCurrentIndex(nextIdx);
  }, [records]);

  const handleSubmit = useCallback(async (data: AnnotationData) => {
    try {
      await saveAnnotation({ ...data, pieceId: editPieceId });
      // Update local record in-place
      setRecords(prev => prev.map(r =>
        r.id === editPieceId ? { ...r, ...data, era: ERA_NAMES_MAP[data.eraCode] || r.era } : r
      ));
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      const nextIdx = currentIndex + 1;
      if (nextIdx < records.length) {
        loadNextRecord(nextIdx);
      } else {
        setEditRecord(undefined);
        setEditImage('');
        setEditPieceId('');
        setMode('preview');
      }
    } catch (err: any) {
      alert('保存失败: ' + (err.message || 'Unknown error'));
    }
  }, [saveAnnotation, currentIndex, records, loadNextRecord, editPieceId]);

  // Load from API
  const doLoad = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const resp = await fetch(`${API}/annotations?limit=200&offset=0`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json = await resp.json();
      const sorted = (json.data || []).sort((a: JadeRecord, b: JadeRecord) => {
        if (a.review_count !== b.review_count) return b.review_count - a.review_count;
        if (a.annotation_confidence !== b.annotation_confidence) return b.annotation_confidence - a.annotation_confidence;
        return 0;
      });
      setRecords(sorted);
      setTotalRecords(json.total || 0);
      setPage(0);
    } catch (e: any) {
      setError(e.message || 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (mode === 'preview') doLoad();
  }, [mode, doLoad]); // eslint-disable-line

  const paged = records.slice(page * PER_PAGE, (page + 1) * PER_PAGE);
  const totalPages = Math.max(1, Math.ceil(records.length / PER_PAGE));

  // Best image: training crop > artifact crop > page image
  const bestImgUrl = (rec: JadeRecord): string => {
    if (rec.training_image) return `${API}/images/${rec.training_image.replace(/\\/g, '/')}`;
    const page = rec.image_paths?.[0];
    if (!page) return '';
    const base = page.replace(/\\/g, '/');
    return `${API}/images/${base.replace(/\.png$/, '_artifact.png')}`;
  };
  const pageImgUrl = (rec: JadeRecord): string => {
    const page = rec.image_paths?.[0];
    return page ? `${API}/images/${page.replace(/\\/g, '/')}` : '';
  };

  return (
    <div className="page annotate-page">
      <h2>数据标注</h2>

      <div className="toggle-group" style={{ marginBottom: 20 }}>
        <button className={`toggle-btn ${mode === 'new' ? 'active genuine' : ''}`}
          onClick={() => { setMode('new'); setEditRecord(undefined); setEditImage(''); }}>✏️ {editRecord ? '编辑标注' : '新建标注'}</button>
        <button className={`toggle-btn ${mode === 'preview' ? 'active genuine' : ''}`}
          onClick={() => setMode('preview')}>👁️ 预览标注 ({totalRecords || '...'})</button>
      </div>

      {mode === 'new' && (
        <>
          {saved && <div className="success-banner">✅ 标注已保存！已加载下一条</div>}
          {editRecord && (
            <div className="stats-bar" style={{ marginBottom: 12 }}>
              <span>第 {currentIndex + 1} / {records.length} 条</span>
              <button className="btn btn-secondary btn-sm" onClick={() => loadNextRecord(currentIndex - 1)} disabled={currentIndex <= 0}>← 上一条</button>
              <button className="btn btn-secondary btn-sm" onClick={() => loadNextRecord(currentIndex + 1)} disabled={currentIndex >= records.length - 1}>下一条 →</button>
            </div>
          )}
          <div className="annotate-split">
            <div className="annotate-left">
              <AnnotationForm
                key={editPieceId || 'new'}
                onSubmit={handleSubmit}
                onCancel={() => { setMode('preview'); setEditRecord(undefined); setEditImage(''); setEditPieceId(''); }}
                initialValues={editRecord}
              />
            </div>
            <div className="annotate-right">
              {editImage ? (
                <div className="image-viewer">
                  <div className="image-viewer-main" style={{ position: 'relative', minHeight: 280 }}>
                    {imgLoading && (
                      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.6)', zIndex: 2 }}>
                        <span style={{ color: '#ccc', fontSize: '0.9rem' }}>⏳ 加载中...</span>
                      </div>
                    )}
                    {imgError && (
                      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: '#1a1a1a', zIndex: 1, gap: 8 }}>
                        <span style={{ fontSize: '2rem' }}>⚠️</span>
                        <span style={{ color: '#e88', fontSize: '0.9rem' }}>图片加载失败</span>
                        <span style={{ color: '#888', fontSize: '0.72rem' }}>文件可能不存在或已损坏</span>
                        <button className="btn btn-secondary btn-sm" style={{ marginTop: 8 }}
                          onClick={() => { setImgError(false); setImgLoading(true); setImgVersion(v => v + 1); }}>
                          🔄 重试
                        </button>
                      </div>
                    )}
                    <img src={`${API}/images/${editImage.replace(/\\/g, '/')}?v=${imgVersion}`} alt="玉器图片" className="image-viewer-img"
                      style={{ display: imgError ? 'none' : 'block' }}
                      onLoadStart={() => {
                        clearTimeout(imgTimer.current);
                        imgTimer.current = setTimeout(() => setImgLoading(true), 200);
                      }}
                      onLoad={() => { clearTimeout(imgTimer.current); setImgLoading(false); setImgError(false); }}
                      onError={() => {
                        clearTimeout(imgTimer.current); setImgLoading(false); setImgError(true);
                      }} />
                  </div>
                  <div className="image-viewer-nav" style={{ justifyContent: 'space-between', padding: '6px 10px' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--bronze-600)' }}>
                      {editRecord?.productName || '玉器预览'}
                    </span>
                    <button className="btn btn-secondary btn-sm"
                      onClick={() => { setImgError(false); setImgLoading(true); setImgVersion(v => v + 1); }}
                      title="重新加载图片"
                      style={{ padding: '2px 8px', fontSize: '0.7rem' }}>
                      🔄 刷新图片
                    </button>
                  </div>
                </div>
              ) : (
                <div className="image-viewer-empty">
                  <div className="empty-icon">🖼️</div>
                  <p>从预览列表点击记录以查看玉器图片</p>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {mode === 'preview' && (
        <>
          {error && <div className="error-message">❌ {error}</div>}
          {loading && <div className="empty-state"><p>⏳ 加载中...</p></div>}

          {!loading && !error && (
            <>
              <div className="stats-bar">
                <span>共 {totalRecords} 条 | 当前显示 {records.length} 条</span>
                <button className="btn btn-secondary btn-sm" onClick={doLoad} disabled={loading}>🔄 刷新</button>
              </div>

              <div className="record-list">
                {paged.map((rec) => (
                  <div key={rec.id}
                    className="record-item"
                    onClick={() => {
                      const idx = page * PER_PAGE + paged.indexOf(rec);
                      loadNextRecord(idx);
                      setMode('new');
                    }}>
                    <div className="record-main">
                      {                      <img src={bestImgUrl(rec)} className="record-thumb" alt=""
                        onError={(e) => {
                          const t = e.target as HTMLImageElement;
                          const fallback = pageImgUrl(rec);
                          if (t.src !== fallback) { t.src = fallback; }
                          else { t.style.display = 'none'; }
                        }} />}
                      <div className="record-info">
                        <div className="record-top">
                          <span className={`badge ${rec.authenticity === '真老' ? 'genuine' : 'fake'}`}>{rec.authenticity}</span>
                          <span className="record-era">{rec.era} ({rec.era_code})</span>
                          {rec.review_count > 0 && <span className="review-tag-sm reviewed">✅×{rec.review_count}</span>}
                        </div>
                        <div className="record-meta">
                          <span className="record-name">{rec.product_name || '未命名'}</span>
                          <span className="record-source">{rec.source_detail?.slice(0, 30) || '—'}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {totalPages > 1 && (
                <div className="pagination">
                  <button className="btn btn-secondary btn-sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>←</button>
                  <span className="page-info">{page + 1} / {totalPages}</span>
                  <button className="btn btn-secondary btn-sm" disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>→</button>
                </div>
              )}

              {records.length === 0 && !loading && (
                <div className="empty-state"><p>暂无数据，点击刷新加载</p></div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
