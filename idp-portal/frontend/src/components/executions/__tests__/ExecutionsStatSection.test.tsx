/**
 * Tests for ExecutionsStatSection component (Story 26.4 - AC4).
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ExecutionsStatSection } from '../ExecutionsStatSection';
import type { ExecutionsStatSectionProps } from '../ExecutionsStatSection';
import type { DashboardStats } from '../../../types/api';

// Mock StatCard to render props as text
vi.mock('../../dashboard/StatCard', () => ({
  StatCard: ({ label, value, loading, suffix }: { label: string; value: number; loading?: boolean; suffix?: string }) => (
    <div data-testid="stat-card" data-loading={loading}>
      <span data-testid="stat-label">{label}</span>
      <span data-testid="stat-value">{value}{suffix}</span>
    </div>
  ),
}));

// Mock TrendLineChart
vi.mock('../../dashboard/reporting/TrendLineChart', () => ({
  TrendLineChart: ({ loading }: { loading?: boolean }) => (
    <div data-testid="trend-line-chart" data-loading={loading}>TrendLineChart</div>
  ),
}));

// Mock antd icons
vi.mock('@ant-design/icons', () => ({
  RocketOutlined: () => <span>RocketIcon</span>,
  CheckCircleOutlined: () => <span>CheckIcon</span>,
  SyncOutlined: () => <span>SyncIcon</span>,
  ExclamationCircleOutlined: () => <span>ExclamationIcon</span>,
}));

const defaultStats: DashboardStats = {
  executions_jour: 42,
  taux_succes_pct: 95,
  executions_en_cours: 3,
  executions_en_erreur: 2,
};

const defaultProps: ExecutionsStatSectionProps = {
  statsData: defaultStats,
  statsLoading: false,
  timeSeriesData: [],
  timeSeriesLoading: false,
  filters: {},
};

describe('ExecutionsStatSection', () => {
  it('renders 4 StatCards with correct labels', () => {
    render(<ExecutionsStatSection {...defaultProps} />);

    const cards = screen.getAllByTestId('stat-card');
    expect(cards).toHaveLength(4);

    const labels = screen.getAllByTestId('stat-label').map((el) => el.textContent);
    expect(labels).toContain('Exécutions du jour');
    expect(labels).toContain('Taux de succès');
    expect(labels).toContain('En cours');
    expect(labels).toContain('En erreur');
  });

  it('renders TrendLineChart', () => {
    render(<ExecutionsStatSection {...defaultProps} />);

    expect(screen.getByTestId('trend-line-chart')).toBeInTheDocument();
  });

  it('shows loading state when statsLoading=true', () => {
    render(<ExecutionsStatSection {...defaultProps} statsLoading={true} />);

    const cards = screen.getAllByTestId('stat-card');
    cards.forEach((card) => {
      expect(card).toHaveAttribute('data-loading', 'true');
    });
  });

  it('shows "Exécutions" label when date filter is active', () => {
    render(
      <ExecutionsStatSection
        {...defaultProps}
        filters={{ start_date: '2025-01-01' }}
      />,
    );

    const labels = screen.getAllByTestId('stat-label').map((el) => el.textContent);
    expect(labels).toContain('Exécutions');
    expect(labels).not.toContain('Exécutions du jour');
  });

  it('shows "Exécutions du jour" label when no date filter', () => {
    render(<ExecutionsStatSection {...defaultProps} filters={{}} />);

    const labels = screen.getAllByTestId('stat-label').map((el) => el.textContent);
    expect(labels).toContain('Exécutions du jour');
  });
});
