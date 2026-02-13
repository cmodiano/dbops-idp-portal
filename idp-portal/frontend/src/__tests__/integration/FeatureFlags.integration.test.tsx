/**
 * Story 20.7 Task 7: Feature Flags integration test.
 *
 * Tests the full flow: API mock → FeatureFlagProvider → FeatureGuard/FeatureToggle components.
 * Validates that flags fetched from the API propagate correctly through context to components.
 */

import { render, screen, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { FeatureFlagProvider } from '../../contexts/FeatureFlagContext';
import { FeatureGuard } from '../../components/FeatureGuard';
import { FeatureToggle } from '../../components/FeatureToggle';
import * as AuthContextModule from '../../contexts/AuthContext';

// Mock the feature flag service
vi.mock('../../services/featureFlagService', () => ({
  fetchFeatureFlagsStatus: vi.fn(),
  fetchFeatureFlags: vi.fn(),
  updateFeatureFlag: vi.fn(),
}));

// Mock logger to silence test output
vi.mock('../../services/logger', () => ({
  default: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock api_client to prevent token accessor issues
vi.mock('../../services/api_client', () => ({
  setAuthAccessors: vi.fn(),
  apiFetch: vi.fn(),
  apiFetchRaw: vi.fn(),
}));

// Mock auth service
vi.mock('../../services/auth_service', () => ({
  refreshAccessToken: vi.fn().mockResolvedValue(null),
  fetchCurrentUser: vi.fn(),
  logoutApi: vi.fn(),
}));

import { fetchFeatureFlagsStatus } from '../../services/featureFlagService';

/** Helper: mock useAuth to return authenticated state. */
function mockAuthenticated() {
  vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
    user: {
      id: 42,
      username: 'integration_user',
      display_name: 'Integration Test User',
      profile: 'dbops',
      navigation_tabs: ['catalog', 'admin'],
      is_auditor: false,
    },
    accessToken: 'integration-test-token',
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
    refreshToken: vi.fn().mockResolvedValue('integration-test-token'),
    hasTab: vi.fn().mockReturnValue(true),
    isBusinessProfile: false,
  });
}

describe('Feature Flags Integration: API → Context → Components', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockAuthenticated();
  });

  it('FeatureGuard renders children when API returns flag enabled', async () => {
    vi.mocked(fetchFeatureFlagsStatus).mockResolvedValue({
      new_workflow_builder: true,
      dark_mode: false,
    });

    await act(async () => {
      render(
        <FeatureFlagProvider>
          <FeatureGuard flag="new_workflow_builder" fallback={<span>old UI</span>}>
            <span>new UI</span>
          </FeatureGuard>
          <FeatureGuard flag="dark_mode" fallback={<span>light mode</span>}>
            <span>dark mode</span>
          </FeatureGuard>
        </FeatureFlagProvider>
      );
    });

    await waitFor(() => {
      // new_workflow_builder is enabled → render children
      expect(screen.getByText('new UI')).toBeTruthy();
      expect(screen.queryByText('old UI')).toBeNull();
      // dark_mode is disabled → render fallback
      expect(screen.getByText('light mode')).toBeTruthy();
      expect(screen.queryByText('dark mode')).toBeNull();
    });
  });

  it('FeatureToggle switches branches based on API flags', async () => {
    vi.mocked(fetchFeatureFlagsStatus).mockResolvedValue({
      experimental_feature: true,
    });

    await act(async () => {
      render(
        <FeatureFlagProvider>
          <FeatureToggle
            flag="experimental_feature"
            on={<span>experiment ON</span>}
            off={<span>experiment OFF</span>}
          />
        </FeatureFlagProvider>
      );
    });

    await waitFor(() => {
      expect(screen.getByText('experiment ON')).toBeTruthy();
      expect(screen.queryByText('experiment OFF')).toBeNull();
    });
  });

  it('handles API error gracefully with empty flags', async () => {
    vi.mocked(fetchFeatureFlagsStatus).mockRejectedValue(new Error('Network error'));

    await act(async () => {
      render(
        <FeatureFlagProvider>
          <FeatureGuard flag="any_flag" fallback={<span>fallback content</span>}>
            <span>guarded content</span>
          </FeatureGuard>
        </FeatureFlagProvider>
      );
    });

    await waitFor(() => {
      // On error, flags are empty → FeatureGuard renders fallback
      expect(screen.getByText('fallback content')).toBeTruthy();
      expect(screen.queryByText('guarded content')).toBeNull();
    });
  });
});
