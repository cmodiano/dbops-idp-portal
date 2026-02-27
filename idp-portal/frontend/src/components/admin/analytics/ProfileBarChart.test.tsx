/**
 * Tests for ProfileBarChart component (Story 8.2, AC1, Task 12.3).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProfileBarChart } from './ProfileBarChart';
import type { ProfileExecutions } from '../../../types/api';

const mockData: ProfileExecutions[] = [
  { profile: 'dba_app', count: 80 },
  { profile: 'dbops', count: 70 },
  { profile: 'client', count: 20 },
];

describe('ProfileBarChart', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders chart with data', () => {
    render(<ProfileBarChart data={mockData} loading={false} />);

    expect(screen.getByText('Exécutions par profil')).toBeInTheDocument();
  });

  it('renders empty state when no data', () => {
    render(<ProfileBarChart data={[]} loading={false} />);

    expect(screen.getByText('Exécutions par profil')).toBeInTheDocument();
    expect(screen.getByText('Aucune execution')).toBeInTheDocument();
  });

  it('renders skeleton when loading', () => {
    render(<ProfileBarChart data={[]} loading={true} />);

    expect(screen.getByText('Exécutions par profil')).toBeInTheDocument();
    expect(document.querySelector('.ant-skeleton')).toBeTruthy();
  });
});
