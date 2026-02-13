/**
 * Story 17.12: FeatureGuard component tests.
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FeatureGuard } from './FeatureGuard';

// Mock the context hook
vi.mock('../contexts/FeatureFlagContext', () => ({
  useFeatureFlag: vi.fn(),
}));

import { useFeatureFlag } from '../contexts/FeatureFlagContext';

describe('FeatureGuard', () => {
  it('renders children when flag is enabled', () => {
    vi.mocked(useFeatureFlag).mockReturnValue(true);

    render(
      <FeatureGuard flag="new_ui">
        <div>New UI</div>
      </FeatureGuard>,
    );

    expect(screen.getByText('New UI')).toBeTruthy();
  });

  it('renders fallback when flag is disabled', () => {
    vi.mocked(useFeatureFlag).mockReturnValue(false);

    render(
      <FeatureGuard flag="new_ui" fallback={<div>Old UI</div>}>
        <div>New UI</div>
      </FeatureGuard>,
    );

    expect(screen.queryByText('New UI')).toBeNull();
    expect(screen.getByText('Old UI')).toBeTruthy();
  });

  it('renders nothing when flag is disabled and no fallback', () => {
    vi.mocked(useFeatureFlag).mockReturnValue(false);

    const { container } = render(
      <FeatureGuard flag="new_ui">
        <div>New UI</div>
      </FeatureGuard>,
    );

    expect(screen.queryByText('New UI')).toBeNull();
    expect(container.innerHTML).toBe('');
  });

  it('passes correct flag key to useFeatureFlag', () => {
    vi.mocked(useFeatureFlag).mockReturnValue(false);

    render(
      <FeatureGuard flag="my_special_flag">
        <div>Content</div>
      </FeatureGuard>,
    );

    expect(useFeatureFlag).toHaveBeenCalledWith('my_special_flag');
  });
});
