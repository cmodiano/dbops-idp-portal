/**
 * Tests for ServiceCallStepConfig — Story 57.20, Task 6 + Story 16.9 (notification).
 * Verifies MappingHelpPopover integration, updated placeholders, validation warnings,
 * and notification integration_type support.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ServiceCallStepConfig } from './ServiceCallStepConfig';

vi.mock('../../../hooks/useOutputSchemas', () => ({
  useOutputSchemas: () => ({ availableVariables: [], loading: false, error: null }),
}));
import {
  SERVICE_CALL_OPERATIONS,
  INTEGRATION_LABELS,
  OPERATION_LABELS,
} from './serviceCallConstants';

const baseData = {
  name: null,
  label: 'Service Call',
  step_type: 'service_call' as const,
  step_id: 'sc-1',
  on_success_step_id: null,
  on_error_step_id: null,
  on_success_step_name: null,
  on_error_step_name: null,
  isStartNode: false,
  isEndNode: false,
  integration_type: 'servicenow',
  operation: 'create_change',
  input_mapping: null,
  output_mapping: null,
};

describe('ServiceCallStepConfig — MappingHelpPopover integration (Story 57.20)', () => {
  it('renders input mapping help icon', () => {
    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} />);
    expect(screen.getByLabelText('Aide syntaxe input_mapping')).toBeInTheDocument();
  });

  it('renders output mapping help icon', () => {
    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} />);
    expect(screen.getByLabelText('Aide syntaxe output_mapping')).toBeInTheDocument();
  });

  it('shows input help content with available steps on click', () => {
    const steps = [
      { value: 'step-1', label: 'Étape 1 — Discovery' },
    ];
    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} availableStepOptions={steps} />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe input_mapping'));
    expect(screen.getByText('Syntaxe input_mapping')).toBeInTheDocument();
    expect(screen.getByText('Étape 1 — Discovery')).toBeInTheDocument();
  });

  it('shows output help content with service_call outputs on click', () => {
    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe output_mapping'));
    expect(screen.getByText('Syntaxe output_mapping')).toBeInTheDocument();
    expect(screen.getByText('number')).toBeInTheDocument();
    expect(screen.getByText('sys_id')).toBeInTheDocument();
  });

  it('uses updated placeholder for input_mapping value', () => {
    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} />);
    expect(screen.getByText("Mapping d'entrée (input_mapping)")).toBeInTheDocument();
  });

  it('uses updated placeholder for output_mapping value', () => {
    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} />);
    expect(screen.getByText('Mapping de sortie (output_mapping)')).toBeInTheDocument();
  });
});

describe('ServiceCallStepConfig — validation warnings (Story 57.20, AC5)', () => {
  it('shows warning for invalid step reference', () => {
    const dataWithBadRef = {
      ...baseData,
      input_mapping: { param1: '{{ steps.nonexistent.field }}' },
    };
    const steps = [{ value: 'step-1', label: 'Étape 1' }];
    render(
      <ServiceCallStepConfig data={dataWithBadRef} onUpdate={vi.fn()} availableStepOptions={steps} />
    );
    expect(screen.getByTestId('input-mapping-editor-warning')).toBeInTheDocument();
    expect(screen.getByText(/Référence inconnue : step_id 'nonexistent'/)).toBeInTheDocument();
  });

  it('does not show warning when references are valid', () => {
    const dataWithGoodRef = {
      ...baseData,
      input_mapping: { param1: '{{ steps.step-1.field }}' },
    };
    const steps = [{ value: 'step-1', label: 'Étape 1' }];
    render(
      <ServiceCallStepConfig data={dataWithGoodRef} onUpdate={vi.fn()} availableStepOptions={steps} />
    );
    expect(screen.queryByTestId('input-mapping-editor-warning')).not.toBeInTheDocument();
  });

  it('does not show warning when no template references exist', () => {
    const dataWithPlain = {
      ...baseData,
      input_mapping: { param1: 'plain value' },
    };
    const steps = [{ value: 'step-1', label: 'Étape 1' }];
    render(
      <ServiceCallStepConfig data={dataWithPlain} onUpdate={vi.fn()} availableStepOptions={steps} />
    );
    expect(screen.queryByTestId('input-mapping-editor-warning')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Story 16.9 — notification comme integration_type
// ---------------------------------------------------------------------------

describe('serviceCallConstants — notification (Story 16.9, AC6-7)', () => {
  it('SERVICE_CALL_OPERATIONS inclut notification avec 3 opérations', () => {
    expect(SERVICE_CALL_OPERATIONS.notification).toEqual([
      'send_email',
      'send_teams',
      'notify_execution_event',
    ]);
  });

  it('INTEGRATION_LABELS.notification est "Notification"', () => {
    expect(INTEGRATION_LABELS.notification).toBe('Notification');
  });

  it('OPERATION_LABELS contient les libellés notification', () => {
    expect(OPERATION_LABELS.send_email).toBe('Envoyer un email');
    expect(OPERATION_LABELS.send_teams).toBe('Envoyer un message Teams');
    expect(OPERATION_LABELS.notify_execution_event).toBe("Notifier un événement d'exécution");
  });

  it('non-régression: servicenow, vault, jira toujours présents dans les constantes', () => {
    expect(SERVICE_CALL_OPERATIONS.servicenow).toBeDefined();
    expect(SERVICE_CALL_OPERATIONS.vault).toBeDefined();
    expect(SERVICE_CALL_OPERATIONS.jira).toBeDefined();
    expect(INTEGRATION_LABELS.servicenow).toBe('ServiceNow');
    expect(INTEGRATION_LABELS.vault).toBe('HashiCorp Vault');
    expect(INTEGRATION_LABELS.jira).toBe('Jira');
  });
});

describe('ServiceCallStepConfig — notification integration_type (Story 16.9, AC6-7)', () => {
  const notificationBase = {
    ...baseData,
    integration_type: 'notification',
    operation: 'send_email',
  };

  it('affiche "Notification" comme libellé du type d\'intégration sélectionné', () => {
    render(<ServiceCallStepConfig data={notificationBase} onUpdate={vi.fn()} />);
    expect(screen.getByText('Notification')).toBeInTheDocument();
  });

  it('affiche "Envoyer un email" comme libellé de l\'opération send_email', () => {
    render(<ServiceCallStepConfig data={notificationBase} onUpdate={vi.fn()} />);
    expect(screen.getByText('Envoyer un email')).toBeInTheDocument();
  });

  it('affiche "Envoyer un message Teams" quand send_teams est sélectionné', () => {
    const data = { ...notificationBase, operation: 'send_teams' };
    render(<ServiceCallStepConfig data={data} onUpdate={vi.fn()} />);
    expect(screen.getByText('Envoyer un message Teams')).toBeInTheDocument();
  });

  it("affiche \"Notifier un événement d'exécution\" quand notify_execution_event est sélectionné", () => {
    const data = { ...notificationBase, operation: 'notify_execution_event' };
    render(<ServiceCallStepConfig data={data} onUpdate={vi.fn()} />);
    expect(screen.getByText("Notifier un événement d'exécution")).toBeInTheDocument();
  });

  it('non-régression: servicenow + create_change toujours fonctionnel', () => {
    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} />);
    expect(screen.getByText('ServiceNow')).toBeInTheDocument();
    expect(screen.getByText('Créer un change')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Story 63.3 — VariablePicker intégration
// ---------------------------------------------------------------------------

const dataWithMapping = { ...baseData, input_mapping: { param1: 'value1' } };

describe('ServiceCallStepConfig — VariablePicker (Story 63.3)', () => {
  it('passe workflowId au composant enfant via KeyValueEditor', () => {
    // Le VariablePicker est rendu par KeyValueEditor — avec au moins une ligne input_mapping
    // et workflowId fourni, il doit apparaître dans le DOM (via data-testid du trigger).
    const { container } = render(
      <ServiceCallStepConfig
        data={dataWithMapping}
        onUpdate={vi.fn()}
        workflowId={42}
        availableStepIds={['sc-1', 'sc-2']}
      />
    );
    // Le VariablePicker trigger (CodeOutlined) doit être présent pour chaque ligne
    expect(container.querySelector('[data-testid="variable-picker-trigger"]')).toBeInTheDocument();
  });

  it('ne rend pas le VariablePicker si workflowId est undefined', () => {
    const { container } = render(
      <ServiceCallStepConfig data={dataWithMapping} onUpdate={vi.fn()} />
    );
    expect(container.querySelector('[data-testid="variable-picker-trigger"]')).not.toBeInTheDocument();
  });
});
