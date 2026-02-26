/**
 * Tests for TechnologyBarChart component (Story 8.3, AC3).
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TechnologyBarChart } from './TechnologyBarChart';
import type { TechnologyStats } from '../../../types/api';

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
    expect(screen.getByText('Aucune execution sur la periode')).toBeInTheDocument();
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
