import React from 'react';
import { Link, useLocation } from 'react-router-dom';

export default function Layout({ children }) {
  const location = useLocation();

  const isActive = (path) => location.pathname.startsWith(path) ? 'nav-link active' : 'nav-link';

  return (
    <div className="layout-container">
      <nav className="sidebar">
        <h1>Seismic Dash</h1>
        <Link to="/sensors" className={isActive('/sensors')}>Sensors</Link>
        <Link to="/history" className={isActive('/history')}>History</Link>
        <Link to="/health" className={isActive('/health')}>Health</Link>
      </nav>
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}