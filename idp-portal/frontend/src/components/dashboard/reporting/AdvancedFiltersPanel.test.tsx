/**
 * Tests for AdvancedFiltersPanel (Story 8.4, Task 15).
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AdvancedFiltersPanel } from './AdvancedFiltersPanel';
import type { DashboardFilters, FilterOptions } from '../../../types/api';

describe('AdvancedFiltersPanel', () => {
  const mockOnFiltersChange = vi.fn();

  const defaultProps = {
    filters: {} as DashboardFilters,
    onFiltersChange: mockOnFiltersChange,
    loading: false,
    filterOptions: null,
  };

  beforeEach(() => {
    mockOnFiltersChange.mockClear();
  });

  it('renders all filter controls (AC1)', () => {
    render(<AdvancedFiltersPanel {...defaultProps} />);

    expect(screen.getByTestId('advanced-filters-panel')).toBeInTheDocument();
    expect(screen.getByTestId('filter-engine')).toBeInTheDocument();
    expect(screen.getByTestId('filter-environment')).toBeInTheDocument();
    expect(screen.getByTestId('filter-tags')).toBeInTheDocument();
    expect(screen.getByTestId('filter-status')).toBeInTheDocument();
    // RangePicker has two inputs, so use getAllBy
    expect(screen.getAllByTestId('filter-date-range').length).toBe(2);
    expect(screen.getByTestId('filter-reset')).toBeInTheDocument();
  });

  it('displays engine select with placeholder', () => {
    render(<AdvancedFiltersPanel {...defaultProps} />);

    // Check placeholder is shown
    expect(screen.getByText('Moteur')).toBeInTheDocument();
  });

  it('reset button clears all filters (AC5)', () => {
    const filtersWithValues: DashboardFilters = {
      engine: 'aap',
      environment: 'prod',
      status: 'COMPLETED',
    };

    render(
      <AdvancedFiltersPanel
        {...defaultProps}
        filters={filtersWithValues}
      />,
    );

    const resetButton = screen.getByTestId('filter-reset');
    expect(resetButton).not.toBeDisabled();

    fireEvent.click(resetButton);

    expect(mockOnFiltersChange).toHaveBeenCalledWith({});
  });

  it('reset button is disabled when no filters are active', () => {
    render(<AdvancedFiltersPanel {...defaultProps} />);

    const resetButton = screen.getByTestId('filter-reset');
    expect(resetButton).toBeDisabled();
  });

  it('displays active filters count badge when filters are applied', () => {
    const filtersWithValues: DashboardFilters = {
      engine: 'aap',
      environment: 'prod',
    };

    render(
      <AdvancedFiltersPanel
        {...defaultProps}
        filters={filtersWithValues}
      />,
    );

    const badge = screen.getByTestId('active-filters-count');
    expect(badge).toHaveTextContent('2 filtres actifs');
  });

  it('displays singular form for single active filter', () => {
    const filtersWithValues: DashboardFilters = {
      engine: 'aap',
    };

    render(
      <AdvancedFiltersPanel
        {...defaultProps}
        filters={filtersWithValues}
      />,
    );

    const badge = screen.getByTestId('active-filters-count');
    expect(badge).toHaveTextContent('1 filtre actif');
  });

  it('does not display active filters badge when no filters', () => {
    render(<AdvancedFiltersPanel {...defaultProps} />);

    expect(screen.queryByTestId('active-filters-count')).not.toBeInTheDocument();
  });

  it('disables inputs when loading', () => {
    render(<AdvancedFiltersPanel {...defaultProps} loading={true} />);

    const engineSelect = screen.getByTestId('filter-engine');
    expect(engineSelect).toHaveClass('ant-select-disabled');

    const resetButton = screen.getByTestId('filter-reset');
    expect(resetButton).toBeDisabled();
  });

  it('counts date range as single filter', () => {
    const filtersWithDateRange: DashboardFilters = {
      fromDate: '2026-01-01',
      toDate: '2026-01-31',
    };

    render(
      <AdvancedFiltersPanel
        {...defaultProps}
        filters={filtersWithDateRange}
      />,
    );

    const badge = screen.getByTestId('active-filters-count');
    expect(badge).toHaveTextContent('1 filtre actif');
  });

  it('counts tags array as single filter', () => {
    const filtersWithTags: DashboardFilters = {
      tags: ['oracle', 'postgresql'],
    };

    render(
      <AdvancedFiltersPanel
        {...defaultProps}
        filters={filtersWithTags}
      />,
    );

    const badge = screen.getByTestId('active-filters-count');
    expect(badge).toHaveTextContent('1 filtre actif');
  });

  it('uses dynamic filterOptions from API when provided', () => {
    const dynamicOptions: FilterOptions = {
      engines: ['CustomEngine1', 'CustomEngine2'],
      environments: ['custom-env', 'another-env'],
      tags: ['tag1', 'tag2', 'tag3'],
      statuses: ['COMPLETED', 'FAILED'],
    };

    render(
      <AdvancedFiltersPanel
        {...defaultProps}
        filterOptions={dynamicOptions}
      />,
    );

    // Component should render with dynamic options
    // (Options are in Select dropdowns, so we just verify component renders)
    expect(screen.getByTestId('filter-engine')).toBeInTheDocument();
    expect(screen.getByTestId('filter-environment')).toBeInTheDocument();
    expect(screen.getByTestId('filter-tags')).toBeInTheDocument();
  });
});
