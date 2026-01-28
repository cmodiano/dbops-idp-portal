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
    });
}

describe('App routing', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
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
});
