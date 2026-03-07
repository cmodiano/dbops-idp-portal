/**
 * Tests pour VariablePicker (Story 63.3).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { VariablePicker } from './VariablePicker';
import * as useOutputSchemasModule from '../../../hooks/useOutputSchemas';

vi.mock('../../../hooks/useOutputSchemas');

const mockStep = {
  step_id: 'step-1',
  step_name: 'Créer changement',
  step_type: 'service_call',
  variables: [
    { name: 'change_number', path: '$.number', type: 'string', description: 'Numéro du change' },
    { name: 'sys_id', path: '$.sys_id', type: 'string', description: 'ID système' },
  ],
};

const defaultHookReturn = {
  availableVariables: [mockStep],
  loading: false,
  error: null,
};

describe('VariablePicker — rendu de base', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useOutputSchemasModule.useOutputSchemas).mockReturnValue(defaultHookReturn);
  });

  it('affiche le bouton déclencheur (CodeOutlined)', () => {
    render(
      <VariablePicker workflowId={42} currentStepId="step-2" onSelect={vi.fn()} />
    );
    expect(screen.getByTestId('variable-picker-trigger')).toBeInTheDocument();
  });

  it('ouvre le popover au clic', async () => {
    render(
      <VariablePicker
        workflowId={42}
        currentStepId="step-2"
        onSelect={vi.fn()}
        availableStepIds={['step-1', 'step-2']}
      />
    );
    fireEvent.click(screen.getByTestId('variable-picker-trigger'));
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Rechercher une variable...')).toBeInTheDocument();
    });
  });

  it('affiche "Aucune variable disponible" si workflowId undefined', async () => {
    vi.mocked(useOutputSchemasModule.useOutputSchemas).mockReturnValue({
      availableVariables: [],
      loading: false,
      error: null,
    });
    render(
      <VariablePicker workflowId={undefined} currentStepId="step-1" onSelect={vi.fn()} />
    );
    fireEvent.click(screen.getByTestId('variable-picker-trigger'));
    await waitFor(() => {
      expect(screen.getByText('Aucune variable disponible')).toBeInTheDocument();
    });
  });

  it('affiche le spinner si loading=true', async () => {
    vi.mocked(useOutputSchemasModule.useOutputSchemas).mockReturnValue({
      availableVariables: [],
      loading: true,
      error: null,
    });
    render(
      <VariablePicker workflowId={42} currentStepId="step-2" onSelect={vi.fn()} />
    );
    fireEvent.click(screen.getByTestId('variable-picker-trigger'));
    // Ant Design Spin renders with role="img" or a specific class
    await waitFor(() => {
      expect(document.querySelector('.ant-spin')).toBeInTheDocument();
    });
  });
});

describe('VariablePicker — filtrage des steps', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useOutputSchemasModule.useOutputSchemas).mockReturnValue(defaultHookReturn);
  });

  it('n\'affiche pas le step courant', async () => {
    render(
      <VariablePicker
        workflowId={42}
        currentStepId="step-1"
        onSelect={vi.fn()}
        availableStepIds={['step-1']}
      />
    );
    fireEvent.click(screen.getByTestId('variable-picker-trigger'));
    await waitFor(() => {
      expect(screen.queryByTestId('variable-option-step-1-change_number')).not.toBeInTheDocument();
    });
  });

  it('affiche les variables des steps précédents', async () => {
    render(
      <VariablePicker
        workflowId={42}
        currentStepId="step-2"
        onSelect={vi.fn()}
        availableStepIds={['step-1', 'step-2']}
      />
    );
    fireEvent.click(screen.getByTestId('variable-picker-trigger'));
    await waitFor(() => {
      expect(screen.getByTestId('variable-option-step-1-change_number')).toBeInTheDocument();
    });
  });
});

describe('VariablePicker — recherche/filtrage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useOutputSchemasModule.useOutputSchemas).mockReturnValue(defaultHookReturn);
  });

  it('filtre les variables par nom', async () => {
    render(
      <VariablePicker
        workflowId={42}
        currentStepId="step-2"
        onSelect={vi.fn()}
        availableStepIds={['step-1', 'step-2']}
      />
    );
    fireEvent.click(screen.getByTestId('variable-picker-trigger'));
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Rechercher une variable...')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText('Rechercher une variable...'), {
      target: { value: 'change' },
    });

    expect(screen.getByTestId('variable-option-step-1-change_number')).toBeInTheDocument();
    expect(screen.queryByTestId('variable-option-step-1-sys_id')).not.toBeInTheDocument();
  });
});

describe('VariablePicker — clic sur variable → callback', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useOutputSchemasModule.useOutputSchemas).mockReturnValue(defaultHookReturn);
  });

  it('appelle onSelect avec l\'expression Jinja2 complète', async () => {
    const onSelect = vi.fn();
    render(
      <VariablePicker
        workflowId={42}
        currentStepId="step-2"
        onSelect={onSelect}
        availableStepIds={['step-1', 'step-2']}
      />
    );
    fireEvent.click(screen.getByTestId('variable-picker-trigger'));
    await waitFor(() => {
      expect(screen.getByTestId('variable-option-step-1-change_number')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('variable-option-step-1-change_number'));

    expect(onSelect).toHaveBeenCalledWith('{{ steps.step-1.change_number }}');
  });
});
