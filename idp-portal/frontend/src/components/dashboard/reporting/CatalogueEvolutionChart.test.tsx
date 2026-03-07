/**
 * Tests for CatalogueEvolutionChart component (Story 60.4, AC: 1, 2, 4, 5, 8).
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { CatalogueEvolutionChart } from './CatalogueEvolutionChart';
import type { StatsCatalogueEvolutionPoint } from '../../../types/api';

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

describe('CatalogueEvolutionChart', () => {
  const mockData: StatsCatalogueEvolutionPoint[] = [
    { week_start: '2026-01-01', created_count: 5, published_count: 3 },
    { week_start: '2026-01-08', created_count: 8, published_count: 6 },
  ];

  it('test_renders_chart_title', () => {
    render(<CatalogueEvolutionChart data={mockData} loading={false} />);
    expect(screen.getByText('Évolution du catalogue')).toBeInTheDocument();
    expect(document.querySelector('.ant-card-body')).toBeInTheDocument();
  });

  it('test_loading_shows_skeleton', () => {
    render(<CatalogueEvolutionChart data={[]} loading={true} />);
    expect(screen.getByText('Évolution du catalogue')).toBeInTheDocument();
    expect(document.querySelector('.ant-skeleton')).toBeInTheDocument();
  });

  it('test_empty_data_shows_empty', () => {
    render(<CatalogueEvolutionChart data={[]} loading={false} />);
    expect(screen.getByText('Évolution du catalogue')).toBeInTheDocument();
    expect(screen.getByText("Aucune donnée d'évolution")).toBeInTheDocument();
  });

  it('test_renders_with_data', () => {
    render(<CatalogueEvolutionChart data={mockData} loading={false} />);
    expect(screen.getByText('Évolution du catalogue')).toBeInTheDocument();
    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
  });
});
