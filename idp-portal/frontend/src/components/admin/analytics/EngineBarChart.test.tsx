/**
 * Tests for EngineBarChart component (Story 8.2, AC1, AC5, Task 12.1-12.2).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EngineBarChart } from './EngineBarChart';
import type { EngineExecutions } from '../../../types/api';

const mockData: EngineExecutions[] = [
  { engine: 'Oracle', count: 100 },
  { engine: 'SQL Server', count: 50 },
  { engine: 'DB2', count: 25 },
];

describe('EngineBarChart', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders chart with data', () => {
    render(<EngineBarChart data={mockData} loading={false} />);

    expect(screen.getByText('Exécutions par moteur')).toBeInTheDocument();
    // Check that the chart container exists
    expect(document.querySelector('.recharts-responsive-container')).toBeTruthy();
  });

  it('renders empty state when no data', () => {
    render(<EngineBarChart data={[]} loading={false} />);

    expect(screen.getByText('Exécutions par moteur')).toBeInTheDocument();
    expect(screen.getByText('Aucune execution')).toBeInTheDocument();
  });

  it('renders skeleton when loading', () => {
    render(<EngineBarChart data={[]} loading={true} />);

    expect(screen.getByText('Exécutions par moteur')).toBeInTheDocument();
    // Skeleton should be present (Ant Design renders animated placeholder)
    expect(document.querySelector('.ant-skeleton')).toBeTruthy();
  });

  it('renders chart with single engine', () => {
    render(<EngineBarChart data={[{ engine: 'Oracle', count: 50 }]} loading={false} />);

    expect(screen.getByText('Exécutions par moteur')).toBeInTheDocument();
  });
});
