/**
 * 古玉鉴真 — 设置页面
 */

import React, { useEffect, useState } from 'react';

export function Settings(): React.ReactElement {
  const [modelInfo, setModelInfo] = useState<any>(null);

  useEffect(() => {
    window.electronAPI.modelStatus().then((result) => {
      if (result?.data) setModelInfo(result.data);
    });
  }, []);

  return (
    <div className="page settings-page">
      <h2>设置</h2>

      <section className="settings-section">
        <h3>模型状态</h3>
        {modelInfo ? (
          <div className="model-info">
            <div className="info-row">
              <span>版本:</span>
              <span>{modelInfo.version}</span>
            </div>
            <div className="info-row">
              <span>推理引擎:</span>
              <span>{modelInfo.providers?.join(', ') || 'CPU'}</span>
            </div>
          </div>
        ) : (
          <p>模型未加载</p>
        )}
      </section>

      <section className="settings-section">
        <h3>数据目录</h3>
        <ul>
          <li>标注文件 (真): <code>./annotation_data/genuine.jsonl</code></li>
          <li>标注文件 (伪): <code>./annotation_data/fake.jsonl</code></li>
          <li>数据库: <code>./jade.db</code></li>
        </ul>
      </section>

      <section className="settings-section">
        <h3>关于</h3>
        <p>古玉鉴真 v0.1.0</p>
        <p>基于 ConvNeXt-V2 双流多视角架构</p>
        <p>面向专业古玉鉴定与学术研究</p>
      </section>
    </div>
  );
}
