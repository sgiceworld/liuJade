/**
 * 古玉鉴真 — React 应用入口
 */

import React from 'react';
import { HashRouter, Routes, Route, NavLink } from 'react-router-dom';
import { Home } from './routes/Home';
import { Authenticate } from './routes/Authenticate';
import { Results } from './routes/Results';
import { History } from './routes/History';
import { Annotate } from './routes/Annotate';
import { Review } from './routes/Review';
import { Settings } from './routes/Settings';

const navItems = [
  { to: '/', label: '首页', icon: '🏠' },
  { to: '/authenticate', label: '鉴定', icon: '🔍' },
  { to: '/review', label: '审查', icon: '👁️' },
  { to: '/history', label: '历史', icon: '📋' },
  { to: '/annotate', label: '标注', icon: '✏️' },
  { to: '/settings', label: '设置', icon: '⚙️' },
];

export function App(): React.ReactElement {
  return (
    <HashRouter>
      <div className="app-container">
        {/* 侧边导航 */}
        <nav className="sidebar">
          <div className="sidebar-header">
            <h1>古玉鉴真</h1>
            <p className="subtitle">AI 古玉鉴定系统</p>
          </div>
          <ul className="nav-list">
            {navItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `nav-link ${isActive ? 'active' : ''}`
                  }
                >
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-label">{item.label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
          <div className="sidebar-footer">
            <span className="version">v0.1.0</span>
          </div>
        </nav>

        {/* 主内容区 */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/authenticate" element={<Authenticate />} />
            <Route path="/results/:pieceId" element={<Results />} />
            <Route path="/review" element={<Review />} />
            <Route path="/history" element={<History />} />
            <Route path="/annotate" element={<Annotate />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </HashRouter>
  );
}
