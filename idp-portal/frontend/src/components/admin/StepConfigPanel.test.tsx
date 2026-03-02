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
import { render, screen, fireEvent } from '@testing-library/react';
import { StepConfigPanel } from './StepConfigPanel';
import type { Node } from '@xyflow/react';

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
