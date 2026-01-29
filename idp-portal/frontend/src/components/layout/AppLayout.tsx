import { Layout, Spin, theme } from 'antd';
import { Suspense } from 'react';
import { Outlet } from 'react-router';
import { TopNav } from './TopNav';

const { Header, Content } = Layout;

export function AppLayout() {
  // Use Ant Design theme tokens for consistent theming (AC #4, #6)
  const { token } = theme.useToken();

  return (
    <Layout style={{ minHeight: '100vh', background: token.colorBgLayout }}>
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
          background: token.colorBgContainer,
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
          boxShadow: token.boxShadow,
          transition: 'all 0.2s ease',
        }}
      >
        <TopNav />
      </Header>
      <Content
        style={{
          marginTop: 64,
          padding: '32px 40px',
          background: token.colorBgLayout,
          minHeight: 'calc(100vh - 64px)',
          transition: 'background-color 0.2s ease',
        }}
      >
        <Suspense fallback={<Spin size="large" style={{ display: 'block', margin: '100px auto' }} />}>
          <Outlet />
        </Suspense>
      </Content>
    </Layout>
  );
}
