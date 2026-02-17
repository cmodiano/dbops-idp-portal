import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AuthProvider, useAuth } from './AuthContext';
import * as authService from '../services/auth_service';
import logger from '../services/logger';

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
    expect(hrefSetter).toHaveBeenCalledWith('/api/v1/auth/saml/login/');
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

  // Story 22.3: Token refresh mutex tests (CRIT-3 fix)
  describe('Token refresh mutex (Story 22.3 — CRIT-3)', () => {
    // Helper to capture refreshToken from AuthContext
    let capturedRefreshToken: (() => Promise<string | null>) | null = null;

    function RefreshCapture() {
      const { refreshToken, isLoading } = useAuth();
      capturedRefreshToken = refreshToken;
      return <span data-testid="mutex-loading">{String(isLoading)}</span>;
    }

    beforeEach(() => {
      capturedRefreshToken = null;
    });

    /** Render AuthProvider, wait for mount refresh to complete, clear mock, return mock. */
    async function renderAndWaitForMount(mockRefresh: ReturnType<typeof vi.fn>) {
      vi.spyOn(authService, 'fetchCurrentUser').mockResolvedValue(null);

      render(
        <AuthProvider>
          <RefreshCapture />
        </AuthProvider>
      );

      // Wait for loading to finish (mount refresh completed)
      await waitFor(() => {
        expect(screen.getByTestId('mutex-loading').textContent).toBe('false');
      });

      // Clear call counts from mount
      mockRefresh.mockClear();
    }

    it('should call refreshAccessToken only once for concurrent refresh attempts', async () => {
      const mockRefresh = vi.spyOn(authService, 'refreshAccessToken')
        .mockResolvedValue('mount-token');

      await renderAndWaitForMount(mockRefresh);

      // Setup for concurrent test
      mockRefresh.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve('concurrent-token'), 20);
      }));

      // Trigger 3 concurrent refreshes
      let results: (string | null)[] = [];
      await act(async () => {
        results = await Promise.all([
          capturedRefreshToken!(),
          capturedRefreshToken!(),
          capturedRefreshToken!(),
        ]);
      });

      expect(mockRefresh).toHaveBeenCalledTimes(1);
      expect(results[0]).toBe('concurrent-token');
      expect(results[1]).toBe('concurrent-token');
      expect(results[2]).toBe('concurrent-token');
    });

    it('should wait for in-progress refresh instead of starting a new one', async () => {
      const mockRefresh = vi.spyOn(authService, 'refreshAccessToken')
        .mockResolvedValue('mount-token');

      await renderAndWaitForMount(mockRefresh);

      // Set up a controlled promise
      let resolveRefresh!: (token: string | null) => void;
      mockRefresh.mockImplementation(() => new Promise((resolve) => {
        resolveRefresh = resolve;
      }));

      // Trigger two concurrent refreshes
      let promise1: Promise<string | null>;
      let promise2: Promise<string | null>;
      act(() => {
        promise1 = capturedRefreshToken!();
        promise2 = capturedRefreshToken!();
      });

      // Only one call should have been made
      expect(mockRefresh).toHaveBeenCalledTimes(1);

      // Resolve it
      resolveRefresh('waited-token');

      const [result1, result2] = await act(async () =>
        Promise.all([promise1!, promise2!])
      );

      expect(result1).toBe('waited-token');
      expect(result2).toBe('waited-token');
    });

    it('should return null for all concurrent requests if refresh fails', async () => {
      const mockRefresh = vi.spyOn(authService, 'refreshAccessToken')
        .mockResolvedValue('mount-token');

      await renderAndWaitForMount(mockRefresh);

      // Setup: next refresh rejects
      mockRefresh.mockImplementation(() => new Promise((_, reject) => {
        setTimeout(() => reject(new Error('Refresh error')), 10);
      }));

      let results: (string | null)[] = [];
      await act(async () => {
        results = await Promise.all([
          capturedRefreshToken!(),
          capturedRefreshToken!(),
          capturedRefreshToken!(),
        ]);
      });

      expect(mockRefresh).toHaveBeenCalledTimes(1);
      expect(results[0]).toBeNull();
      expect(results[1]).toBeNull();
      expect(results[2]).toBeNull();
    });

    it('should reset mutex after successful refresh to allow new refreshes', async () => {
      const mockRefresh = vi.spyOn(authService, 'refreshAccessToken')
        .mockResolvedValue('mount-token');

      await renderAndWaitForMount(mockRefresh);

      // First refresh
      mockRefresh.mockResolvedValueOnce('token-1');
      let result1: string | null = null;
      await act(async () => {
        result1 = await capturedRefreshToken!();
      });
      expect(result1).toBe('token-1');

      // Second refresh — should create a NEW promise (mutex was reset)
      mockRefresh.mockResolvedValueOnce('token-2');
      let result2: string | null = null;
      await act(async () => {
        result2 = await capturedRefreshToken!();
      });
      expect(result2).toBe('token-2');

      // Two separate calls to refreshAccessToken
      expect(mockRefresh).toHaveBeenCalledTimes(2);
    });

    it('should reset mutex after failed refresh to allow new refreshes', async () => {
      const mockRefresh = vi.spyOn(authService, 'refreshAccessToken')
        .mockResolvedValue('mount-token');

      await renderAndWaitForMount(mockRefresh);

      // First refresh fails
      mockRefresh.mockRejectedValueOnce(new Error('Fail 1'));
      let result1: string | null = null;
      await act(async () => {
        result1 = await capturedRefreshToken!();
      });
      expect(result1).toBeNull();

      // Second refresh succeeds — mutex was reset after failure
      mockRefresh.mockResolvedValueOnce('token-after-fail');
      let result2: string | null = null;
      await act(async () => {
        result2 = await capturedRefreshToken!();
      });
      expect(result2).toBe('token-after-fail');

      expect(mockRefresh).toHaveBeenCalledTimes(2);
    });

    it('should log refresh attempts with structured logging', async () => {
      const debugSpy = vi.spyOn(logger, 'debug');
      const infoSpy = vi.spyOn(logger, 'info');
      const mockRefresh = vi.spyOn(authService, 'refreshAccessToken')
        .mockResolvedValue('mount-token');

      await renderAndWaitForMount(mockRefresh);

      // Mount triggered logging
      expect(debugSpy).toHaveBeenCalledWith('Starting token refresh', expect.objectContaining({ correlation_id: expect.any(String) }));
      expect(infoSpy).toHaveBeenCalledWith('Token refresh completed', expect.objectContaining({ success: true, correlation_id: expect.any(String) }));

      // Reset spies and mock for a concurrent test
      debugSpy.mockClear();
      infoSpy.mockClear();
      mockRefresh.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve('new-token'), 20);
      }));

      // Trigger two concurrent refreshes
      await act(async () => {
        await Promise.all([
          capturedRefreshToken!(),
          capturedRefreshToken!(),
        ]);
      });

      // First call: "Starting token refresh", second: "already in progress"
      expect(debugSpy).toHaveBeenCalledWith('Starting token refresh', expect.objectContaining({ correlation_id: expect.any(String) }));
      expect(debugSpy).toHaveBeenCalledWith('Token refresh already in progress, waiting for existing promise', expect.objectContaining({ correlation_id: expect.any(String) }));
      expect(infoSpy).toHaveBeenCalledWith('Token refresh completed', expect.objectContaining({ success: true, correlation_id: expect.any(String) }));
    });

    it('should integrate correctly with api_client retry logic on 401', async () => {
      const mockRefresh = vi.spyOn(authService, 'refreshAccessToken')
        .mockResolvedValue('mount-token');

      await renderAndWaitForMount(mockRefresh);

      // Setup: Mock fetch to return 401, then succeed on retry with new token
      let fetchCallCount = 0;
      globalThis.fetch = vi.fn().mockImplementation(() => {
        fetchCallCount++;
        // First call: 401 Unauthorized
        if (fetchCallCount === 1) {
          return Promise.resolve({ ok: false, status: 401, headers: new Headers() });
        }
        // After refresh: 200 OK
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ data: { message: 'success' } }),
          headers: new Headers({ 'content-type': 'application/json' }),
        });
      });

      // Mock refresh to return new token
      mockRefresh.mockResolvedValueOnce('refreshed-token');

      // Import and test apiFetch (simulates real usage)
      const { apiFetch } = await import('../services/api_client');

      // Trigger apiFetch - should hit 401, refresh token, retry
      let result: unknown;
      await act(async () => {
        result = await apiFetch('/test-endpoint');
      });

      // Verify: refreshAccessToken called once despite 401 retry
      expect(mockRefresh).toHaveBeenCalledTimes(1);
      // Verify: fetch called twice (initial 401 + retry after refresh)
      expect(fetchCallCount).toBe(2);
      expect(result).toEqual({ message: 'success' });
    });

    it('should call refresh only once when multiple concurrent API requests receive 401', async () => {
      const mockRefresh = vi.spyOn(authService, 'refreshAccessToken')
        .mockResolvedValue('mount-token');

      await renderAndWaitForMount(mockRefresh);

      // Setup: Mock fetch to return 401 for all initial requests, then succeed on retry
      const fetchCallMap = new Map<string, number>();
      globalThis.fetch = vi.fn().mockImplementation((url: string) => {
        const callCount = (fetchCallMap.get(url) || 0) + 1;
        fetchCallMap.set(url, callCount);

        // First call to each endpoint: 401
        if (callCount === 1) {
          return Promise.resolve({ ok: false, status: 401, headers: new Headers() });
        }

        // Retry after refresh: 200 OK
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ data: { endpoint: url, call: callCount } }),
          headers: new Headers({ 'content-type': 'application/json' }),
        });
      });

      // Mock refresh to return new token (with delay to ensure concurrency)
      mockRefresh.mockImplementation(() => new Promise((resolve) => {
        setTimeout(() => resolve('concurrent-refreshed-token'), 20);
      }));

      const { apiFetch } = await import('../services/api_client');

      // Trigger 3 concurrent API calls
      let results: unknown[] = [];
      await act(async () => {
        results = await Promise.all([
          apiFetch('/endpoint-1'),
          apiFetch('/endpoint-2'),
          apiFetch('/endpoint-3'),
        ]);
      });

      // CRITICAL: refreshAccessToken should be called ONLY ONCE despite 3 concurrent 401s
      expect(mockRefresh).toHaveBeenCalledTimes(1);
      // Each endpoint should have been called twice (initial 401 + retry)
      expect(fetchCallMap.get('/api/v1/endpoint-1/')).toBe(2);
      expect(fetchCallMap.get('/api/v1/endpoint-2/')).toBe(2);
      expect(fetchCallMap.get('/api/v1/endpoint-3/')).toBe(2);
      // All requests should succeed after shared refresh
      expect(results).toHaveLength(3);
    });
  });
});
