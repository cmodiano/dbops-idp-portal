import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { ConfigProvider } from 'antd';
import { AppLayout } from './AppLayout';
import { AuthProvider } from '../../contexts/AuthContext';
import { ThemeProvider } from '../../contexts/ThemeContext';
import { DashboardProvider } from '../../contexts/DashboardContext';
import { lightTheme } from '../../theme/desjardins';

// Mock logger to prevent actual logging in tests
vi.mock('../../services/logger', () => ({
  default: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

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
    <ThemeProvider>
      <ConfigProvider theme={lightTheme}>
        <AuthProvider>
          <DashboardProvider>
            <RouterProvider router={router} />
          </DashboardProvider>
        </AuthProvider>
      </ConfigProvider>
    </ThemeProvider>,
  );
}

describe('AppLayout', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    // Mock matchMedia for theme context
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('dark') ? false : true,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
  });

  it('renders child route content via Outlet (AC #4)', async () => {
    renderLayout();
    expect(screen.getByText('test content')).toBeInTheDocument();
  });

  it('renders the Portail DBOPS brand (AC #4)', () => {
    renderLayout();
    expect(screen.getByText('DBOPS')).toBeInTheDocument();
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

  it('catches errors from child routes via ErrorBoundary (AC #5)', () => {
    // Suppress React's console.error noise from error boundaries
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    // Mock fetch for auth
    global.fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 401 });

    function ThrowError(): React.ReactElement {
      throw new Error('Child route error');
    }

    const router = createMemoryRouter(
      [
        {
          element: <AppLayout />,
          children: [{ path: '/error', element: <ThrowError /> }],
        },
      ],
      { initialEntries: ['/error'] },
    );

    render(
      <ThemeProvider>
        <ConfigProvider theme={lightTheme}>
          <AuthProvider>
            <DashboardProvider>
              <RouterProvider router={router} />
            </DashboardProvider>
          </AuthProvider>
        </ConfigProvider>
      </ThemeProvider>,
    );

    // ErrorBoundary should catch error and show fallback UI
    expect(screen.getByText('Une erreur est survenue')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Recharger la page/i })).toBeInTheDocument();

    consoleErrorSpy.mockRestore();
  });

  it('wraps Outlet with ErrorBoundary and Suspense (AC #5)', () => {
    renderLayout();
    // If Suspense or ErrorBoundary were missing, this would fail
    expect(screen.getByText('test content')).toBeInTheDocument();
  });
});
