import { Layout, Spin } from 'antd';
import { Suspense, useEffect } from 'react';
import { Outlet } from 'react-router';
import { ErrorBoundary } from '../ErrorBoundary';
import { TopNav } from './TopNav';
import { prefetchEngineIcons } from '../../utils/engineIconCache';

const { Header, Content } = Layout;

export function AppLayout() {
  // Warm the engine icon cache once auth is confirmed (this component only renders
  // inside ProtectedRoute, so the JWT token is already available at this point).
  useEffect(() => {
    prefetchEngineIcons();
  }, []);

  return (
    <Layout style={{ minHeight: '100vh', background: 'transparent' }}>
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
        style={{
          marginTop: 64,
          padding: '32px 40px',
          background: 'transparent',
          minHeight: 'calc(100vh - 64px)',
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
