/**
 * 古玉鉴真 — 交互式 OCR 审查页面
 *
 * 逐条审查 OCR 结果, 用户确认/修正/标记非玉器。
 */

import React, { useState, useCallback, useEffect } from 'react';

const API = 'http://localhost:8720';
const ERA_OPTIONS = [
  { code: 'A', name: '文化期' }, { code: 'B', name: '商代' }, { code: 'C', name: '春秋' },
  { code: 'D', name: '战国' }, { code: 'E', name: '秦汉' }, { code: 'F', name: '三国两晋南北朝' },
  { code: 'G', name: '唐' }, { code: 'H', name: '宋' }, { code: 'I', name: '金元' },
  { code: 'J', name: '明' }, { code: 'K', name: '清' }, { code: 'L', name: '民国' },
  { code: 'M', name: '出口创汇' }, { code: 'N', name: '现代' },
];
const MATERIALS = ['和田白玉','和田青玉','和田碧玉','和田青花','翡翠（翠玉）','岫玉','玛瑙','水晶','独山玉','绿松石','琥珀','其他'];

interface ReviewData {
  id: string; label_code: string;
  product_name: string; material: string; era: string; era_code: string;
  authenticity: string; source_type: string; source_detail: string; notes: string;
  image_path: string; image_url: string;
  artifact_url: string; text_url: string;
  remaining: number;
  review_count: number; review_status: string; last_reviewed_at: string;
  ocr_suggestions: any;
}

