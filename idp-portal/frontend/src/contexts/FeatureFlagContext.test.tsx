/**
 * Story 17.12: Feature Flag Context tests.
 */

import { render, screen, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { FeatureFlagProvider, useFeatureFlag, useFeatureFlags, useFeatureFlagContext } from './FeatureFlagContext';
import { AuthProvider } from './AuthContext';

// Mock the feature flag service
vi.mock('../services/feature_flag_service', () => ({
  fetchFeatureFlagsStatus: vi.fn(),
}));

// Mock the auth service to prevent real auth calls
vi.mock('../services/auth_service', () => ({
  refreshAccessToken: vi.fn().mockResolvedValue(null),
  fetchCurrentUser: vi.fn(),
  logoutApi: vi.fn(),
}));

// Mock logger to silence test output
vi.mock('../services/logger', () => ({
  default: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock api_client to prevent token accessor issues
vi.mock('../services/api_client', () => ({
  setAuthAccessors: vi.fn(),
  apiFetch: vi.fn(),
  apiFetchRaw: vi.fn(),
}));

import { fetchFeatureFlagsStatus } from '../services/feature_flag_service';

function FlagDisplay({ flagKey }: { flagKey: string }) {
  const isEnabled = useFeatureFlag(flagKey);
  return <span data-testid={`flag-${flagKey}`}>{String(isEnabled)}</span>;
}

function AllFlagsDisplay() {
  const flags = useFeatureFlags();
  return (
    <span data-testid="all-flags">{JSON.stringify(flags)}</span>
  );
}

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <AuthProvider>
      <FeatureFlagProvider>
        {ui}
      </FeatureFlagProvider>
    </AuthProvider>
  );
}

describe('FeatureFlagContext', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // Default: no auth session (refresh fails)
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });
    vi.mocked(fetchFeatureFlagsStatus).mockResolvedValue({});
  });

  it('renders children', () => {
    renderWithProviders(<span>child</span>);
    expect(screen.getByText('child')).toBeTruthy();
  });

  it('returns false for unknown flag', async () => {
    renderWithProviders(<FlagDisplay flagKey="nonexistent" />);
    await waitFor(() => {
      expect(screen.getByTestId('flag-nonexistent').textContent).toBe('false');
    });
  });

  it('returns empty flags when not authenticated', async () => {
    renderWithProviders(<AllFlagsDisplay />);
    await waitFor(() => {
      expect(screen.getByTestId('all-flags').textContent).toBe('{}');
    });
  });
});

describe('FeatureFlagProvider with mocked flags', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });
  });

  it('returns false for all flags when user is not authenticated (service not called)', async () => {
    vi.mocked(fetchFeatureFlagsStatus).mockResolvedValue({
      new_ui: true,
      dark_mode: false,
    });

    render(
      <AuthProvider>
        <FeatureFlagProvider>
          <FlagDisplay flagKey="new_ui" />
          <FlagDisplay flagKey="dark_mode" />
        </FeatureFlagProvider>
      </AuthProvider>
    );

    // User is not authenticated → fetchFeatureFlagsStatus is NOT called → flags stay empty
    await waitFor(() => {
      expect(screen.getByTestId('flag-new_ui').textContent).toBe('false');
      expect(screen.getByTestId('flag-dark_mode').textContent).toBe('false');
    });
  });
});

describe('useFeatureFlag hook', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });
    vi.mocked(fetchFeatureFlagsStatus).mockResolvedValue({});
  });

  it('returns false for disabled flag', async () => {
    renderWithProviders(<FlagDisplay flagKey="disabled_flag" />);
    await waitFor(() => {
      expect(screen.getByTestId('flag-disabled_flag').textContent).toBe('false');
    });
  });
});

describe('useFeatureFlags hook', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });
    vi.mocked(fetchFeatureFlagsStatus).mockResolvedValue({});
  });

  it('returns all flags as record', async () => {
    renderWithProviders(<AllFlagsDisplay />);
    await waitFor(() => {
      const content = screen.getByTestId('all-flags').textContent;
      expect(content).toBeTruthy();
      const parsed = JSON.parse(content!);
      expect(typeof parsed).toBe('object');
    });
  });
});

