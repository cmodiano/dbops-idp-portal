/**
 * Story 17.12: FeatureToggle component for A/B testing.
 *
 * Renders one of two branches based on a feature flag.
 *
 * Usage:
 *   <FeatureToggle flag="dark_mode" on={<DarkUI />} off={<LightUI />} />
 */

import type { ReactNode } from 'react';
import { useFeatureFlag } from '../contexts/FeatureFlagContext';

interface FeatureToggleProps {
  /** The feature flag key to check. */
  flag: string;
  /** Content to render when the flag is enabled. */
  on: ReactNode;
  /** Content to render when the flag is disabled. */
  off: ReactNode;
}

export function FeatureToggle({ flag, on, off }: FeatureToggleProps) {
  const isEnabled = useFeatureFlag(flag);
  return <>{isEnabled ? on : off}</>;
}
