import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { ConfigProvider } from 'antd';
import { TopNav } from './TopNav';
import { AuthProvider } from '../../contexts/AuthContext';
import { desjardinsTheme } from '../../theme/desjardins';

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
    <ConfigProvider theme={desjardinsTheme}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </ConfigProvider>,
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
      expect(screen.getByText('Executions')).toBeInTheDocument();
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
      expect(screen.getByText('Executions')).toBeInTheDocument();
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
        expect(screen.getByText('Test User')).toBeInTheDocument();
        expect(screen.getByText('dbops')).toBeInTheDocument();
        expect(screen.getByText('Deconnexion')).toBeInTheDocument();
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

    it('renders IDP Portal brand', async () => {
      mockAuthSession('dbops', ['catalog', 'executions', 'dashboard', 'admin']);
      renderTopNav();

      await waitFor(() => {
        expect(screen.getByText('IDP Portal')).toBeInTheDocument();
      });
    });

    it('no user shows no avatar', () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });
      renderTopNav();
      expect(screen.queryByLabelText('Menu profil utilisateur')).not.toBeInTheDocument();
    });
  });
});
