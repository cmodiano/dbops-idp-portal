/**
 * Story 17.12: FeatureGuard component for conditional rendering based on feature flags.
 *
 * Usage:
 *   <FeatureGuard flag="new_workflow_builder" fallback={<OldUI />}>
 *     <NewUI />
 *   </FeatureGuard>
 */

import type { ReactNode } from 'react';
import { useFeatureFlag } from '../contexts/FeatureFlagContext';

interface FeatureGuardProps {
  /** The feature flag key to check. */
  flag: string;
  /** Content to render when the flag is enabled. */
  children: ReactNode;
  /** Optional fallback content when the flag is disabled. Defaults to null. */
  fallback?: ReactNode;
}

export function FeatureGuard({ flag, children, fallback = null }: FeatureGuardProps) {
  const isEnabled = useFeatureFlag(flag);
  return <>{isEnabled ? children : fallback}</>;
}
