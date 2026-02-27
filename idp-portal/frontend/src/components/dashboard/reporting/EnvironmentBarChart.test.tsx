/**
 * Tests for EnvironmentBarChart component (Story 8.3, AC4).
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { EnvironmentBarChart } from './EnvironmentBarChart';
import type { EnvironmentStats } from '../../../types/api';

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

describe('EnvironmentBarChart', () => {
  const mockData: EnvironmentStats[] = [
    { environment: 'dev', count: 40, success_rate: 92.0 },
    { environment: 'staging', count: 25, success_rate: 88.0 },
    { environment: 'prod', count: 20, success_rate: 95.0 },
  ];

  it('renders chart title with data', () => {
    render(<EnvironmentBarChart data={mockData} loading={false} />);

    expect(screen.getByText('Répartition par environnement')).toBeInTheDocument();
    // Chart card should be present (chart content depends on recharts rendering)
    expect(document.querySelector('.ant-card-body')).toBeInTheDocument();
  });

  it('renders empty state when no data', () => {
    render(<EnvironmentBarChart data={[]} loading={false} />);

    expect(screen.getByText('Répartition par environnement')).toBeInTheDocument();
    expect(screen.getByText('Aucune execution sur la periode')).toBeInTheDocument();
  });

  it('renders skeleton when loading', () => {
    render(<EnvironmentBarChart data={[]} loading={true} />);

    expect(screen.getByText('Répartition par environnement')).toBeInTheDocument();
    expect(document.querySelector('.ant-skeleton')).toBeInTheDocument();
  });

  it('renders chart container with single environment', () => {
    const singleData: EnvironmentStats[] = [
      { environment: 'prod', count: 100, success_rate: 99.5 },
    ];

    render(<EnvironmentBarChart data={singleData} loading={false} />);

    expect(screen.getByText('Répartition par environnement')).toBeInTheDocument();
    expect(document.querySelector('.ant-card-body')).toBeInTheDocument();
  });
});
