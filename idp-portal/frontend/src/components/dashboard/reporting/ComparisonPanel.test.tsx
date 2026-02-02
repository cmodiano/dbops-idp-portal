/**
 * Tests for ComparisonPanel component (Story 8.6, AC1, AC2, AC3, AC4).
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ComparisonPanel } from './ComparisonPanel';
import type { FilterOptions } from '../../../types/api';

const mockFilterOptions: FilterOptions = {
  engines: ['Oracle', 'PostgreSQL', 'SQL Server'],
  environments: ['dev', 'staging', 'prod'],
  tags: ['patch', 'backup'],
  statuses: ['COMPLETED', 'FAILED'],
};

describe('ComparisonPanel', () => {
  it('renders dimension selector with technology selected by default (AC1)', () => {
    const onCompare = vi.fn();
    render(<ComparisonPanel filterOptions={mockFilterOptions} onCompare={onCompare} />);

    // Should show Technologie as the selected dimension
    expect(screen.getByText('Technologie')).toBeInTheDocument();
  });

  it('renders compare button (AC2)', () => {
    const onCompare = vi.fn();
    render(<ComparisonPanel filterOptions={mockFilterOptions} onCompare={onCompare} />);

    // Should have compare button
    const button = screen.getByRole('button', { name: /comparer/i });
    expect(button).toBeInTheDocument();
  });

  it('renders compare button disabled when no values selected', () => {
    const onCompare = vi.fn();
    render(<ComparisonPanel filterOptions={mockFilterOptions} onCompare={onCompare} />);

    const button = screen.getByRole('button', { name: /comparer/i });
    expect(button).toBeDisabled();
  });

  it('shows swap icon between value selectors', () => {
    const onCompare = vi.fn();
    render(<ComparisonPanel filterOptions={mockFilterOptions} onCompare={onCompare} />);

    // Should have swap icon
    expect(document.querySelector('.anticon-swap')).toBeInTheDocument();
  });

  it('shows loading state on compare button', () => {
    const onCompare = vi.fn();
    render(<ComparisonPanel filterOptions={mockFilterOptions} onCompare={onCompare} loading />);

    const button = screen.getByRole('button', { name: /comparer/i });
    expect(button).toBeInTheDocument();
    // Button should be in loading state
    expect(document.querySelector('.ant-btn-loading-icon')).toBeInTheDocument();
  });

  it('works without filter options (uses empty arrays)', () => {
    const onCompare = vi.fn();
    render(<ComparisonPanel filterOptions={null} onCompare={onCompare} />);

    // Should still render with dimension options
    expect(screen.getByText('Technologie')).toBeInTheDocument();
  });
});
