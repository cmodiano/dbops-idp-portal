import { Layout, Spin, App as AntApp } from 'antd';
import { Suspense, useEffect } from 'react';
import { Outlet } from 'react-router';
import { ErrorBoundary } from '../ErrorBoundary';
import { TopNav } from './TopNav';
import './AppLayout.css';
import { prefetchEngineIcons } from '../../utils/engineIconCache';
import { setNotificationCallback } from '../../services/api_client';

const { Header, Content } = Layout;

export function AppLayout() {
  const { notification } = AntApp.useApp();

  // Wire notification callback so api_client can display UI notifications
  // without depending on antd directly (DIP — Story 34.2).
  // Cleanup resets to no-op on unmount to avoid stale closure after logout.
  useEffect(() => {
    setNotificationCallback((type, config) => notification[type](config));
    return () => setNotificationCallback(() => {});
  }, [notification]);

  // Warm the engine icon cache once auth is confirmed (this component only renders
  // inside ProtectedRoute, so the JWT token is already available at this point).
  useEffect(() => {
    prefetchEngineIcons();
  }, []);

  return (
    <Layout style={{ minHeight: '100vh', background: 'transparent' }}>
      {/* Skip link for keyboard users (WCAG 2.4.1) */}
      <a href="#main-content" className="skip-link">
        Aller au contenu principal
      </a>
      <Header
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 100,
          height: 64,
          lineHeight: '64px',
          padding: '0 32px',
          display: 'flex',
          alignItems: 'center',
          transition: 'all 0.2s ease',
        }}
      >
        <TopNav />
      </Header>
      <Content
        id="main-content"
        tabIndex={-1}
        style={{
          marginTop: 64,
          padding: '32px 40px',
          background: 'transparent',
          minHeight: 'calc(100vh - 64px)',
          flex: 'none',
          overflow: 'visible',
          transition: 'background 0.2s ease',
        }}
      >
        <ErrorBoundary>
          <Suspense fallback={<Spin size="large" style={{ display: 'block', margin: '100px auto' }} />}>
            <Outlet />
          </Suspense>
        </ErrorBoundary>
      </Content>
    </Layout>
  );
}
