/**
 * Story 17.12: FeatureToggle component tests.
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FeatureToggle } from './FeatureToggle';

vi.mock('../contexts/FeatureFlagContext', () => ({
  useFeatureFlag: vi.fn(),
}));

import { useFeatureFlag } from '../contexts/FeatureFlagContext';

describe('FeatureToggle', () => {
  it('renders "on" branch when flag is enabled', () => {
    vi.mocked(useFeatureFlag).mockReturnValue(true);

    render(
      <FeatureToggle
        flag="dark_mode"
        on={<div>Dark Theme</div>}
        off={<div>Light Theme</div>}
      />,
    );

    expect(screen.getByText('Dark Theme')).toBeTruthy();
    expect(screen.queryByText('Light Theme')).toBeNull();
  });

  it('renders "off" branch when flag is disabled', () => {
    vi.mocked(useFeatureFlag).mockReturnValue(false);

    render(
      <FeatureToggle
        flag="dark_mode"
        on={<div>Dark Theme</div>}
        off={<div>Light Theme</div>}
      />,
    );

    expect(screen.getByText('Light Theme')).toBeTruthy();
    expect(screen.queryByText('Dark Theme')).toBeNull();
  });

  it('passes correct flag key to useFeatureFlag', () => {
    vi.mocked(useFeatureFlag).mockReturnValue(false);

    render(
      <FeatureToggle flag="ab_test" on={<span />} off={<span />} />,
    );

    expect(useFeatureFlag).toHaveBeenCalledWith('ab_test');
  });
});
