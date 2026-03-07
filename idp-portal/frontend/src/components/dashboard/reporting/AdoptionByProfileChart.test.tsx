/**
 * Tests for AdoptionByProfileChart component (Story 60.4, AC: 1, 3, 4, 5, 8).
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AdoptionByProfileChart } from './AdoptionByProfileChart';
import type { StatsAdoptionByProfile } from '../../../types/api';

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

describe('AdoptionByProfileChart', () => {
  const mockData: StatsAdoptionByProfile[] = [
    { profile: 'DBA', count: 50 },
    { profile: 'DBOPS', count: 20 },
  ];

  it('test_renders_chart_title', () => {
    render(<AdoptionByProfileChart data={mockData} loading={false} />);
    expect(screen.getByText('Adoption par profil')).toBeInTheDocument();
    expect(document.querySelector('.ant-card-body')).toBeInTheDocument();
  });

  it('test_loading_shows_skeleton', () => {
    render(<AdoptionByProfileChart data={[]} loading={true} />);
    expect(screen.getByText('Adoption par profil')).toBeInTheDocument();
    expect(document.querySelector('.ant-skeleton')).toBeInTheDocument();
  });

  it('test_empty_data_shows_empty', () => {
    render(<AdoptionByProfileChart data={[]} loading={false} />);
    expect(screen.getByText('Adoption par profil')).toBeInTheDocument();
    expect(screen.getByText("Aucune donnée d'adoption")).toBeInTheDocument();
  });

  it('test_renders_with_data', () => {
    render(<AdoptionByProfileChart data={mockData} loading={false} />);
    expect(screen.getByText('Adoption par profil')).toBeInTheDocument();
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
    expect(screen.getByTestId('bar')).toBeInTheDocument();
  });
});
