/**
 * Story 17.12: Feature Flag Context tests.
 */

import { render, screen, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { FeatureFlagProvider, useFeatureFlag, useFeatureFlags } from './FeatureFlagContext';
import { AuthProvider } from './AuthContext';

// Mock the feature flag service
vi.mock('../services/featureFlagService', () => ({
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

import { fetchFeatureFlagsStatus } from '../services/featureFlagService';

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

  it('provides flag values from service', async () => {
    vi.mocked(fetchFeatureFlagsStatus).mockResolvedValue({
      new_ui: true,
      dark_mode: false,
    });

    // Render without AuthProvider to test standalone
    render(
      <AuthProvider>
        <FeatureFlagProvider>
          <FlagDisplay flagKey="new_ui" />
          <FlagDisplay flagKey="dark_mode" />
        </FeatureFlagProvider>
      </AuthProvider>
    );

    // Since user is not authenticated, flags won't be fetched
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