// ============================================================================
// useFeatureFlagContext hook
// ============================================================================

function ContextDisplay() {
  const { flags, isEnabled, isLoading } = useFeatureFlagContext();
  return (
    <span data-testid="ctx">
      {JSON.stringify({ flagCount: Object.keys(flags).length, isLoading, isEnabledFn: typeof isEnabled })}
    </span>
  );
}

describe('useFeatureFlagContext hook', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });
    vi.mocked(fetchFeatureFlagsStatus).mockResolvedValue({});
  });

  it('exposes flags, isEnabled function and isLoading', async () => {
    renderWithProviders(<ContextDisplay />);
    await waitFor(() => {
      const raw = screen.getByTestId('ctx').textContent;
      const parsed = JSON.parse(raw!);
      expect(parsed.isEnabledFn).toBe('function');
      expect(typeof parsed.isLoading).toBe('boolean');
      expect(typeof parsed.flagCount).toBe('number');
    });
  });
});

// ============================================================================
// Story 20.7 Task 5: Auto-refresh timer tests
// ============================================================================

// To test auto-refresh, we need isAuthenticated=true.
// We mock useAuth to control authentication state directly.
import * as AuthContextModule from './AuthContext';

/**
 * Render with a mocked authenticated context.
 * Wraps FeatureFlagProvider without AuthProvider, mocking useAuth instead.
 */
function renderAuthenticated(ui: React.ReactElement) {
  return render(
    <FeatureFlagProvider>
      {ui}
    </FeatureFlagProvider>
  );
}

describe('FeatureFlagProvider auto-refresh', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(fetchFeatureFlagsStatus).mockResolvedValue({ test_flag: true });
    // Mock useAuth to return authenticated state
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: { id: 1, username: 'test_user', display_name: 'Test', profile: 'dbops', navigation_tabs: ['catalog'], is_auditor: false },
      accessToken: 'mock-token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      loginWithCredentials: vi.fn(),
      logout: vi.fn().mockResolvedValue(undefined),
      refreshToken: vi.fn().mockResolvedValue('mock-token'),
      hasTab: vi.fn().mockReturnValue(true),
      isBusinessProfile: false,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('fetches flags again after 5 minutes', async () => {
    const fetchMock = vi.mocked(fetchFeatureFlagsStatus);

    await act(async () => {
      renderAuthenticated(<FlagDisplay flagKey="test_flag" />);
    });

    // Let initial effects settle
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    const initialCallCount = fetchMock.mock.calls.length;
    expect(initialCallCount).toBeGreaterThanOrEqual(1); // Initial fetch happened

    // Advance 5 minutes (300000ms = REFRESH_INTERVAL_MS)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300_000);
    });

    // Should have at least one more call from the interval
    expect(fetchMock.mock.calls.length).toBeGreaterThan(initialCallCount);
  });

  it('cleans up interval on unmount', async () => {
    const fetchMock = vi.mocked(fetchFeatureFlagsStatus);

    let unmount: () => void;
    await act(async () => {
      const result = renderAuthenticated(<FlagDisplay flagKey="test_flag" />);
      unmount = result.unmount;
    });

    // Let initial effects settle
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    const callCountBeforeUnmount = fetchMock.mock.calls.length;

    // Unmount the component
    await act(async () => {
      unmount!();
    });

    // Advance 5 minutes - should NOT trigger additional calls
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300_000);
    });

    expect(fetchMock.mock.calls.length).toBe(callCountBeforeUnmount);
  });

  it('does not set interval when not authenticated', async () => {
    // Override: not authenticated
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      loginWithCredentials: vi.fn(),
      logout: vi.fn().mockResolvedValue(undefined),
      refreshToken: vi.fn().mockResolvedValue(null),
      hasTab: vi.fn().mockReturnValue(false),
      isBusinessProfile: false,
    });
    const fetchMock = vi.mocked(fetchFeatureFlagsStatus);

    await act(async () => {
      renderAuthenticated(<FlagDisplay flagKey="test_flag" />);
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    const callCountAfterInit = fetchMock.mock.calls.length;

    // Advance 5 minutes
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300_000);
    });

    // No additional calls since not authenticated
    expect(fetchMock.mock.calls.length).toBe(callCountAfterInit);
  });
});
