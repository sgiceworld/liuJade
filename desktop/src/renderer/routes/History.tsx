/**
 * 古玉鉴真 — 历史记录页面
 */

import React, { useEffect, useState } from 'react';
import { apiListAnnotations } from '../services/api';

export function History(): React.ReactElement {
  const [records, setRecords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const result = await apiListAnnotations();
        if (result?.data) {
          setRecords(result.data);
        }
      } catch (err) {
        console.error('Failed to load history:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <div className="page">加载中...</div>;

  return (
    <div className="page history-page">
      <h2>鉴定与标注历史</h2>

      {records.length === 0 ? (
        <div className="empty-state">
          <p>暂无记录</p>
          <p className="hint">完成鉴定或标注后，记录将显示在此处。</p>
        </div>
      ) : (
        <div className="history-table-wrapper">
          <table className="history-table">
            <thead>
              <tr>
                <th>标签编码</th>
                <th>品名</th>
                <th>年代</th>
                <th>真伪</th>
                <th>材质</th>
                <th>来源</th>
                <th>标注人</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              {records.map((rec) => (
                <tr key={rec.id}>
                  <td className="code-cell">{rec.label_code}</td>
                  <td>{rec.product_name || '—'}</td>
                  <td>{rec.era}</td>
                  <td>
                    <span className={`badge ${rec.authenticity === '真老' ? 'genuine' : 'fake'}`}>
                      {rec.authenticity}
                    </span>
                  </td>
                  <td>{rec.material || '—'}</td>
                  <td>{rec.source_type || '—'}</td>
                  <td>{rec.annotated_by || '—'}</td>
                  <td>{rec.created_at ? new Date(rec.created_at).toLocaleDateString('zh-CN') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