export function Review(): React.ReactElement {
  const [data, setData] = useState<ReviewData | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState('');
  const [reviewed, setReviewed] = useState(0);

  // Editable fields
  const [productName, setProductName] = useState('');
  const [eraCode, setEraCode] = useState('A');
  const [authenticity, setAuthenticity] = useState('真老');
  const [material, setMaterial] = useState('和田白玉');
  const [sourceType, setSourceType] = useState('著录');
  const [sourceDetail, setSourceDetail] = useState('');
  const [notes, setNotes] = useState('');
  const [dimensions, setDimensions] = useState<any>({});
  const [notJade, setNotJade] = useState(false);

  const loadNext = useCallback(async () => {
    setLoading(true); setStatus('加载中...');
    try {
      const r = await fetch(`${API}/ocr/review/next`);
      const d = await r.json();
      if (d.data === null) {
        setStatus('全部审查完成!');
        setData(null);
      } else {
        setData(d.data);
        // Pre-fill from OCR suggestions or existing data
        const sug = d.data.ocr_suggestions || {};
        setProductName(d.data.product_name || sug.artifact_name ? `${sug.era_name || d.data.era}${sug.material || d.data.material}${sug.artifact_name || ''}` : '');
        setEraCode(sug.era_code || d.data.era_code || 'A');
        setAuthenticity(d.data.authenticity || '真老');
        setMaterial(sug.material || d.data.material || '和田白玉');
        setSourceType(d.data.source_type || '著录');
        setSourceDetail(d.data.source_detail || sug.collection || '');
        setDimensions(sug.dimensions || {});
        setNotes(d.data.notes || '');
        setNotJade(false);
        setStatus('');
      }
    } catch (e) { setStatus('加载失败: ' + String(e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadNext(); }, [loadNext]);

  const handleConfirm = useCallback(async () => {
    if (!data || saving) return;
    setSaving(true);
    try {
      const payload: any = {
        id: data.id,
        product_name: productName || data.product_name,
        era_code: eraCode,
        era: ERA_OPTIONS.find(e => e.code === eraCode)?.name || '',
        authenticity: notJade ? '非玉器数据' : authenticity,
        material: notJade ? '其他' : material,
        source_type: sourceType,
        source_detail: sourceDetail,
        notes: notes + (notJade ? ' [非玉器数据]' : ' [人工确认]'),
        annotation_confidence: 5,
        annotated_by: '人工确认',
        dimensions: Object.keys(dimensions).length > 0 ? dimensions : null,
      };
      const r = await fetch(`${API}/ocr/review/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (r.ok) {
        setReviewed(c => c + 1);
        setStatus('已保存 ✓');
        setTimeout(() => loadNext(), 400);
      }
    } catch (e) { setStatus('保存失败: ' + String(e)); }
    finally { setSaving(false); }
  }, [data, saving, productName, eraCode, authenticity, material, sourceType, sourceDetail, notes, dimensions, notJade, loadNext]);

  const handleSkip = useCallback(async () => {
    if (!data || saving) return;
    setSaving(true);
    try {
      await fetch(`${API}/ocr/review/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: data.id,
          product_name: data.product_name || '待标注',
          era_code: data.era_code || 'A',
          era: data.era || '待OCR确认',
          authenticity: data.authenticity || '真老',
          material: data.material || '和田白玉',
          source_type: data.source_type || '著录',
          source_detail: data.source_detail || '',
          notes: data.notes + ' [跳过]',
          annotation_confidence: 3,
          annotated_by: '跳过审查',
        }),
      });
      setReviewed(c => c + 1);
      setStatus('已跳过 →');
      setTimeout(() => loadNext(), 200);
    } catch (e) { setStatus('错误: ' + String(e)); }
    finally { setSaving(false); }
  }, [data, saving, loadNext]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Enter' && !e.ctrlKey && !e.shiftKey) { e.preventDefault(); handleConfirm(); }
      if (e.key === 's' && e.ctrlKey) { e.preventDefault(); handleSkip(); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleConfirm, handleSkip]);

  const updateDim = (key: string, val: string) => {
    setDimensions((prev: any) => ({ ...prev, [key]: val ? parseFloat(val) : undefined }));
  };

  if (!data && !loading) {
    return <div className="page"><h2>OCR 审查</h2><div className="success-banner">🎉 全部 {reviewed} 条记录已完成审查!</div></div>;
  }

  return (
    <div className="page review-page">
      <h2>OCR 交互审查</h2>

      {/* Progress */}
      <div className="review-progress">
        <div className="progress-text">
          {data ? <>剩余: <strong>{data.remaining}</strong> 条 | 已审查: <strong>{reviewed}</strong> 条</> : '加载中...'}
          {data && (
            <span className="review-tags">
              <span className={`review-tag ${data.review_status}`}>
                {data.review_status === 'imported' ? '📥 未审查' :
                 data.review_status === 'reviewed' ? `✅ 已审查×${data.review_count}` :
                 data.review_status === 'annotated' ? `✏️ 已标注×${data.review_count}` :
                 `📋 ${data.review_status}`}
              </span>
              {data.last_reviewed_at && (
                <span className="review-tag time" title={data.last_reviewed_at}>
                  🕐 {new Date(data.last_reviewed_at).toLocaleDateString('zh-CN')}
                </span>
              )}
            </span>
          )}
        </div>
        <div className="progress-bar-track">
          <div className="progress-bar-fill" style={{
            width: `${data ? (reviewed / (reviewed + (data.remaining || 1))) * 100 : 0}%`
          }} />
        </div>
        <div className="progress-hint">Enter = 确认保存 | Ctrl+S = 跳过</div>
      </div>

      {status && <div className={`review-status ${saving ? 'saving' : ''}`}>{status}</div>}

      <div className="review-split">
        {/* Left: Images */}
        <div className="review-image-panel">
          {notJade ? (
            /* Non-jade: show full page only */
            data?.image_url ? (
              <img src={`${API}${data.image_url}`} alt="页面" className="review-large-img" />
            ) : (
              <div className="image-viewer-empty"><p>无图片</p></div>
            )
          ) : (
            /* Jade: show artifact crop + text region */
            <div className="review-dual-images">
              {data?.artifact_url ? (
                <div className="review-img-box">
                  <div className="review-img-label">📷 玉器照片 (黑底裁剪)</div>
                  <img src={`${API}${data.artifact_url}`} alt="玉器照片" className="review-crop-img" />
                </div>
              ) : data?.image_url ? (
                <div className="review-img-box">
                  <div className="review-img-label">📷 原始页面</div>
                  <img src={`${API}${data.image_url}`} alt="页面" className="review-crop-img" />
                </div>
              ) : null}
              {data?.text_url ? (
                <div className="review-img-box">
                  <div className="review-img-label">📝 文字描述区域</div>
                  <img src={`${API}${data.text_url}`} alt="文字描述" className="review-crop-img" />
                </div>
              ) : null}
            </div>
          )}
          {data?.ocr_suggestions?.raw_text && (
            <details className="ocr-raw-text">
              <summary>OCR 原始文本</summary>
              <pre>{data.ocr_suggestions.raw_text}</pre>
            </details>
          )}
        </div>

        {/* Right: Form */}
        <div className="review-form-panel">
          {/* 非玉器 */}
          <div className="form-group" style={{ background: notJade ? '#fef2f2' : 'transparent', padding: notJade ? 12 : 0, borderRadius: 8 }}>
            <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" checked={notJade} onChange={e => setNotJade(e.target.checked)}
                style={{ width: 18, height: 18 }} />
              <strong style={{ color: notJade ? '#991b1b' : '#666' }}>非玉器数据</strong>
              <span style={{ fontSize: '0.75rem', color: '#999' }}>（非玉器内容的页面，如目录、序言等）</span>
            </label>
          </div>

          {!notJade && (
            <>
              {/* Era */}
              <div className="form-group">
                <label>年代 *</label>
                <select value={eraCode} onChange={e => setEraCode(e.target.value)}>
                  {ERA_OPTIONS.map(e => <option key={e.code} value={e.code}>{e.code}: {e.name}</option>)}
                </select>
              </div>

              {/* Authenticity */}
              <div className="form-group">
                <label>真伪</label>
                <div className="toggle-group">
                  <button className={`toggle-btn ${authenticity === '真老' ? 'active genuine' : ''}`}
                    type="button" onClick={() => setAuthenticity('真老')}>真老 (0)</button>
                  <button className={`toggle-btn ${authenticity === '新仿' ? 'active fake' : ''}`}
                    type="button" onClick={() => setAuthenticity('新仿')}>新仿 (1)</button>
                </div>
              </div>

              {/* Product name */}
              <div className="form-group">
                <label>品名</label>
                <input type="text" value={productName}
                  onChange={e => setProductName(e.target.value)}
                  placeholder="时代+材质+器型" />
              </div>

              {/* Material */}
              <div className="form-group">
                <label>材质</label>
                <select value={material} onChange={e => setMaterial(e.target.value)}>
                  {MATERIALS.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>

              {/* Dimensions */}
              <div className="form-group">
                <label>尺寸 (mm)</label>
                <div className="dimension-inputs">
                  {[{k:'length',l:'长'},{k:'width',l:'宽'},{k:'height',l:'高'},{k:'thickness',l:'厚'},{k:'diameter',l:'直径'}].map(d => (
                    <div key={d.k} className="dim-input">
                      <label>{d.l}</label>
                      <input type="number" step="0.1"
                        value={(dimensions as any)[d.k] || ''}
                        onChange={e => updateDim(d.k, e.target.value)} />
                    </div>
                  ))}
                </div>
              </div>

              {/* Source */}
              <div className="form-group">
                <label>来源</label>
                <select value={sourceType} onChange={e => setSourceType(e.target.value)}>
                  <option value="馆藏">馆藏</option>
                  <option value="拍卖">拍卖</option>
                  <option value="著录">著录</option>
                </select>
                <input type="text" className="mt-2" value={sourceDetail}
                  onChange={e => setSourceDetail(e.target.value)}
                  placeholder="机构/拍卖行/书名" />
              </div>

              {/* Notes */}
              <div className="form-group">
                <label>备注</label>
                <textarea value={notes} onChange={e => setNotes(e.target.value)}
                  rows={2} style={{ width: '100%', resize: 'vertical' }} />
              </div>
            </>
          )}

          {/* Action buttons */}
          <div className="review-actions">
            <button className="btn btn-primary btn-lg" onClick={handleConfirm} disabled={saving || loading}>
              {saving ? '保存中...' : '✓ 确认保存 (Enter)'}
            </button>
            <button className="btn btn-secondary" onClick={handleSkip} disabled={saving}>
              跳过 (Ctrl+S)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
