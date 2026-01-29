import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { ConfigProvider } from 'antd';
import { TopNav } from './TopNav';
import { AuthProvider } from '../../contexts/AuthContext';
import { ThemeProvider } from '../../contexts/ThemeContext';
import { lightTheme } from '../../theme/desjardins';

function mockAuthSession(profile: string, navigationTabs: string[]) {
  global.fetch = vi.fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ data: { access_token: 'token', token_type: 'bearer' } }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        data: {
          id: 1,
          username: 'test.user',
          display_name: 'Test User',
          profile,
          navigation_tabs: navigationTabs,
        },
      }),
    });
}

function renderTopNav(initialPath = '/catalog') {
  const router = createMemoryRouter(
    [
      {
        path: '/',
        element: <TopNav />,
        children: [],
      },
      { path: '/catalog', element: <TopNav /> },
      { path: '/executions', element: <TopNav /> },
      { path: '/dashboard', element: <TopNav /> },
      { path: '/admin', element: <TopNav /> },
    ],
    { initialEntries: [initialPath] },
  );

  return render(
    <ThemeProvider>
      <ConfigProvider theme={lightTheme}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </ConfigProvider>
    </ThemeProvider>,
  );
}

describe('TopNav', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('AC1 — DBOPS Navigation', () => {
    it('DBOPS user sees 4 tabs including Admin', async () => {
      mockAuthSession('dbops', ['catalog', 'executions', 'dashboard', 'admin']);
      renderTopNav();

      await waitFor(() => {
        expect(screen.getByText('Catalogue')).toBeInTheDocument();
      });
      expect(screen.getByText('Exécutions')).toBeInTheDocument();
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
      expect(screen.getByText('Admin')).toBeInTheDocument();
    });
  });

  describe('AC2 — DBA Navigation', () => {
    it('DBA user sees 3 tabs without Admin', async () => {
      mockAuthSession('dba_applicatif', ['catalog', 'executions', 'dashboard']);
      renderTopNav();

      await waitFor(() => {
        expect(screen.getByText('Catalogue')).toBeInTheDocument();
      });
      expect(screen.getByText('Exécutions')).toBeInTheDocument();
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
      expect(screen.queryByText('Admin')).not.toBeInTheDocument();
    });

    it('DBA Infrastructure user also sees 3 tabs', async () => {
      mockAuthSession('dba_infrastructure', ['catalog', 'executions', 'dashboard']);
      renderTopNav();

      await waitFor(() => {
        expect(screen.getByText('Catalogue')).toBeInTheDocument();
      });
      expect(screen.queryByText('Admin')).not.toBeInTheDocument();
    });
  });

  describe('AC3 — Profile Display', () => {
    it('displays user avatar with first letter of display_name', async () => {
      mockAuthSession('dbops', ['catalog', 'executions', 'dashboard', 'admin']);
      renderTopNav();

      await waitFor(() => {
        expect(screen.getByText('T')).toBeInTheDocument(); // "Test User" → "T"
      });
    });

    it('shows profile dropdown on avatar click with name, role, and logout', async () => {
      const user = userEvent.setup();
      mockAuthSession('dbops', ['catalog', 'executions', 'dashboard', 'admin']);
      renderTopNav();

      await waitFor(() => {
        expect(screen.getByText('T')).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText('Menu profil utilisateur'));

      await waitFor(() => {
        // Full name appears in dropdown
        expect(screen.getByText('Test User')).toBeInTheDocument();
        // Logout button with accent
        expect(screen.getByText('Déconnexion')).toBeInTheDocument();
      });
    });
  });

  describe('Navigation', () => {
    it('renders semantic nav element', async () => {
      mockAuthSession('dbops', ['catalog', 'executions', 'dashboard', 'admin']);
      renderTopNav();

      await waitFor(() => {
        const nav = screen.getByLabelText('Navigation principale');
        expect(nav).toBeInTheDocument();
        expect(nav.tagName).toBe('NAV');
      });
    });

    it('renders Portail DBOPS brand', async () => {
      mockAuthSession('dbops', ['catalog', 'executions', 'dashboard', 'admin']);
      renderTopNav();

      await waitFor(() => {
        expect(screen.getByText('DBOPS')).toBeInTheDocument();
      });
    });

    it('no user shows no avatar', async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });
      renderTopNav();
      await waitFor(() => {
        expect(screen.queryByLabelText('Menu profil utilisateur')).not.toBeInTheDocument();
      });
    });
  });

  describe('Theme Toggle (AC #1 Story 2.15)', () => {
    beforeEach(() => {
      localStorage.clear();
      // Mock matchMedia for light system preference
      window.matchMedia = vi.fn().mockImplementation((query: string) => ({
        matches: query.includes('dark') ? false : true,
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }));
    });

    it('renders theme toggle button', async () => {
      mockAuthSession('dbops', ['catalog', 'executions', 'dashboard', 'admin']);
      renderTopNav();

      await waitFor(() => {
        expect(screen.getByLabelText('Activer le theme sombre')).toBeInTheDocument();
      });
    });

    it('toggle button has role="switch" for accessibility (AC #3)', async () => {
      mockAuthSession('dbops', ['catalog', 'executions', 'dashboard', 'admin']);
      renderTopNav();

      await waitFor(() => {
        const toggle = screen.getByRole('switch');
        expect(toggle).toBeInTheDocument();
      });
    });

    it('toggle button changes theme on click (AC #1)', async () => {
      const user = userEvent.setup();
      mockAuthSession('dbops', ['catalog', 'executions', 'dashboard', 'admin']);
      renderTopNav();

      await waitFor(() => {
        expect(screen.getByLabelText('Activer le theme sombre')).toBeInTheDocument();
      });

      // Click to switch to dark mode
      await user.click(screen.getByRole('switch'));

      await waitFor(() => {
        expect(screen.getByLabelText('Activer le theme clair')).toBeInTheDocument();
      });
    });
  });
});
