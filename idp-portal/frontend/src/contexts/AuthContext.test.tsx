import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AuthProvider, useAuth } from './AuthContext';

// Helper component to expose AuthContext values
function AuthDisplay() {
  const { user, isAuthenticated, isLoading, login, logout, isBusinessProfile } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="authenticated">{String(isAuthenticated)}</span>
      <span data-testid="username">{user?.username ?? 'none'}</span>
      <span data-testid="is-business-profile">{String(isBusinessProfile)}</span>
      <button data-testid="login" onClick={login}>Login</button>
      <button data-testid="logout" onClick={logout}>Logout</button>
    </div>
  );
}

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // Default: refresh fails (no session)
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });
  });

  it('renders children', async () => {
    render(
      <AuthProvider>
        <span>child</span>
      </AuthProvider>
    );
    expect(screen.getByText('child')).toBeTruthy();
  });

  it('starts in loading state and resolves', async () => {
    render(
      <AuthProvider>
        <AuthDisplay />
      </AuthProvider>
    );
    // Initially loading, then resolves
    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false');
    });
    expect(screen.getByTestId('authenticated').textContent).toBe('false');
    expect(screen.getByTestId('username').textContent).toBe('none');
  });

  it('login redirects to SAML login URL', async () => {
    const user = userEvent.setup();
    // Mock location.href setter
    const hrefSetter = vi.fn();
    Object.defineProperty(window, 'location', {
      value: { ...window.location, href: '', hash: '' },
      writable: true,
    });
    Object.defineProperty(window.location, 'href', {
      set: hrefSetter,
      get: () => '',
    });

    render(
      <AuthProvider>
        <AuthDisplay />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false');
    });

    await user.click(screen.getByTestId('login'));
    expect(hrefSetter).toHaveBeenCalledWith('/api/v1/auth/saml/login');
  });

  it('restores session from refresh token on mount', async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: { access_token: 'new-access-token', token_type: 'bearer' } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: { id: 1, username: 'marc', display_name: 'Marc D.', profile: 'dbops' } }),
      });

    render(
      <AuthProvider>
        <AuthDisplay />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false');
    });

    expect(screen.getByTestId('authenticated').textContent).toBe('true');
    expect(screen.getByTestId('username').textContent).toBe('marc');
  });

  it('logout clears state', async () => {
    const user = userEvent.setup();
    const hrefSetter = vi.fn();
    Object.defineProperty(window, 'location', {
      value: { ...window.location, href: '', hash: '', pathname: '/' },
      writable: true,
    });
    Object.defineProperty(window.location, 'href', {
      set: hrefSetter,
      get: () => '',
    });

    // Restore session first
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: { access_token: 'token', token_type: 'bearer' } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: { id: 1, username: 'marc', display_name: 'Marc D.', profile: 'dbops' } }),
      })
      // logout call
      .mockResolvedValueOnce({ ok: true, json: async () => ({ data: { message: 'ok' } }) });

    render(
      <AuthProvider>
        <AuthDisplay />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('authenticated').textContent).toBe('true');
    });

    await user.click(screen.getByTestId('logout'));

    await waitFor(() => {
      expect(hrefSetter).toHaveBeenCalledWith('/login');
    });
  });

  // Story 7.1: isBusinessProfile tests
  describe('isBusinessProfile (Story 7.1)', () => {
    it('returns false when user is not authenticated', async () => {
      render(
        <AuthProvider>
          <AuthDisplay />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('loading').textContent).toBe('false');
      });

      expect(screen.getByTestId('is-business-profile').textContent).toBe('false');
    });

    it('returns true when user has client_business profile', async () => {
      globalThis.fetch = vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: { access_token: 'token', token_type: 'bearer' } }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            data: {
              id: 1,
              username: 'fatima',
              display_name: 'Fatima B.',
              profile: 'client_business',
              navigation_tabs: ['catalog', 'executions', 'dashboard'],
            },
          }),
        });

      render(
        <AuthProvider>
          <AuthDisplay />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('authenticated').textContent).toBe('true');
      });

      expect(screen.getByTestId('is-business-profile').textContent).toBe('true');
    });

    it('returns false when user has dbops profile', async () => {
      globalThis.fetch = vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: { access_token: 'token', token_type: 'bearer' } }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            data: {
              id: 1,
              username: 'karim',
              display_name: 'Karim DBA',
              profile: 'dbops',
              navigation_tabs: ['catalog', 'executions', 'dashboard', 'admin'],
            },
          }),
        });

      render(
        <AuthProvider>
          <AuthDisplay />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('authenticated').textContent).toBe('true');
      });

      expect(screen.getByTestId('is-business-profile').textContent).toBe('false');
    });

    it('uses backend-provided is_business_profile flag when available', async () => {
      globalThis.fetch = vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: { access_token: 'token', token_type: 'bearer' } }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            data: {
              id: 1,
              username: 'test',
              display_name: 'Test User',
              profile: 'dba_applicatif', // Not in BUSINESS_PROFILES
              is_business_profile: true, // But backend says it's business
              navigation_tabs: ['catalog', 'executions', 'dashboard'],
            },
          }),
        });

      render(
        <AuthProvider>
          <AuthDisplay />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('authenticated').textContent).toBe('true');
      });

      // Should trust backend flag over local profile check
      expect(screen.getByTestId('is-business-profile').textContent).toBe('true');
    });
  });
});
