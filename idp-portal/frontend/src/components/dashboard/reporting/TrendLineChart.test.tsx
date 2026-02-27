/**
 * Tests for TrendLineChart component (Story 8.3, AC5).
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TrendLineChart } from './TrendLineChart';
import type { DashboardTimeSeriesPoint } from '../../../types/api';

// Mock recharts to avoid ResponsiveContainer dimension issues in tests,
// and expose LineChart aria-label + Legend formatter output (Story 46.5)
vi.mock('recharts', async () => {
  const actual = await vi.importActual('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 500, height: 300 }}>{children}</div>
    ),
    LineChart: ({
      children,
      'aria-label': ariaLabel,
    }: {
      children: React.ReactNode;
      'aria-label'?: string;
    }) => <div aria-label={ariaLabel}>{children}</div>,
    Legend: ({
      formatter,
    }: {
      formatter?: (value: string) => string;
    }) => (
      <div>
        <span className="recharts-legend-item-text">{formatter?.('success')}</span>
        <span className="recharts-legend-item-text">{formatter?.('failed')}</span>
      </div>
    ),
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
    Line: () => null,
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

describe('Story 46.5 — Légendes et libellés lisibles', () => {
  const mockData: DashboardTimeSeriesPoint[] = [
    { date: '2026-01-28', success: 10, failed: 2 },
    { date: '2026-01-29', success: 15, failed: 1 },
  ];

  it('aria-label contient les accents corrects : succès et échecs', () => {
    render(<TrendLineChart data={mockData} loading={false} />);

    const chartEl = document.querySelector('[aria-label]');
    expect(chartEl?.getAttribute('aria-label')).toBe(
      'Graphique des exécutions par jour : succès et échecs',
    );
  });

  it('les légendes affichent "Succès" et "Échecs" avec accents', () => {
    render(<TrendLineChart data={mockData} loading={false} />);

    const legendItems = document.querySelectorAll('.recharts-legend-item-text');
    const texts = Array.from(legendItems).map((el) => el.textContent);
    expect(texts).toContain('Succès');
    expect(texts).toContain('Échecs');
  });
});
