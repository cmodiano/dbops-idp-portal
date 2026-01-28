import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { ConfigProvider } from 'antd';
import { AppLayout } from './AppLayout';
import { AuthProvider } from '../../contexts/AuthContext';
import { desjardinsTheme } from '../../theme/desjardins';

function renderLayout(initialPath = '/test') {
  // Mock fetch: refresh fails → no session → renders unauthenticated
  // TopNav handles no user gracefully
  global.fetch = vi.fn()
    .mockResolvedValueOnce({ ok: false, status: 401 })  // refresh fails
    ;

  const router = createMemoryRouter(
    [
      {
        element: <AppLayout />,
        children: [
          { path: '/test', element: <div>test content</div> },
        ],
      },
    ],
    { initialEntries: [initialPath] },
  );

  return render(
    <ConfigProvider theme={desjardinsTheme}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </ConfigProvider>,
  );
}

describe('AppLayout', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders child route content via Outlet (AC #4)', async () => {
    renderLayout();
    expect(screen.getByText('test content')).toBeInTheDocument();
  });

  it('renders the IDP Portal brand (AC #4)', () => {
    renderLayout();
    expect(screen.getByText('IDP Portal')).toBeInTheDocument();
  });

  it('renders semantic nav element with aria-label', () => {
    renderLayout();
    const nav = screen.getByLabelText('Navigation principale');
    expect(nav).toBeInTheDocument();
    expect(nav.tagName).toBe('NAV');
  });

  it('renders main element for content area', () => {
    renderLayout();
    expect(screen.getByRole('main')).toBeInTheDocument();
  });
});
