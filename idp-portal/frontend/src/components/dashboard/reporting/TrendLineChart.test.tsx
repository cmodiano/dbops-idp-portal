/**
 * Tests for TrendLineChart component (Story 8.3, AC5).
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TrendLineChart } from './TrendLineChart';
import type { DashboardTimeSeriesPoint } from '../../../types/api';

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

describe('TrendLineChart', () => {
  const mockData: DashboardTimeSeriesPoint[] = [
    { date: '2026-01-28', success: 10, failed: 2 },
    { date: '2026-01-29', success: 15, failed: 1 },
    { date: '2026-01-30', success: 12, failed: 3 },
  ];

  it('renders chart title with data', () => {
    render(<TrendLineChart data={mockData} loading={false} />);

    expect(screen.getByText('Tendances temporelles')).toBeInTheDocument();
    expect(document.querySelector('.ant-card-body')).toBeInTheDocument();
  });

  it('renders empty state when no data', () => {
    render(<TrendLineChart data={[]} loading={false} />);

    expect(screen.getByText('Tendances temporelles')).toBeInTheDocument();
    expect(screen.getByText('Aucune donnee sur la periode')).toBeInTheDocument();
  });

  it('renders skeleton when loading', () => {
    render(<TrendLineChart data={[]} loading={true} />);

    expect(screen.getByText('Tendances temporelles')).toBeInTheDocument();
    expect(document.querySelector('.ant-skeleton')).toBeInTheDocument();
  });

  it('renders chart container with single data point', () => {
    const singleData: DashboardTimeSeriesPoint[] = [
      { date: '2026-01-30', success: 5, failed: 1 },
    ];

    render(<TrendLineChart data={singleData} loading={false} />);

    expect(screen.getByText('Tendances temporelles')).toBeInTheDocument();
    expect(document.querySelector('.ant-card-body')).toBeInTheDocument();
  });
});
