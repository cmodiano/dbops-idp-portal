/**
 * ValidationReportPanel tests (Story 16.7, AC7).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ValidationReportPanel from './ValidationReportPanel';
import type { ValidationResult } from '../../utils/workflowValidation';

describe('ValidationReportPanel', () => {
  const validResult: ValidationResult = {
    valid: true,
    errors: [],
  };

  const invalidResult: ValidationResult = {
    valid: false,
    errors: [
      { nodeId: 'a', type: 'error', message: 'Non atteignable depuis le début' },
      { nodeId: 'b', type: 'error', message: 'Boucle infinie détectée' },
      { nodeId: 'c', type: 'warning', message: 'Pas de chemin de sortie' },
    ],
  };

  it('renders nothing when validation is null', () => {
    const { container } = render(
      <ValidationReportPanel
        validation={null}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('shows error and warning statistic titles', () => {
    render(
      <ValidationReportPanel
        validation={invalidResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );

    expect(screen.getByText('Erreurs')).toBeInTheDocument();
  });

  it('shows error messages', () => {
    render(
      <ValidationReportPanel
        validation={invalidResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );

    expect(screen.getByText('Non atteignable depuis le début')).toBeInTheDocument();
    expect(screen.getByText('Boucle infinie détectée')).toBeInTheDocument();
  });

  it('shows warning messages', () => {
    render(
      <ValidationReportPanel
        validation={invalidResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );

    expect(screen.getByText('Pas de chemin de sortie')).toBeInTheDocument();
  });

  it('renders "Aller au nœud" buttons for each item with nodeId', () => {
    render(
      <ValidationReportPanel
        validation={invalidResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );

    const goToButtons = screen.getAllByText('Aller au nœud');
    expect(goToButtons.length).toBe(3); // 2 errors + 1 warning, all have nodeId
  });

  it('calls onGoToNode when "Aller au nœud" is clicked', async () => {
    const onGoToNode = vi.fn();
    const user = userEvent.setup();

    render(
      <ValidationReportPanel
        validation={invalidResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={onGoToNode}
      />,
    );

    const goToButtons = screen.getAllByLabelText(/Aller au nœud/);
    await user.click(goToButtons[0]);

    expect(onGoToNode).toHaveBeenCalledWith('a');
  });

  it('shows success message when validation is valid', () => {
    render(
      <ValidationReportPanel
        validation={validResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );

    expect(screen.getByText('Workflow valide')).toBeInTheDocument();
  });

  it('shows "Erreurs bloquantes" section divider', () => {
    render(
      <ValidationReportPanel
        validation={invalidResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );

    expect(screen.getByText('Erreurs bloquantes')).toBeInTheDocument();
  });

  it('shows node IDs in error descriptions', () => {
    render(
      <ValidationReportPanel
        validation={invalidResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );

    expect(screen.getByText('Nœud : a')).toBeInTheDocument();
    expect(screen.getByText('Nœud : b')).toBeInTheDocument();
    expect(screen.getByText('Nœud : c')).toBeInTheDocument();
  });
});
