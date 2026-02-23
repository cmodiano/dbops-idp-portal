import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ImpactLevelsLegend } from './ImpactLevelsLegend';

describe('ImpactLevelsLegend', () => {
  it('renders all 4 impact level labels', () => {
    render(<ImpactLevelsLegend />);
    expect(screen.getByText(/Faible/)).toBeInTheDocument();
    expect(screen.getByText(/Moyen/)).toBeInTheDocument();
    expect(screen.getByText(/Élevé/)).toBeInTheDocument();
    expect(screen.getByText(/Critique/)).toBeInTheDocument();
  });

  it('renders legend title', () => {
    render(<ImpactLevelsLegend />);
    expect(screen.getByText(/Signification des niveaux/)).toBeInTheDocument();
  });

  it('has accessible region with aria-label', () => {
    render(<ImpactLevelsLegend />);
    const region = screen.getByRole('region', { name: /Signification des niveaux d'impact/i });
    expect(region).toBeInTheDocument();
  });

  it('renders impact descriptions', () => {
    render(<ImpactLevelsLegend />);
    expect(screen.getByText(/Aucun impact/)).toBeInTheDocument();
    expect(screen.getByText(/Impact possible sur les performances/)).toBeInTheDocument();
    expect(screen.getByText(/Cause une indisponibilité du service/)).toBeInTheDocument();
  });
});
