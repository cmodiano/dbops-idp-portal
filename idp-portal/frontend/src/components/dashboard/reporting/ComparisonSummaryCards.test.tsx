/**
 * Tests for ComparisonSummaryCards component (Story 8.6, AC5).
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ComparisonSummaryCards } from './ComparisonSummaryCards';
import type { ComparisonResult } from '../../../types/api';

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

describe('ComparisonSummaryCards', () => {
  it('renders four metric cards (AC5)', () => {
    render(<ComparisonSummaryCards data={mockComparisonResult} />);

    expect(screen.getByText('Taux de succès')).toBeInTheDocument();
    expect(screen.getByText('Temps moyen')).toBeInTheDocument();
    expect(screen.getByText('Exécutions')).toBeInTheDocument();
    expect(screen.getByText('Incidents')).toBeInTheDocument();
  });

  it('displays value labels (value1 and value2 names)', () => {
    render(<ComparisonSummaryCards data={mockComparisonResult} />);

    // Should show both value names
    const oracleLabels = screen.getAllByText('Oracle');
    const postgresLabels = screen.getAllByText('PostgreSQL');

    expect(oracleLabels.length).toBeGreaterThan(0);
    expect(postgresLabels.length).toBeGreaterThan(0);
  });

  it('displays formatted metric values', () => {
    render(<ComparisonSummaryCards data={mockComparisonResult} />);

    // Execution counts (simple numbers are easier to match)
    expect(screen.getByText('50')).toBeInTheDocument();
    expect(screen.getByText('30')).toBeInTheDocument();
  });

  it('renders loading skeleton when loading', () => {
    render(<ComparisonSummaryCards data={null} loading />);

    // Should have skeleton placeholder divs
    const skeletons = document.querySelectorAll('[style*="background"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders empty state when no data', () => {
    render(<ComparisonSummaryCards data={null} loading={false} />);

    // Should show "Aucune donnée" messages
    const noDataTexts = screen.getAllByText('Aucune donnée');
    expect(noDataTexts.length).toBe(4); // One per card
  });

  it('calls onMetricClick when card is clicked', () => {
    const onMetricClick = vi.fn();
    render(<ComparisonSummaryCards data={mockComparisonResult} onMetricClick={onMetricClick} />);

    // Click on success rate card
    const successRateCard = screen.getByText('Taux de succès').closest('.ant-card');
    fireEvent.click(successRateCard!);

    expect(onMetricClick).toHaveBeenCalledWith('success_rate');
  });

  it('makes cards hoverable when onMetricClick is provided', () => {
    const onMetricClick = vi.fn();
    render(<ComparisonSummaryCards data={mockComparisonResult} onMetricClick={onMetricClick} />);

    // Cards should have hoverable class
    const cards = document.querySelectorAll('.ant-card-hoverable');
    expect(cards.length).toBe(4);
  });

  it('cards are not hoverable when onMetricClick is not provided', () => {
    render(<ComparisonSummaryCards data={mockComparisonResult} />);

    // Cards should not have hoverable class
    const cards = document.querySelectorAll('.ant-card-hoverable');
    expect(cards.length).toBe(0);
  });
});
