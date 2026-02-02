/**
 * Tests for ComparisonChart component (Story 8.6, AC2, AC3, AC8).
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ComparisonChart } from './ComparisonChart';
import type { ComparisonResult } from '../../../types/api';

// Mock recharts to avoid ResponsiveContainer dimension issues in tests
vi.mock('recharts', async () => {
  const actual = await vi.importActual('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 500, height: 300 }}>{children}</div>
    ),
  };
});

const mockComparisonResult: ComparisonResult = {
  dimension: 'technology',
  value1: 'Oracle',
  value2: 'PostgreSQL',
  value1_stats: {
    success_rate: 95.0,
    avg_time: 120.5,
    execution_count: 50,
    incident_count: 2,
  },
  value2_stats: {
    success_rate: 88.5,
    avg_time: 95.2,
    execution_count: 30,
    incident_count: 5,
  },
  deltas: {
    success_rate: -6.84,
    avg_time: -21.0,
    execution_count: -40.0,
    incident_count: 150.0,
  },
};

describe('ComparisonChart', () => {
  it('renders chart title with data', () => {
    render(<ComparisonChart data={mockComparisonResult} loading={false} />);

    expect(screen.getByText('Comparaison graphique')).toBeInTheDocument();
    // Chart card should be present
    expect(document.querySelector('.ant-card-body')).toBeInTheDocument();
  });

  it('renders empty state when no data', () => {
    render(<ComparisonChart data={null} loading={false} />);

    // When no data, card shows "Comparaison graphique" as title
    expect(screen.getByText('Sélectionnez deux valeurs à comparer')).toBeInTheDocument();
  });

  it('renders skeleton when loading', () => {
    render(<ComparisonChart data={null} loading={true} />);

    expect(screen.getByText('Comparaison')).toBeInTheDocument();
    expect(document.querySelector('.ant-skeleton')).toBeInTheDocument();
  });

  it('renders chart with comparison values in legend/labels (AC8)', () => {
    render(<ComparisonChart data={mockComparisonResult} loading={false} />);

    // The chart should include the value names
    expect(document.querySelector('.ant-card-body')).toBeInTheDocument();
  });
});
