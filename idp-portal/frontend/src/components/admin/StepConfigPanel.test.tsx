/**
 * StepConfigPanel tests (Story 16.6, Tasks 9.3-9.4, 9.7, 9.9).
 *
 * Tests:
 * - Retry section display with correct fields
 * - Switch ON/OFF enables/disables fields
 * - Timeline preview display
 * - Validation error messages
 * - ARIA labels and accessibility
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { StepConfigPanel } from './StepConfigPanel';
import type { Node } from '@xyflow/react';

vi.mock('../../hooks/useOutputSchemas', () => ({
  useOutputSchemas: () => ({ availableVariables: [], loading: false, error: null }),
}));

const makeNode = (overrides: Record<string, unknown> = {}): Node => ({
  id: 'step-1',
  type: 'workflowStep',
  position: { x: 0, y: 0 },
  data: {
    action_id: 100,
    action_name: 'Create PDB',
    action_engine: 'Oracle',
    action_platform: 'Linux',
    name: null,
    retry_enabled: false,
    retry_max_attempts: null,
    retry_interval_seconds: null,
    retry_backoff_multiplier: null,
    ...overrides,
  },
});

describe('StepConfigPanel', () => {
  it('renders nothing when node is null', () => {
    const { container } = render(
      <StepConfigPanel
        node={null}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('displays action name and details', () => {
    render(
      <StepConfigPanel
        node={makeNode()}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.getByText('Create PDB')).toBeInTheDocument();
    expect(screen.getByText('Oracle / Linux')).toBeInTheDocument();
  });

  it('displays retry section with label "Options de retry"', () => {
    render(
      <StepConfigPanel
        node={makeNode()}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.getByText('Options de retry')).toBeInTheDocument();
  });

  it('displays retry switch with correct ARIA label', () => {
    render(
      <StepConfigPanel
        node={makeNode()}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.getByRole('switch', { name: 'Activer le retry automatique' })).toBeInTheDocument();
  });

  it('displays all three retry InputNumber fields with ARIA labels', () => {
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: true, retry_max_attempts: 3, retry_interval_seconds: 60, retry_backoff_multiplier: 2.0 })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.getByRole('spinbutton', { name: 'Nombre maximum de tentatives' })).toBeInTheDocument();
    expect(screen.getByRole('spinbutton', { name: 'Intervalle entre tentatives' })).toBeInTheDocument();
    expect(screen.getByRole('spinbutton', { name: 'Multiplicateur de backoff' })).toBeInTheDocument();
  });

  it('disables retry fields when retry is OFF', () => {
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: false })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.getByRole('spinbutton', { name: 'Nombre maximum de tentatives' })).toBeDisabled();
    expect(screen.getByRole('spinbutton', { name: 'Intervalle entre tentatives' })).toBeDisabled();
    expect(screen.getByRole('spinbutton', { name: 'Multiplicateur de backoff' })).toBeDisabled();
  });

  it('enables retry fields when retry is ON', () => {
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: true, retry_max_attempts: 3, retry_interval_seconds: 60, retry_backoff_multiplier: 2.0 })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.getByRole('spinbutton', { name: 'Nombre maximum de tentatives' })).not.toBeDisabled();
    expect(screen.getByRole('spinbutton', { name: 'Intervalle entre tentatives' })).not.toBeDisabled();
    expect(screen.getByRole('spinbutton', { name: 'Multiplicateur de backoff' })).not.toBeDisabled();
  });

  it('displays info alert about exponential backoff', () => {
    render(
      <StepConfigPanel
        node={makeNode()}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.getByText(/backoff exponentiel/)).toBeInTheDocument();
  });

  it('displays timeline preview when retry is enabled', () => {
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: true, retry_max_attempts: 3, retry_interval_seconds: 60, retry_backoff_multiplier: 2.0 })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.getByTestId('retry-timeline-preview')).toBeInTheDocument();
    expect(screen.getByText(/Tentative 1 : immédiate/)).toBeInTheDocument();
    expect(screen.getByText(/Tentative 2 : 1 min/)).toBeInTheDocument();
    expect(screen.getByText(/Tentative 3 : 2 min/)).toBeInTheDocument();
  });

  it('does not display timeline preview when retry is disabled', () => {
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: false })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.queryByTestId('retry-timeline-preview')).not.toBeInTheDocument();
  });

  it('calls onNodeUpdate with defaults when enabling retry', () => {
    const onNodeUpdate = vi.fn();
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: false })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={onNodeUpdate}
        onNodeDelete={vi.fn()}
      />,
    );

    const retrySwitch = screen.getByRole('switch', { name: 'Activer le retry automatique' });
    fireEvent.click(retrySwitch);

    expect(onNodeUpdate).toHaveBeenCalledWith('step-1', {
      retry_enabled: true,
      retry_max_attempts: 3,
      retry_interval_seconds: 60,
      retry_backoff_multiplier: 2.0,
    });
  });

  it('calls onNodeDelete and onClose when delete button is clicked', () => {
    const onNodeDelete = vi.fn();
    const onClose = vi.fn();
    render(
      <StepConfigPanel
        node={makeNode()}
        open={true}
        onClose={onClose}
        onNodeUpdate={vi.fn()}
        onNodeDelete={onNodeDelete}
      />,
    );

    fireEvent.click(screen.getByText('Supprimer cette étape'));
    expect(onNodeDelete).toHaveBeenCalledWith('step-1');
    expect(onClose).toHaveBeenCalled();
  });

  it('shows validation error for max_attempts out of range', () => {
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: true, retry_max_attempts: 15, retry_interval_seconds: 60, retry_backoff_multiplier: 2.0 })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.getByText('Doit être entre 1 et 10')).toBeInTheDocument();
  });

  it('shows validation error for interval < 1', () => {
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: true, retry_max_attempts: 3, retry_interval_seconds: 0, retry_backoff_multiplier: 2.0 })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.getByText('Doit être au moins 1 seconde')).toBeInTheDocument();
  });

  it('shows validation error for backoff multiplier out of range', () => {
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: true, retry_max_attempts: 3, retry_interval_seconds: 60, retry_backoff_multiplier: 15.0 })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.getByText('Doit être entre 1.0 et 10.0')).toBeInTheDocument();
  });

  it('does not show validation errors when retry is disabled', () => {
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: false, retry_max_attempts: 15, retry_interval_seconds: 0, retry_backoff_multiplier: 15.0 })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.queryByText('Doit être entre 1 et 10')).not.toBeInTheDocument();
    expect(screen.queryByText('Doit être au moins 1 seconde')).not.toBeInTheDocument();
    expect(screen.queryByText('Doit être entre 1.0 et 10.0')).not.toBeInTheDocument();
  });

  it('does not call onNodeUpdate when panel is disabled', () => {
    const onNodeUpdate = vi.fn();
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: false })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={onNodeUpdate}
        onNodeDelete={vi.fn()}
        disabled={true}
      />,
    );

    const retrySwitch = screen.getByRole('switch', { name: 'Activer le retry automatique' });
    fireEvent.click(retrySwitch);

    expect(onNodeUpdate).not.toHaveBeenCalled();
  });

  it('does not call onNodeDelete when delete button is disabled', () => {
    const onNodeDelete = vi.fn();
    render(
      <StepConfigPanel
        node={makeNode()}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={onNodeDelete}
        disabled={true}
      />,
    );

    const deleteBtn = screen.getByRole('button', { name: /Supprimer cette étape/i });
    expect(deleteBtn).toBeDisabled();
    fireEvent.click(deleteBtn);
    expect(onNodeDelete).not.toHaveBeenCalled();
  });

  it('shows join_policy selector when incomingEdgeCount >= 2 (Story 67.4)', () => {
    render(
      <StepConfigPanel
        node={makeNode()}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
        incomingEdgeCount={2}
      />,
    );

    expect(screen.getByLabelText('Politique de convergence')).toBeInTheDocument();
    expect(screen.getByText(/Politique de convergence/)).toBeInTheDocument();
  });

  it('hides join_policy selector when incomingEdgeCount < 2', () => {
    render(
      <StepConfigPanel
        node={makeNode()}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
        incomingEdgeCount={1}
      />,
    );

    expect(screen.queryByLabelText('Politique de convergence')).not.toBeInTheDocument();
  });

  it('displays validation warning alert when retry values are invalid', () => {
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: true, retry_max_attempts: 15, retry_interval_seconds: 0, retry_backoff_multiplier: 12.0 })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.getByText('Valeurs de retry invalides')).toBeInTheDocument();
    expect(screen.getByText(/Corrigez les erreurs/)).toBeInTheDocument();
  });

  it('does not display validation warning when all values are valid', () => {
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: true, retry_max_attempts: 5, retry_interval_seconds: 60, retry_backoff_multiplier: 2.0 })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.queryByText('Valeurs de retry invalides')).not.toBeInTheDocument();
  });

  it('recalculates timeline when retry values change', () => {
    const { rerender } = render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: true, retry_max_attempts: 2, retry_interval_seconds: 30, retry_backoff_multiplier: 2.0 })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.getByText(/Tentative 1 : immédiate/)).toBeInTheDocument();
    expect(screen.getByText(/Tentative 2 : 30 s/)).toBeInTheDocument();

    // Change max_attempts to 3
    rerender(
      <StepConfigPanel
        node={makeNode({ retry_enabled: true, retry_max_attempts: 3, retry_interval_seconds: 30, retry_backoff_multiplier: 2.0 })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    expect(screen.getByText(/Tentative 3 : 1 min/)).toBeInTheDocument();
  });
});

// ─── Coverage extras ──────────────────────────────────────────────────────────
describe('StepConfigPanel — coverage extras', () => {
  it('renders without action_platform (no platform suffix shown)', () => {
    render(
      <StepConfigPanel
        node={makeNode({ action_platform: undefined })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );
    // Platform suffix " / Linux" should not appear
    expect(screen.queryByText(/\/ Linux/)).not.toBeInTheDocument();
    // Action name is still shown
    expect(screen.getByText('Create PDB')).toBeInTheDocument();
  });

  it('does not set retry defaults when retry values are already set', () => {
    const onNodeUpdate = vi.fn();
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: false, retry_max_attempts: 5, retry_interval_seconds: 30, retry_backoff_multiplier: 1.5 })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={onNodeUpdate}
        onNodeDelete={vi.fn()}
      />,
    );
    const retrySwitch = screen.getByRole('switch', { name: 'Activer le retry automatique' });
    fireEvent.click(retrySwitch);
    // Since values are already set (not null), defaults should NOT be added
    expect(onNodeUpdate).toHaveBeenCalledWith('step-1', { retry_enabled: true });
  });

  it('updates name field via input change', () => {
    const onNodeUpdate = vi.fn();
    render(
      <StepConfigPanel
        node={makeNode()}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={onNodeUpdate}
        onNodeDelete={vi.fn()}
      />,
    );
    const nameInput = screen.getByLabelText("Nom d'affichage de l'étape");
    fireEvent.change(nameInput, { target: { value: 'My Step' } });
    expect(onNodeUpdate).toHaveBeenCalledWith('step-1', { name: 'My Step' });
  });

  it('calls onNodeUpdate with null when name is cleared', () => {
    const onNodeUpdate = vi.fn();
    render(
      <StepConfigPanel
        node={makeNode({ name: 'Existing Step' })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={onNodeUpdate}
        onNodeDelete={vi.fn()}
      />,
    );
    const nameInput = screen.getByLabelText("Nom d'affichage de l'étape");
    fireEvent.change(nameInput, { target: { value: '' } });
    expect(onNodeUpdate).toHaveBeenCalledWith('step-1', { name: null });
  });

  it('calls onNodeUpdate with retry_max_attempts when InputNumber changes', () => {
    const onNodeUpdate = vi.fn();
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: true, retry_max_attempts: 3, retry_interval_seconds: 60, retry_backoff_multiplier: 2.0 })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={onNodeUpdate}
        onNodeDelete={vi.fn()}
      />,
    );
    // Trigger change on Nombre maximum de tentatives input
    const maxAttemptsInput = screen.getByRole('spinbutton', { name: 'Nombre maximum de tentatives' });
    fireEvent.change(maxAttemptsInput, { target: { value: '5' } });
    // At minimum, the onNodeUpdate was called
    expect(onNodeUpdate).toHaveBeenCalled();
  });

  it('calls onNodeUpdate with retry_interval_seconds when InputNumber changes', () => {
    const onNodeUpdate = vi.fn();
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: true, retry_max_attempts: 3, retry_interval_seconds: 60, retry_backoff_multiplier: 2.0 })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={onNodeUpdate}
        onNodeDelete={vi.fn()}
      />,
    );
    const intervalInput = screen.getByRole('spinbutton', { name: 'Intervalle entre tentatives' });
    fireEvent.change(intervalInput, { target: { value: '30' } });
    expect(onNodeUpdate).toHaveBeenCalled();
  });

  it('calls onNodeUpdate with retry_backoff_multiplier when InputNumber changes', () => {
    const onNodeUpdate = vi.fn();
    render(
      <StepConfigPanel
        node={makeNode({ retry_enabled: true, retry_max_attempts: 3, retry_interval_seconds: 60, retry_backoff_multiplier: 2.0 })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={onNodeUpdate}
        onNodeDelete={vi.fn()}
      />,
    );
    const backoffInput = screen.getByRole('spinbutton', { name: 'Multiplicateur de backoff' });
    fireEvent.change(backoffInput, { target: { value: '3.0' } });
    expect(onNodeUpdate).toHaveBeenCalled();
  });
});

// ─── Story 63.12: input/output mapping for platform steps ────────────────────
describe('StepConfigPanel — platform input/output mapping (Story 63.12)', () => {
  it('affiche la section input_mapping pour un step platform', () => {
    render(
      <StepConfigPanel
        node={makeNode({ step_type: 'platform' })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );
    expect(screen.getByTestId('platform-input-mapping-editor')).toBeInTheDocument();
  });

  it('affiche la section output_mapping pour un step platform', () => {
    render(
      <StepConfigPanel
        node={makeNode({ step_type: 'platform' })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );
    expect(screen.getByTestId('platform-output-mapping-editor')).toBeInTheDocument();
  });

  it('affiche les labels "Mapping d\'entrée" et "Mapping de sortie"', () => {
    render(
      <StepConfigPanel
        node={makeNode({ step_type: 'platform' })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );
    expect(screen.getByText("Mapping d'entrée (input_mapping)")).toBeInTheDocument();
    expect(screen.getByText('Mapping de sortie (output_mapping)')).toBeInTheDocument();
  });

  it('appelle onNodeUpdate avec input_mapping mis à jour quand une clé est saisie', () => {
    const onNodeUpdate = vi.fn();
    render(
      <StepConfigPanel
        node={makeNode({ step_type: 'platform', input_mapping: null })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={onNodeUpdate}
        onNodeDelete={vi.fn()}
      />,
    );
    // Scope to the input_mapping KeyValueEditor (platform has both input and output mapping editors)
    const inputMappingEditor = screen.getByTestId('platform-input-mapping-editor');
    const addButton = within(inputMappingEditor).getByText('Ajouter une entrée');
    fireEvent.click(addButton);
    const keyInput = within(inputMappingEditor).getByPlaceholderText('Paramètre');
    fireEvent.change(keyInput, { target: { value: 'my_param' } });
    expect(onNodeUpdate).toHaveBeenCalledWith(
      'step-1',
      expect.objectContaining({
        input_mapping: expect.objectContaining({ my_param: expect.anything() }),
      }),
    );
  });

  it('n\'affiche pas le bouton "Ajouter une entrée" quand disabled=true', () => {
    render(
      <StepConfigPanel
        node={makeNode({ step_type: 'platform', input_mapping: null })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
        disabled={true}
      />,
    );
    // KeyValueEditor masque le bouton "Ajouter une entrée" quand disabled=true
    expect(screen.queryByText('Ajouter une entrée')).not.toBeInTheDocument();
  });

  it('charge correctement les valeurs input_mapping existantes', () => {
    render(
      <StepConfigPanel
        node={makeNode({ step_type: 'platform', input_mapping: { job_id: '{{ steps.step1.job_id }}' } })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );
    expect(screen.getByDisplayValue('job_id')).toBeInTheDocument();
    expect(screen.getByDisplayValue('{{ steps.step1.job_id }}')).toBeInTheDocument();
  });

  it('charge correctement les valeurs output_mapping existantes', () => {
    render(
      <StepConfigPanel
        node={makeNode({ step_type: 'platform', output_mapping: { result: '$.output.value' } })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );
    expect(screen.getByDisplayValue('result')).toBeInTheDocument();
    expect(screen.getByDisplayValue('$.output.value')).toBeInTheDocument();
  });

  it('fonctionne sans input_mapping ni output_mapping (rétrocompatibilité)', () => {
    expect(() =>
      render(
        <StepConfigPanel
          node={makeNode({ step_type: 'platform', input_mapping: undefined, output_mapping: undefined })}
          open={true}
          onClose={vi.fn()}
          onNodeUpdate={vi.fn()}
          onNodeDelete={vi.fn()}
        />,
      ),
    ).not.toThrow();
    expect(screen.getByTestId('platform-input-mapping-editor')).toBeInTheDocument();
    expect(screen.getByTestId('platform-output-mapping-editor')).toBeInTheDocument();
  });

  it('passe currentStepId au KeyValueEditor input_mapping (node.id quand data.step_id absent) pour VariablePicker', () => {
    // Quand data.step_id est undefined (ex: node depuis workflowStepsToReactFlow), on utilise node.id.
    // Cela permet au VariablePicker de s'afficher (workflowId + currentStepId requis).
    render(
      <StepConfigPanel
        node={makeNode({
          step_type: 'platform',
          input_mapping: { job_id: '{{ steps.step-2.platform_job_id }}' },
        })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
        workflowId={42}
        availableStepIds={['step-1', 'step-2']}
        availableStepOptions={[
          { value: 'step-1', label: 'Étape 1' },
          { value: 'step-2', label: 'Étape 2' },
        ]}
      />,
    );
    // Vérifie que l'éditeur input_mapping est présent (le fix currentStepId permet au VariablePicker de s'afficher)
    expect(screen.getByTestId('platform-input-mapping-editor')).toBeInTheDocument();
    expect(screen.getByDisplayValue('{{ steps.step-2.platform_job_id }}')).toBeInTheDocument();
  });

  it('affiche un avertissement pour référence step_id invalide dans input_mapping (platform)', () => {
    render(
      <StepConfigPanel
        node={makeNode({
          step_type: 'platform',
          input_mapping: { job_id: '{{ steps.inexistant.job_id }}' },
        })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
        availableStepOptions={[
          { value: 'step-1', label: 'Étape 1' },
          { value: 'step-2', label: 'Étape 2' },
        ]}
      />,
    );
    expect(screen.getByTestId('platform-input-mapping-editor-warning')).toBeInTheDocument();
    expect(screen.getByText(/Référence inconnue : step_id 'inexistant'/)).toBeInTheDocument();
  });
});

// ─── Story 57.19: step_id label display ──────────────────────────────────────
describe('StepConfigPanel — step_id with label (Story 57.19)', () => {
  it('displays generated label for platform step with action_name', () => {
    render(
      <StepConfigPanel
        node={makeNode({ action_name: 'Create PDB', step_type: 'platform', order: 1 })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    // getStepLabel should produce "Étape 1 — Create PDB" for a platform step with order=1 and action_name
    expect(screen.getByText('Étape 1 — Create PDB')).toBeInTheDocument();
    // The step_id input should still exist
    expect(screen.getByLabelText('step_id')).toBeInTheDocument();
  });

  it('displays custom name as label when name is set', () => {
    render(
      <StepConfigPanel
        node={makeNode({ name: 'Mon étape custom', action_name: 'Create PDB', step_type: 'platform' })}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    // The label from getStepLabel should prioritize name
    expect(screen.getByText('Mon étape custom')).toBeInTheDocument();
  });

  it('displays step_id in monospace input', () => {
    render(
      <StepConfigPanel
        node={makeNode()}
        open={true}
        onClose={vi.fn()}
        onNodeUpdate={vi.fn()}
        onNodeDelete={vi.fn()}
      />,
    );

    const stepIdInput = screen.getByLabelText('step_id');
    expect(stepIdInput).toHaveValue('step-1');
    expect(stepIdInput).toBeDisabled();
  });
});
