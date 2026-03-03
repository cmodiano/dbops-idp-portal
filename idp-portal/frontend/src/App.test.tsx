import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { App } from './App';

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
    })
    // Catch-all: any unexpected fetch call returns a safe 204 to avoid silent undefined returns
    .mockResolvedValue({ ok: true, status: 204, json: async () => ({}) });
}

describe('App routing', () => {
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
    // Default: no session
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });
  });

  it('redirects to /login when not authenticated', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/connexion|login|SSO/i)).toBeInTheDocument();
    });
  });

  it('renders Catalogue when authenticated on /catalog', async () => {
    mockAuthSession('dbops', ['catalog', 'executions', 'dashboard', 'admin']);

    // Navigate to /catalog
    window.history.pushState({}, '', '/catalog');
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Catalogue')).toBeInTheDocument();
    });
  });

  it('renders NotFoundPage on unknown route', async () => {
    window.history.pushState({}, '', '/unknown-route-xyz');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText('404')).toBeInTheDocument();
    });
  });

  it('AdminGuard redirects DBA user from /admin to /catalog', async () => {
    // DBA user: no 'admin' tab in navigation_tabs
    mockAuthSession('dba_applicatif', ['catalog', 'executions', 'dashboard']);

    window.history.pushState({}, '', '/admin');
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Catalogue')).toBeInTheDocument();
    });
    // Should have been redirected away from /admin — no Admin tab visible
    expect(screen.queryByText('Admin')).not.toBeInTheDocument();
  });

  // Story 56.3: AnalyticsGuard uses hasTab('dashboard') instead of profile === 'dbops'
  it('AnalyticsGuard allows access to /analytics when user has dashboard in navigation_tabs (AC1)', async () => {
    // User with 'dashboard' in navigation_tabs can access /analytics
    mockAuthSession('dbops', ['catalog', 'executions', 'dashboard', 'admin']);

    window.history.pushState({}, '', '/analytics');
    render(<App />);

    await waitFor(() => {
      // Guard must NOT redirect: URL stays at /analytics (not /executions or /catalog)
      expect(window.location.pathname).toBe('/analytics');
      // Confirm no redirection to catalog or executions occurred
      expect(screen.queryByText('Catalogue')).not.toBeInTheDocument();
    });
  });

  // Story 56.3 AC3: access is based on navigation_tabs, NOT on profile name
  it('AnalyticsGuard allows access to /analytics for non-DBOPS profile if dashboard is in navigation_tabs (AC3)', async () => {
    // A non-DBOPS profile that has 'dashboard' in navigation_tabs must be granted access
    // This validates that profile name is irrelevant — only hasTab('dashboard') matters
    mockAuthSession('dba_applicatif', ['catalog', 'executions', 'dashboard']);

    window.history.pushState({}, '', '/analytics');
    render(<App />);

    await waitFor(() => {
      // Guard must NOT redirect: URL stays at /analytics
      expect(window.location.pathname).toBe('/analytics');
      expect(screen.queryByText('Catalogue')).not.toBeInTheDocument();
    });
  });

  it('AnalyticsGuard redirects to /executions when user lacks dashboard in navigation_tabs (AC2)', async () => {
    // User without 'dashboard' in navigation_tabs is redirected from /analytics
    mockAuthSession('dba_applicatif', ['catalog', 'executions', 'calendar']);

    window.history.pushState({}, '', '/analytics');
    render(<App />);

    await waitFor(() => {
      // Should be redirected to /executions page
      expect(screen.getByText(/exécutions|executions/i)).toBeInTheDocument();
    });
  });
});
