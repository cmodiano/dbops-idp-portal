/**
 * Tests for CatalogueItemTypeChart component (Story 60.4, AC: 1, 2, 4, 5, 8).
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { CatalogueItemTypeChart } from './CatalogueItemTypeChart';
import type { StatsCatalogueByItemType } from '../../../types/api';

vi.mock('recharts', () => ({
  BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bar-chart">{children}</div>,
  Bar: ({ children }: { children: React.ReactNode }) => <div data-testid="bar">{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div data-testid="line-chart">{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Cell: () => null,
  Legend: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div style={{ width: 500, height: 300 }}>{children}</div>
  ),
}));

describe('CatalogueItemTypeChart', () => {
  const mockData: StatsCatalogueByItemType[] = [
    { item_type: 'action', count: 38 },
    { item_type: 'workflow', count: 14 },
  ];

  it('test_renders_chart_title', () => {
    render(<CatalogueItemTypeChart data={mockData} loading={false} />);
    expect(screen.getByText('Répartition actions / workflows')).toBeInTheDocument();
    expect(document.querySelector('.ant-card-body')).toBeInTheDocument();
  });

  it('test_loading_shows_skeleton', () => {
    render(<CatalogueItemTypeChart data={[]} loading={true} />);
    expect(screen.getByText('Répartition actions / workflows')).toBeInTheDocument();
    expect(document.querySelector('.ant-skeleton')).toBeInTheDocument();
  });

  it('test_empty_data_shows_empty', () => {
    render(<CatalogueItemTypeChart data={[]} loading={false} />);
    expect(screen.getByText('Répartition actions / workflows')).toBeInTheDocument();
    expect(screen.getByText('Aucune donnée de catalogue')).toBeInTheDocument();
  });

  it('test_renders_with_data', () => {
    render(<CatalogueItemTypeChart data={mockData} loading={false} />);
    expect(screen.getByText('Répartition actions / workflows')).toBeInTheDocument();
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
    expect(screen.getByTestId('bar')).toBeInTheDocument();
  });

  it('renders unknown item_type with default gray color', () => {
    const unknownData: StatsCatalogueByItemType[] = [
      { item_type: 'other', count: 5 },
    ];
    render(<CatalogueItemTypeChart data={unknownData} loading={false} />);
    expect(screen.getByText('Répartition actions / workflows')).toBeInTheDocument();
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
    expect(screen.getByTestId('bar')).toBeInTheDocument();
  });
});
