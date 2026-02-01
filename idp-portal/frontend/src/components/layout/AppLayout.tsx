import { Layout, Spin } from 'antd';
import { Suspense } from 'react';
import { Outlet } from 'react-router';
import { TopNav } from './TopNav';

const { Header, Content } = Layout;

export function AppLayout() {
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
        <Suspense fallback={<Spin size="large" style={{ display: 'block', margin: '100px auto' }} />}>
          <Outlet />
        </Suspense>
      </Content>
    </Layout>
  );
}
