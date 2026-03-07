import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ApprobationsRatioChart } from './ApprobationsRatioChart';

describe('ApprobationsRatioChart', () => {
  it('affiche le graphique avec des données', () => {
    render(
      <ApprobationsRatioChart approved={8} rejected={2} approvalRate={80.0} />
    );
    expect(
      screen.getByLabelText('Graphique de répartition des approbations')
    ).toBeInTheDocument();
    expect(screen.getByText("Taux d'approbation : 80.0 %")).toBeInTheDocument();
  });

  it('affiche un skeleton en état loading', () => {
    render(
      <ApprobationsRatioChart approved={8} rejected={2} approvalRate={80.0} loading />
    );
    expect(
      screen.queryByLabelText('Graphique de répartition des approbations')
    ).not.toBeInTheDocument();
    expect(screen.getByText('Répartition des approbations')).toBeInTheDocument();
  });

  it('affiche Empty si approved=0 et rejected=0', () => {
    render(
      <ApprobationsRatioChart approved={0} rejected={0} approvalRate={null} />
    );
    expect(screen.getByText('Aucune approbation sur la période')).toBeInTheDocument();
  });

  it("n'affiche pas le taux si approvalRate est null", () => {
    render(
      <ApprobationsRatioChart approved={3} rejected={1} approvalRate={null} />
    );
    expect(screen.queryByText(/Taux d'approbation/)).not.toBeInTheDocument();
  });
});
