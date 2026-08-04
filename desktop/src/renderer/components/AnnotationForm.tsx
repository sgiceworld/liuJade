/**
 * 古玉鉴真 — 标注表单组件
 *
 * 字段:
 * 0. 标签编码 (自动生成)
 * 1. 品名 (时代+材质+器型)
 * 2. 材质 (下拉选择)
 * 3. 尺寸 (长/宽/高/厚/直径)
 * 4. 来源 (馆藏/拍卖/著录 + 详情)
 * + 真伪 + 年代代码
 */

import React, { useState } from 'react';

const MATERIALS = [
  '和田白玉', '和田青玉', '和田碧玉', '和田青花',
  '翡翠（翠玉）', '岫玉', '玛瑙', '水晶',
  '独山玉', '绿松石', '琥珀', '其他',
];

const SOURCE_TYPES = ['馆藏', '拍卖', '著录'];

const ERA_OPTIONS = [
  { code: 'A', name: '文化期' },
  { code: 'B', name: '商代' },
  { code: 'C', name: '春秋' },
  { code: 'D', name: '战国' },
  { code: 'E', name: '秦汉' },
  { code: 'F', name: '三国两晋南北朝' },
  { code: 'G', name: '唐' },
  { code: 'H', name: '宋' },
  { code: 'I', name: '金元' },
  { code: 'J', name: '明' },
  { code: 'K', name: '清' },
  { code: 'L', name: '民国' },
  { code: 'M', name: '出口创汇' },
  { code: 'N', name: '现代' },
];

interface AnnotationFormProps {
  initialValues?: Partial<AnnotationData>;
  onSubmit: (data: AnnotationData) => void;
  onCancel: () => void;
  onImagesChange?: (paths: string[]) => void;
}

export interface AnnotationData {
  authenticity: '真老' | '新仿' | '非玉器数据';
  eraCode: string;
  productName: string;
  material: string;
  dimensions: {
    length?: number;
    width?: number;
    height?: number;
    thickness?: number;
    diameter?: number;
  };
  sourceType: string;
  sourceDetail: string;
  annotatedBy: string;
  annotationConfidence: number;
}

