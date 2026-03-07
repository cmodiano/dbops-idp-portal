import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TopActionsByExecutionChart } from './TopActionsByExecutionChart';

const mockData = [
  { action_id: 1, action_name: 'Deploy DB', execution_count: 42 },
  { action_id: 2, action_name: 'Backup', execution_count: 28 },
];

describe('TopActionsByExecutionChart', () => {
  it('affiche le graphique avec les données', () => {
    render(<TopActionsByExecutionChart data={mockData} />);
    expect(
      screen.getByLabelText("Graphique des top actions par nombre d'exécutions")
    ).toBeInTheDocument();
  });

  it('affiche un skeleton en état loading', () => {
    render(<TopActionsByExecutionChart data={mockData} loading />);
    expect(
      screen.queryByLabelText("Graphique des top actions par nombre d'exécutions")
    ).not.toBeInTheDocument();
    expect(screen.getByText('Top actions — exécutions')).toBeInTheDocument();
  });

  it('affiche Empty si data est vide', () => {
    render(<TopActionsByExecutionChart data={[]} />);
    expect(screen.getByText('Aucune donnée')).toBeInTheDocument();
  });
});
