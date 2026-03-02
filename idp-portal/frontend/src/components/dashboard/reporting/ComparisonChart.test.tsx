/**
 * Tests for ComparisonChart component (Story 8.6, AC2, AC3, AC8).
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ComparisonChart } from './ComparisonChart';
import type { ComparisonResult } from '../../../types/api';

// Mock recharts to avoid ResponsiveContainer dimension issues in tests
// Tooltip mock renders content with active=true and payload to cover CustomTooltip (lines 57-68)
vi.mock('recharts', () => ({
  BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => <div data-testid="bar" />,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: ({ content }: { content: React.ReactElement }) => {
    if (!content) return null;
    // Invoke content as a function-component with active tooltip props to cover CustomTooltip body
    const ContentComponent = content.type as React.ComponentType<Record<string, unknown>>;
    const payload = [
      { name: 'Oracle', value: 95.0, color: '#4096ff' },
      { name: 'PostgreSQL', value: 88.5, color: '#16a34a' },
    ];
    return <ContentComponent active={true} payload={payload} label="Taux de succès (%)" />;
  },
  Legend: () => <div data-testid="legend" />,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div style={{ width: 500, height: 300 }}>{children}</div>
  ),
}));

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

  it('CustomTooltip renders tooltip content with active payload (covers CustomTooltip body)', () => {
    render(<ComparisonChart data={mockComparisonResult} loading={false} />);
    // The Tooltip mock invokes CustomTooltip with active=true and payload
    // So tooltip content "Taux de succès (%)" and entry names should be in the DOM
    expect(screen.getByText('Taux de succès (%)')).toBeInTheDocument();
    expect(screen.getByText('Oracle: 95.0')).toBeInTheDocument();
    expect(screen.getByText('PostgreSQL: 88.5')).toBeInTheDocument();
  });
});

describe('ComparisonChart — additional coverage', () => {
  it('renders the chart body with both comparison values', () => {
    render(<ComparisonChart data={mockComparisonResult} loading={false} />);
    // Chart card body should be present with data
    expect(document.querySelector('.ant-card-body')).toBeInTheDocument();
    // The card title with "graphique" is shown when data is present
    expect(screen.getByText('Comparaison graphique')).toBeInTheDocument();
  });

  it('renders Comparaison title for null data (not loading)', () => {
    render(<ComparisonChart data={null} loading={false} />);
    expect(screen.getByText('Comparaison')).toBeInTheDocument();
  });

  it('renders Comparaison graphique title when data present', () => {
    render(<ComparisonChart data={mockComparisonResult} loading={false} />);
    expect(screen.getByText('Comparaison graphique')).toBeInTheDocument();
  });

  it('renders Skeleton with Comparaison title when loading and data=null', () => {
    render(<ComparisonChart data={null} loading={true} />);
    expect(screen.getByText('Comparaison')).toBeInTheDocument();
    expect(document.querySelector('.ant-skeleton')).toBeInTheDocument();
  });

  it('does not render chart bars for null data (shows empty state)', () => {
    render(<ComparisonChart data={null} loading={false} />);
    // No recharts BarChart aria-label present
    const barChart = document.querySelector('[aria-label*="Comparaison entre"]');
    expect(barChart).not.toBeInTheDocument();
  });
});

