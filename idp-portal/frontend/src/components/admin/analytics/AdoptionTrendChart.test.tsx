/**
 * Tests for AdoptionTrendChart component (Story 8.2, AC2, Task 12.4).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AdoptionTrendChart } from './AdoptionTrendChart';
import type { WeeklyTrendPoint } from '../../../types/api';

const mockData: WeeklyTrendPoint[] = [
  { week_start: '2026-01-01', engine: 'Oracle', count: 10 },
  { week_start: '2026-01-01', engine: 'SQL Server', count: 5 },
  { week_start: '2026-01-08', engine: 'Oracle', count: 15 },
  { week_start: '2026-01-08', engine: 'SQL Server', count: 8 },
  { week_start: '2026-01-15', engine: 'Oracle', count: 20 },
  { week_start: '2026-01-15', engine: 'SQL Server', count: 12 },
];

describe('AdoptionTrendChart', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders chart with multi-engine data', () => {
    render(<AdoptionTrendChart data={mockData} loading={false} />);

    expect(screen.getByText("Tendance d'adoption (par semaine)")).toBeInTheDocument();
  });

  it('renders empty state when no data', () => {
    render(<AdoptionTrendChart data={[]} loading={false} />);

    expect(screen.getByText("Tendance d'adoption (par semaine)")).toBeInTheDocument();
    expect(screen.getByText('Aucune donnée')).toBeInTheDocument();
  });

  it('renders skeleton when loading', () => {
    render(<AdoptionTrendChart data={[]} loading={true} />);

    expect(screen.getByText("Tendance d'adoption (par semaine)")).toBeInTheDocument();
    expect(document.querySelector('.ant-skeleton')).toBeTruthy();
  });

  it('renders with single engine data', () => {
    const singleEngineData: WeeklyTrendPoint[] = [
      { week_start: '2026-01-01', engine: 'Oracle', count: 10 },
      { week_start: '2026-01-08', engine: 'Oracle', count: 15 },
    ];
    render(<AdoptionTrendChart data={singleEngineData} loading={false} />);

    expect(screen.getByText("Tendance d'adoption (par semaine)")).toBeInTheDocument();
  });
});
