/**
 * ComparisonModeSelector - Toggle between Stats and Comparison modes.
 * Story 8.6, AC1.
 *
 * Uses Ant Design Segmented for mode selection.
 */

import { Segmented } from 'antd';

export type DashboardMode = 'stats' | 'comparison';

export interface ComparisonModeSelectorProps {
  /** Current mode. */
  mode: DashboardMode;
  /** Callback when mode changes. */
  onModeChange: (mode: DashboardMode) => void;
}

const MODE_OPTIONS = [
  { label: 'Statistiques', value: 'stats' as const },
  { label: 'Comparaison', value: 'comparison' as const },
];

export function ComparisonModeSelector({ mode, onModeChange }: ComparisonModeSelectorProps) {
  return (
    <Segmented
      options={MODE_OPTIONS}
      value={mode}
      onChange={(val) => onModeChange(val as DashboardMode)}
      aria-label="Mode d'affichage du dashboard"
    />
  );
}

export default ComparisonModeSelector;