export function AnnotationForm({
  initialValues,
  onSubmit,
  onCancel,
}: AnnotationFormProps): React.ReactElement {
  const [authenticity, setAuthenticity] = useState<'真老' | '新仿' | '非玉器数据'>(
    initialValues?.authenticity || '真老'
  );
  const isNotJade = authenticity === '非玉器数据';
  const [eraCode, setEraCode] = useState(initialValues?.eraCode || '');
  const [productName, setProductName] = useState(initialValues?.productName || '');
  const [material, setMaterial] = useState(initialValues?.material || '');
  const [dimensions, setDimensions] = useState(
    initialValues?.dimensions || {}
  );
  const [sourceType, setSourceType] = useState(initialValues?.sourceType || '');
  const [sourceDetail, setSourceDetail] = useState(initialValues?.sourceDetail || '');
  const [annotatedBy, setAnnotatedBy] = useState(initialValues?.annotatedBy || '');
  const [confidence, setConfidence] = useState(
    initialValues?.annotationConfidence || 5
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      authenticity,
      eraCode,
      productName,
      material,
      dimensions,
      sourceType,
      sourceDetail,
      annotatedBy,
      annotationConfidence: confidence,
    });
  };

  const updateDimension = (key: string, value: string) => {
    setDimensions((prev) => ({
      ...prev,
      [key]: value ? parseFloat(value) : undefined,
    }));
  };

  return (
    <form className="annotation-form" onSubmit={handleSubmit}>
      {/* 真伪选择 */}
      <div className="form-group">
        <label>真伪判定 *</label>
        <div className="toggle-group">
          <button
            type="button"
            className={`toggle-btn ${authenticity === '真老' ? 'active genuine' : ''}`}
            onClick={() => setAuthenticity('真老')}
          >
            真老 (0)
          </button>
          <button
            type="button"
            className={`toggle-btn ${authenticity === '新仿' ? 'active fake' : ''}`}
            onClick={() => setAuthenticity('新仿')}
          >
            新仿 (1)
          </button>
          <button
            type="button"
            className={`toggle-btn ${isNotJade ? 'active' : ''}`}
            style={isNotJade ? { borderColor: '#888', background: '#f0efec', color: '#52473e' } : {}}
            onClick={() => setAuthenticity('非玉器数据')}
          >
            非玉器
          </button>
        </div>
      </div>

      {isNotJade ? (
        <div className="form-group">
          <label>备注</label>
          <textarea value={productName} onChange={e => setProductName(e.target.value)}
            rows={2} style={{ width: '100%', resize: 'vertical', fontFamily: 'inherit', fontSize: '0.85rem', padding: '8px 12px', border: '1px solid #d9d3c7', borderRadius: 6 }}
            placeholder="非玉器数据说明（如：目录、序言等）" />
        </div>
      ) : (
        <>
      {/* 年代选择 */}
      <div className="form-group">
        <label>年代 *</label>
        <select
          value={eraCode}
          onChange={(e) => setEraCode(e.target.value)}
          required
        >
          <option value="">请选择年代</option>
          {ERA_OPTIONS.map((era) => (
            <option key={era.code} value={era.code}>
              {era.code} — {era.name}
            </option>
          ))}
        </select>
      </div>

      {/* 品名 */}
      <div className="form-group">
        <label>1. 品名（标准定名：时代+材质+器型）*</label>
        <input
          type="text"
          value={productName}
          onChange={(e) => setProductName(e.target.value)}
          placeholder="例如: 清和田玉三羊开泰摆件"
          required
        />
      </div>

      {/* 材质 */}
      <div className="form-group">
        <label>2. 材质 *</label>
        <select
          value={material}
          onChange={(e) => setMaterial(e.target.value)}
          required
        >
          <option value="">请选择材质</option>
          {MATERIALS.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      {/* 尺寸 */}
      <div className="form-group">
        <label>3. 尺寸 (mm)</label>
        <div className="dimension-inputs">
          {[
            { key: 'length', label: '长' },
            { key: 'width', label: '宽' },
            { key: 'height', label: '高' },
            { key: 'thickness', label: '厚' },
            { key: 'diameter', label: '直径' },
          ].map((dim) => (
            <div key={dim.key} className="dim-input">
              <label>{dim.label}</label>
              <input
                type="number"
                step="0.1"
                min="0"
                value={(dimensions as any)[dim.key] || ''}
                onChange={(e) => updateDimension(dim.key, e.target.value)}
                placeholder="—"
              />
            </div>
          ))}
        </div>
      </div>

      {/* 来源 */}
      <div className="form-group">
        <label>4. 来源 *</label>
        <select
          value={sourceType}
          onChange={(e) => setSourceType(e.target.value)}
          required
        >
          <option value="">请选择来源类型</option>
          {SOURCE_TYPES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <input
          type="text"
          value={sourceDetail}
          onChange={(e) => setSourceDetail(e.target.value)}
          placeholder="馆藏机构名 / 拍卖行 / 著录书名"
          className="mt-2"
        />
      </div>

      {/* 标注人 + 置信度 */}
      <div className="form-row">
        <div className="form-group">
          <label>标注人</label>
          <input
            type="text"
            value={annotatedBy}
            onChange={(e) => setAnnotatedBy(e.target.value)}
            placeholder="姓名"
          />
        </div>
        <div className="form-group">
          <label>标注置信度 (1-5)</label>
          <div className="confidence-stars">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                type="button"
                className={`star ${star <= confidence ? 'active' : ''}`}
                onClick={() => setConfidence(star)}
              >
                ★
              </button>
            ))}
          </div>
        </div>
      </div>
      </>
      )}

      {/* 按钮 */}
      <div className="form-actions">
        <button type="submit" className="btn btn-primary">
          提交标注
        </button>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          取消
        </button>
      </div>
    </form>
  );
}
