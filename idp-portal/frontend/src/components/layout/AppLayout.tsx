import { Layout, Spin } from 'antd';
import { Suspense } from 'react';
import { Outlet } from 'react-router';
import { TopNav } from './TopNav';

const { Header, Content } = Layout;

export function AppLayout() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 100,
          height: 56,
          lineHeight: '56px',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          background: '#FFFFFF',
          borderBottom: '1px solid #E5E7EB',
        }}
      >
        <TopNav />
      </Header>
      <Content
        style={{
          marginTop: 56,
          padding: 48,
          background: '#FAFBFC',
          minHeight: 'calc(100vh - 56px)',
        }}
      >
        <Suspense fallback={<Spin size="large" style={{ display: 'block', margin: '100px auto' }} />}>
          <Outlet />
        </Suspense>
      </Content>
    </Layout>
  );
}
