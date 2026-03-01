/**
 * Tests for ComparisonPanel component (Story 8.6, AC1, AC2, AC3, AC4).
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import dayjs, { type Dayjs } from 'dayjs';
import { ComparisonPanel } from './ComparisonPanel';
import type { FilterOptions } from '../../../types/api';

// Mock antd: RangePicker controllable + value Selects as native selects for testability
vi.mock('antd', async (importOriginal) => {
  const mod = await importOriginal<typeof import('antd')>();

  // Replace value Selects (Première/Deuxième valeur) with native selects that properly fire onChange
  const SelectWrapper = (props: {
    value?: string;
    onChange?: (value: string | undefined) => void;
    options?: Array<{ label: string; value: string }>;
    placeholder?: string;
    'aria-label'?: string;
    [key: string]: unknown;
  }) => {
    const { 'aria-label': ariaLabel, onChange, value, options = [], placeholder } = props;
    if (ariaLabel === 'Première valeur' || ariaLabel === 'Deuxième valeur') {
      return (
        <select
          aria-label={ariaLabel}
          value={value ?? ''}
          onChange={(e) => onChange?.(e.target.value || undefined)}
        >
          <option value="">{placeholder}</option>
          {options.map((o: { label: string; value: string }) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      );
    }
    return <mod.Select {...(props as Record<string, unknown>)} />;
  };
  SelectWrapper.Option = mod.Select.Option;
  SelectWrapper.OptGroup = mod.Select.OptGroup;

  return {
    ...mod,
    Select: SelectWrapper,
    DatePicker: Object.assign(
      { ...mod.DatePicker },
      {
        RangePicker: ({ onChange, 'aria-label': ariaLabel }: {
          onChange?: (dates: [Dayjs | null, Dayjs | null] | null) => void;
          'aria-label'?: string;
        }) => (
          <button
            data-testid={`range-picker-${ariaLabel}`}
            aria-label={ariaLabel}
            onClick={() => onChange?.([dayjs('2026-01-01'), dayjs('2026-01-31')])}
            className="ant-picker-range"
          >
            {ariaLabel}
          </button>
        ),
      }
    ),
  };
});

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

  it('affiche les RangePickers quand dimension=period', async () => {
    const user = userEvent.setup();
    const { container } = render(<ComparisonPanel filterOptions={mockFilterOptions} onCompare={vi.fn()} />);

    const dimensionSelect = container.querySelector('[aria-label="Dimension de comparaison"]');
    await user.click(dimensionSelect!.closest('.ant-select')!);

    // Cliquer sur l'option "Période" dans le dropdown
    const options = document.querySelectorAll('.ant-select-item-option');
    const periodOpt = Array.from(options).find(o => o.textContent?.trim() === 'Période');
    expect(periodOpt).toBeTruthy();
    await user.click(periodOpt as HTMLElement);

    expect(document.querySelectorAll('.ant-picker-range').length).toBeGreaterThan(0);
  });

  it('affiche les selects valeur pour Environnement quand dimension=environment', async () => {
    const user = userEvent.setup();
    const { container } = render(<ComparisonPanel filterOptions={mockFilterOptions} onCompare={vi.fn()} />);

    const dimensionSelect = container.querySelector('[aria-label="Dimension de comparaison"]');
    await user.click(dimensionSelect!.closest('.ant-select')!);

    const options = document.querySelectorAll('.ant-select-item-option');
    const envOpt = Array.from(options).find(o => o.textContent?.trim() === 'Environnement');
    expect(envOpt).toBeTruthy();
    await user.click(envOpt as HTMLElement);

    expect(screen.getByLabelText('Première valeur')).toBeInTheDocument();
    expect(screen.getByLabelText('Deuxième valeur')).toBeInTheDocument();
  });

  it('handleCompare — appelle onCompare avec les valeurs sélectionnées', async () => {
    const user = userEvent.setup();
    const onCompare = vi.fn();
    render(<ComparisonPanel filterOptions={mockFilterOptions} onCompare={onCompare} />);

    // Sélectionner val1 = Oracle (native select via fireEvent.change)
    const val1Select = screen.getByLabelText('Première valeur') as HTMLSelectElement;
    fireEvent.change(val1Select, { target: { value: 'Oracle' } });

    // Sélectionner val2 = PostgreSQL
    const val2Select = screen.getByLabelText('Deuxième valeur') as HTMLSelectElement;
    fireEvent.change(val2Select, { target: { value: 'PostgreSQL' } });

    // Attendre que le bouton soit activé (canCompare=true après les setState)
    const compareBtn = screen.getByRole('button', { name: /comparer/i });
    await waitFor(() => expect(compareBtn).not.toBeDisabled());

    await user.click(compareBtn);
    expect(onCompare).toHaveBeenCalledWith('technology', 'Oracle', 'PostgreSQL');
  });

  it('handleDimensionChange — réinitialise les valeurs quand la dimension change', async () => {
    const user = userEvent.setup();
    const { container } = render(<ComparisonPanel filterOptions={mockFilterOptions} onCompare={vi.fn()} />);

    // Sélectionner Oracle via native select
    const val1Select = screen.getByLabelText('Première valeur') as HTMLSelectElement;
    fireEvent.change(val1Select, { target: { value: 'Oracle' } });

    // Changer dimension → réinitialisation
    const dimensionSelect = container.querySelector('[aria-label="Dimension de comparaison"]');
    await user.click(dimensionSelect!.closest('.ant-select')!);
    const dimOpts = document.querySelectorAll('.ant-select-item-option');
    const envOpt = Array.from(dimOpts).find(o => o.textContent?.trim() === 'Environnement');
    await user.click(envOpt as HTMLElement);

    const compareBtn = screen.getByRole('button', { name: /comparer/i });
    expect(compareBtn).toBeDisabled();
  });

  it('bouton Comparer reste désactivé quand une seule valeur est sélectionnée', () => {
    render(<ComparisonPanel filterOptions={mockFilterOptions} onCompare={vi.fn()} />);

    const val1Select = screen.getByLabelText('Première valeur') as HTMLSelectElement;
    fireEvent.change(val1Select, { target: { value: 'Oracle' } });

    expect(screen.getByRole('button', { name: /comparer/i })).toBeDisabled();
  });

  it('RangePicker — affiche Période 1 et Période 2 en dimension période', async () => {
    const user = userEvent.setup();
    const { container } = render(<ComparisonPanel filterOptions={mockFilterOptions} onCompare={vi.fn()} />);

    // Changer dimension vers "Période"
    const dimensionSelect = container.querySelector('[aria-label="Dimension de comparaison"]');
    await user.click(dimensionSelect!.closest('.ant-select')!);

    const dimOptions = document.querySelectorAll('.ant-select-item-option');
    const periodOpt = Array.from(dimOptions).find(o => o.textContent?.trim() === 'Période');
    expect(periodOpt).toBeTruthy();
    await user.click(periodOpt as HTMLElement);

    // Les RangePickers doivent être affichés (aria-label vérifié sur les placeholders)
    expect(document.querySelectorAll('.ant-picker-range').length).toBeGreaterThanOrEqual(2);
  });

  it('handleCompare avec dimension période — appelle onCompare quand les deux périodes sont définies', async () => {
    const user = userEvent.setup();
    const onCompare = vi.fn();
    const { container } = render(<ComparisonPanel filterOptions={mockFilterOptions} onCompare={onCompare} />);

    // Changer dimension vers "Période"
    const dimensionSelect = container.querySelector('[aria-label="Dimension de comparaison"]');
    await user.click(dimensionSelect!.closest('.ant-select')!);
    const dimOptions = document.querySelectorAll('.ant-select-item-option');
    const periodOpt = Array.from(dimOptions).find(o => o.textContent?.trim() === 'Période');
    await user.click(periodOpt as HTMLElement);

    // Sélectionner période 1 et période 2 (via les boutons du RangePicker mocké)
    const period1Btn = screen.getByTestId('range-picker-Période 1');
    const period2Btn = screen.getByTestId('range-picker-Période 2');
    await user.click(period1Btn);
    await user.click(period2Btn);

    // Maintenant canCompare est true — cliquer Comparer
    const compareBtn = screen.getByRole('button', { name: /comparer/i });
    await user.click(compareBtn);

    expect(onCompare).toHaveBeenCalledWith(
      'period',
      'Période 1',
      'Période 2',
      '2026-01-01',
      '2026-01-31',
      '2026-01-01',
      '2026-01-31',
    );
  });
});
