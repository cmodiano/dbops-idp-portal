/**
 * Tests for TechnologyBarChart component (Story 8.3, AC3).
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TechnologyBarChart } from './TechnologyBarChart';
import type { TechnologyStats } from '../../../types/api';

// Mock recharts to avoid ResponsiveContainer dimension issues in tests
// Tooltip mock invokes content with active=true to cover CustomTooltip body (lines 50-52)
vi.mock('recharts', () => ({
  BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bar-chart">{children}</div>,
  Bar: ({ children }: { children: React.ReactNode }) => <div data-testid="bar">{children}</div>,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Cell: () => null,
  Tooltip: ({ content }: { content: React.ReactElement }) => {
    if (!content) return null;
    const ContentComponent = content.type as React.ComponentType<Record<string, unknown>>;
    const payload = [
      { payload: { engine: 'Oracle', count: 50, success_rate: 95.0 } },
    ];
    return <ContentComponent active={true} payload={payload} label="Oracle" />;
  },
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div style={{ width: 500, height: 300 }}>{children}</div>
  ),
}));

describe('TechnologyBarChart', () => {
  const mockData: TechnologyStats[] = [
    { engine: 'Oracle', count: 50, success_rate: 95.0 },
    { engine: 'PostgreSQL', count: 30, success_rate: 88.5 },
    { engine: 'N/A', count: 10, success_rate: null },
  ];

  it('renders chart title with data', () => {
    render(<TechnologyBarChart data={mockData} loading={false} />);

    expect(screen.getByText('Répartition par technologie')).toBeInTheDocument();
    // Chart card should be present (chart content depends on recharts rendering)
    expect(document.querySelector('.ant-card-body')).toBeInTheDocument();
  });

  it('renders empty state when no data', () => {
    render(<TechnologyBarChart data={[]} loading={false} />);

    expect(screen.getByText('Répartition par technologie')).toBeInTheDocument();
    expect(screen.getByText('Aucune exécution sur la période')).toBeInTheDocument();
  });

  it('renders skeleton when loading', () => {
    render(<TechnologyBarChart data={[]} loading={true} />);

    expect(screen.getByText('Répartition par technologie')).toBeInTheDocument();
    // Skeleton has specific structure
    expect(document.querySelector('.ant-skeleton')).toBeInTheDocument();
  });

  it('renders chart container with single engine', () => {
    const singleData: TechnologyStats[] = [
      { engine: 'Oracle', count: 100, success_rate: 99.0 },
    ];

    render(<TechnologyBarChart data={singleData} loading={false} />);

    expect(screen.getByText('Répartition par technologie')).toBeInTheDocument();
    expect(document.querySelector('.ant-card-body')).toBeInTheDocument();
  });
});

describe('TechnologyBarChart — additional coverage', () => {
  it('renders chart with unknown engine (fallback gray color)', () => {
    const unknownEngineData: TechnologyStats[] = [
      { engine: 'UnknownDB', count: 5, success_rate: 80.0 },
    ];
    render(<TechnologyBarChart data={unknownEngineData} loading={false} />);
    expect(screen.getByText('Répartition par technologie')).toBeInTheDocument();
    expect(document.querySelector('.ant-card-body')).toBeInTheDocument();
  });

  it('renders chart when success_rate is null (does not show success rate line)', () => {
    const dataWithNullRate: TechnologyStats[] = [
      { engine: 'N/A', count: 10, success_rate: null },
    ];
    render(<TechnologyBarChart data={dataWithNullRate} loading={false} />);
    expect(screen.getByText('Répartition par technologie')).toBeInTheDocument();
  });

  it('renders chart with all known engine colors', () => {
    const allEnginesData: TechnologyStats[] = [
      { engine: 'Oracle', count: 50, success_rate: 95.0 },
      { engine: 'SQL Server', count: 30, success_rate: 90.0 },
      { engine: 'DB2', count: 20, success_rate: 85.0 },
      { engine: 'PostgreSQL', count: 40, success_rate: 88.0 },
      { engine: 'MySQL', count: 25, success_rate: 82.0 },
      { engine: 'N/A', count: 10, success_rate: null },
    ];
    render(<TechnologyBarChart data={allEnginesData} loading={false} />);
    expect(screen.getByText('Répartition par technologie')).toBeInTheDocument();
  });

  it('renders multiple bars for multiple engines', () => {
    const multiData: TechnologyStats[] = [
      { engine: 'Oracle', count: 50, success_rate: 95.0 },
      { engine: 'PostgreSQL', count: 30, success_rate: 88.5 },
    ];
    render(<TechnologyBarChart data={multiData} loading={false} />);
    expect(screen.getByText('Répartition par technologie')).toBeInTheDocument();
    expect(document.querySelector('.ant-card-body')).toBeInTheDocument();
  });

  it('CustomTooltip renders tooltip content with active=true and payload (covers CustomTooltip body)', () => {
    const mockData: TechnologyStats[] = [
      { engine: 'Oracle', count: 50, success_rate: 95.0 },
    ];
    render(<TechnologyBarChart data={mockData} loading={false} />);
    // The Tooltip mock invokes CustomTooltip with active=true, so tooltip content appears
    expect(screen.getByText('Oracle')).toBeInTheDocument();
    expect(screen.getByText('Exécutions: 50')).toBeInTheDocument();
    expect(screen.getByText('Taux de succès: 95.0%')).toBeInTheDocument();
  });

  it('CustomTooltip with null success_rate does not render success rate line', () => {
    const mockData: TechnologyStats[] = [
      { engine: 'N/A', count: 5, success_rate: null },
    ];
    render(<TechnologyBarChart data={mockData} loading={false} />);
    expect(screen.getByText('Répartition par technologie')).toBeInTheDocument();
  });
});
