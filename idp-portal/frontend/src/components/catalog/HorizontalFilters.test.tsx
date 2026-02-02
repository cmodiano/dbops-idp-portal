/**
 * Tests for HorizontalFilters component (Story 8.7, AC5).
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { HorizontalFilters, ENGINE_OPTIONS, ENVIRONMENT_OPTIONS, IMPACT_OPTIONS } from './HorizontalFilters';

describe('HorizontalFilters', () => {
  const defaultProps = {
    selectedEngines: [],
    selectedEnvironments: [],
    selectedImpacts: [],
    onEnginesChange: vi.fn(),
    onEnvironmentsChange: vi.fn(),
    onImpactsChange: vi.fn(),
  };

  it('renders 3 Select dropdowns', () => {
    render(<HorizontalFilters {...defaultProps} />);

    expect(screen.getByText('Moteur')).toBeInTheDocument();
    expect(screen.getByText('Environnement')).toBeInTheDocument();
    expect(screen.getByText('Impact')).toBeInTheDocument();
  });

  it('renders with correct placeholders', () => {
    render(<HorizontalFilters {...defaultProps} />);

    expect(screen.getByText('Tous les moteurs')).toBeInTheDocument();
    expect(screen.getByText('Tous les environnements')).toBeInTheDocument();
    expect(screen.getByText('Tous les impacts')).toBeInTheDocument();
  });

  it('renders with selected engines prop', () => {
    const { container } = render(
      <HorizontalFilters
        {...defaultProps}
        selectedEngines={['Oracle']}
      />
    );

    // Verify component renders without error with selected values
    expect(container.querySelector('.ant-select')).toBeInTheDocument();
  });

  it('renders with selected environments prop', () => {
    const { container } = render(
      <HorizontalFilters
        {...defaultProps}
        selectedEnvironments={['PROD', 'DEV']}
      />
    );

    // Verify component renders without error with selected values
    expect(container.querySelectorAll('.ant-select').length).toBe(3);
  });

  it('renders with selected impacts prop', () => {
    const { container } = render(
      <HorizontalFilters
        {...defaultProps}
        selectedImpacts={['high']}
      />
    );

    // Verify component renders without error with selected values
    expect(container.querySelector('.ant-select')).toBeInTheDocument();
  });

  it('has correct engine options defined', () => {
    expect(ENGINE_OPTIONS).toEqual([
      { value: 'Oracle', label: 'Oracle' },
      { value: 'SQL Server', label: 'SQL Server' },
      { value: 'DB2', label: 'DB2' },
    ]);
  });

  it('has correct environment options defined', () => {
    expect(ENVIRONMENT_OPTIONS).toEqual([
      { value: 'DEV', label: 'DEV' },
      { value: 'QUAL', label: 'QUAL' },
      { value: 'PROD', label: 'PROD' },
    ]);
  });

  it('has correct impact options defined', () => {
    expect(IMPACT_OPTIONS).toEqual([
      { value: 'low', label: 'Faible' },
      { value: 'medium', label: 'Moyen' },
      { value: 'high', label: 'Élevé' },
    ]);
  });

  it('has ARIA labels for accessibility', () => {
    render(<HorizontalFilters {...defaultProps} />);

    expect(screen.getByLabelText('Filtrer par moteur')).toBeInTheDocument();
    expect(screen.getByLabelText('Filtrer par environnement')).toBeInTheDocument();
    expect(screen.getByLabelText('Filtrer par impact')).toBeInTheDocument();
  });
});
