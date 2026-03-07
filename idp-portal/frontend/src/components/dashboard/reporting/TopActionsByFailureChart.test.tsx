import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TopActionsByFailureChart } from './TopActionsByFailureChart';

const mockData = [
  { action_id: 1, action_name: 'Deploy DB', failure_count: 7 },
  { action_id: 2, action_name: 'Backup', failure_count: 3 },
];

describe('TopActionsByFailureChart', () => {
  it('affiche le graphique avec les données', () => {
    render(<TopActionsByFailureChart data={mockData} />);
    expect(
      screen.getByLabelText("Graphique des top actions par nombre d'échecs")
    ).toBeInTheDocument();
  });

  it('affiche un skeleton en état loading', () => {
    render(<TopActionsByFailureChart data={mockData} loading />);
    expect(
      screen.queryByLabelText("Graphique des top actions par nombre d'échecs")
    ).not.toBeInTheDocument();
    expect(screen.getByText('Top actions — échecs')).toBeInTheDocument();
  });

  it('affiche Empty si data est vide', () => {
    render(<TopActionsByFailureChart data={[]} />);
    expect(screen.getByText('Aucune donnée')).toBeInTheDocument();
  });
});
