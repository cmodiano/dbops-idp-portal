/**
 * Tests for HorizontalFilters component (Story 8.7, AC5; Story 18.4: Environment filter removed).
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { HorizontalFilters, IMPACT_OPTIONS } from './HorizontalFilters';

vi.mock('../../hooks/useEngines', () => ({
  useEngines: () => ({
    engineOptions: [
      { value: 'Oracle', label: 'Oracle' },
      { value: 'SQL Server', label: 'SQL Server' },
      { value: 'DB2', label: 'DB2' },
    ],
    loading: false,
    error: null,
  }),
}));

describe('HorizontalFilters', () => {
  const defaultProps = {
    selectedEngines: [],
    selectedImpacts: [],
    onEnginesChange: vi.fn(),
    onImpactsChange: vi.fn(),
  };

  it('renders 2 Select dropdowns: Moteur and Impact (Story 18.4: Environment removed)', () => {
    render(<HorizontalFilters {...defaultProps} />);

    expect(screen.getByText('Moteur')).toBeInTheDocument();
    expect(screen.getByText('Impact')).toBeInTheDocument();
    // Story 18.4: Environment filter removed
    expect(screen.queryByText('Environnement')).not.toBeInTheDocument();
  });

  it('renders with correct placeholders', () => {
    render(<HorizontalFilters {...defaultProps} />);

    expect(screen.getByText('Tous les moteurs')).toBeInTheDocument();
    expect(screen.getByText('Tous les impacts')).toBeInTheDocument();
    // Story 18.4: Environment placeholder removed
    expect(screen.queryByText('Tous les environnements')).not.toBeInTheDocument();
  });

  it('renders with selected engines prop', () => {
    const { container } = render(
      <HorizontalFilters
        {...defaultProps}
        selectedEngines={['Oracle']}
      />
    );

    expect(container.querySelector('.ant-select')).toBeInTheDocument();
  });

  it('renders with selected impacts prop', () => {
    const { container } = render(
      <HorizontalFilters
        {...defaultProps}
        selectedImpacts={['high']}
      />
    );

    expect(container.querySelector('.ant-select')).toBeInTheDocument();
  });

  it('has correct engine options defined', () => {
    render(<HorizontalFilters {...defaultProps} />);
    expect(screen.getByLabelText('Filtrer par moteur')).toBeInTheDocument();
  });

  it('has correct impact options defined', () => {
    expect(IMPACT_OPTIONS).toEqual([
      { value: 'low', label: 'Faible' },
      { value: 'medium', label: 'Moyen' },
      { value: 'high', label: 'Élevé' },
    ]);
  });

  it('has ARIA labels for accessibility (2 filters only)', () => {
    render(<HorizontalFilters {...defaultProps} />);

    expect(screen.getByLabelText('Filtrer par moteur')).toBeInTheDocument();
    expect(screen.getByLabelText('Filtrer par impact')).toBeInTheDocument();
    // Story 18.4: Environment ARIA label removed
    expect(screen.queryByLabelText('Filtrer par environnement')).not.toBeInTheDocument();
  });

  it('renders 2 columns with sm=12 layout (Story 18.4)', () => {
    const { container } = render(<HorizontalFilters {...defaultProps} />);

    const selects = container.querySelectorAll('.ant-select');
    expect(selects).toHaveLength(2);
  });

  describe('Story 46.2 — taille minimale 44px (WCAG 2.5.5)', () => {
    it('les Select ont un style minHeight >= 44px', () => {
      const { container } = render(<HorizontalFilters {...defaultProps} />);

      const selects = container.querySelectorAll('.ant-select');
      expect(selects.length).toBe(2);
      selects.forEach((select) => {
        const el = select as HTMLElement;
        const minHeight = parseInt(el.style.minHeight);
        expect(minHeight).toBeGreaterThanOrEqual(44);
      });
    });

    it('les Select ont size="large" (classe ant-select-lg)', () => {
      const { container } = render(<HorizontalFilters {...defaultProps} />);

      const largeSelects = container.querySelectorAll('.ant-select-lg');
      expect(largeSelects.length).toBe(2);
    });

    it('aucun Select n\'a size="small" ou size="middle"', () => {
      const { container } = render(<HorizontalFilters {...defaultProps} />);

      expect(container.querySelectorAll('.ant-select-sm')).toHaveLength(0);
      expect(container.querySelectorAll('.ant-select-md')).toHaveLength(0);
    });
  });
});
