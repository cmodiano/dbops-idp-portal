/**
 * Tests for ComparisonModeSelector component (Story 8.6, AC1).
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ComparisonModeSelector } from './ComparisonModeSelector';

describe('ComparisonModeSelector', () => {
  it('renders both mode options', () => {
    const onModeChange = vi.fn();
    render(<ComparisonModeSelector mode="stats" onModeChange={onModeChange} />);

    expect(screen.getByText('Statistiques')).toBeInTheDocument();
    expect(screen.getByText('Comparaison')).toBeInTheDocument();
  });

  it('displays stats mode as selected when mode is stats', () => {
    const onModeChange = vi.fn();
    render(<ComparisonModeSelector mode="stats" onModeChange={onModeChange} />);

    // The Segmented component marks the selected option with a specific class
    const segmented = document.querySelector('.ant-segmented');
    expect(segmented).toBeInTheDocument();
  });

  it('displays comparison mode as selected when mode is comparison', () => {
    const onModeChange = vi.fn();
    render(<ComparisonModeSelector mode="comparison" onModeChange={onModeChange} />);

    const segmented = document.querySelector('.ant-segmented');
    expect(segmented).toBeInTheDocument();
  });

  it('calls onModeChange when clicking comparison mode', () => {
    const onModeChange = vi.fn();
    render(<ComparisonModeSelector mode="stats" onModeChange={onModeChange} />);

    fireEvent.click(screen.getByText('Comparaison'));

    expect(onModeChange).toHaveBeenCalledWith('comparison');
  });

  it('calls onModeChange when clicking stats mode', () => {
    const onModeChange = vi.fn();
    render(<ComparisonModeSelector mode="comparison" onModeChange={onModeChange} />);

    fireEvent.click(screen.getByText('Statistiques'));

    expect(onModeChange).toHaveBeenCalledWith('stats');
  });
});
