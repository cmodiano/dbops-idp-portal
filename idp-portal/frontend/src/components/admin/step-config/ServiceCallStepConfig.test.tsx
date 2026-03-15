/**
 * Tests for ServiceCallStepConfig — Story 57.20, Task 6 + Story 16.9 (notification).
 * Verifies MappingHelpPopover integration, updated placeholders, validation warnings,
 * and notification integration_type support.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ServiceCallStepConfig } from './ServiceCallStepConfig';
import * as useCapabilitiesModule from '../../../hooks/useCapabilities';

vi.mock('../../../hooks/useOutputSchemas', () => ({
  useOutputSchemas: () => ({ availableVariables: [], loading: false, error: null }),
}));
vi.mock('../../../hooks/useCapabilities');

const mockUseCapabilities = vi.mocked(useCapabilitiesModule.useCapabilities);

// Story 82.7: Mock capabilities with ServiceOperation[] (code + label)
const mockCapabilitiesWithServices = {
  platforms: [],
  services: [
    {
      code: 'servicenow', display_name: 'ServiceNow', credential_mode: 'integration' as const, supports_health_check: false,
      operations: [
        { code: 'cancel_change', label: 'Annuler le change' },
        { code: 'close_change', label: 'Fermer le change' },
        { code: 'create_change', label: 'Créer un change' },
        { code: 'get_change_status', label: 'Statut du change' },
        { code: 'update_change', label: 'Mettre à jour le change' },
      ],
    },
    {
      code: 'vault', display_name: 'HashiCorp Vault', credential_mode: 'integration' as const, supports_health_check: false,
      operations: [{ code: 'get_secret', label: 'Lire un secret' }],
    },
    {
      code: 'jira', display_name: 'Jira', credential_mode: 'integration' as const, supports_health_check: false,
      operations: [
        { code: 'create_issue', label: 'Créer un ticket' },
        { code: 'get_issue', label: 'Lire le ticket' },
        { code: 'update_issue', label: 'Mettre à jour le ticket' },
      ],
    },
    {
      code: 'notification', display_name: 'Notification', credential_mode: 'credential_free' as const, supports_health_check: false,
      operations: [
        { code: 'notify_execution_event', label: "Notifier un événement d'exécution" },
        { code: 'send_email', label: 'Envoyer un email' },
        { code: 'send_teams', label: 'Envoyer un message Teams' },
      ],
    },
  ],
  stepTypes: [],
};

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
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseCapabilities.mockReturnValue({ capabilities: mockCapabilitiesWithServices, loading: false, error: null });
  });

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
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseCapabilities.mockReturnValue({ capabilities: mockCapabilitiesWithServices, loading: false, error: null });
  });

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


describe('ServiceCallStepConfig — notification integration_type (Story 16.9, AC6-7)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseCapabilities.mockReturnValue({ capabilities: mockCapabilitiesWithServices, loading: false, error: null });
  });

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
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseCapabilities.mockReturnValue({ capabilities: mockCapabilitiesWithServices, loading: false, error: null });
  });

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

// ---------------------------------------------------------------------------
// Story 63.4 — NotificationTemplateEditor intégration
// ---------------------------------------------------------------------------

describe('ServiceCallStepConfig — NotificationTemplateEditor (Story 63.4, AC4)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseCapabilities.mockReturnValue({ capabilities: mockCapabilitiesWithServices, loading: false, error: null });
  });

  it('rend NotificationTemplateEditor pour notification send_email', () => {
    const data = {
      ...baseData,
      integration_type: 'notification',
      operation: 'send_email',
      input_mapping: null,
    };
    const { container } = render(<ServiceCallStepConfig data={data} onUpdate={vi.fn()} />);
    expect(
      container.querySelector('[data-testid="notification-template-editor-email"]'),
    ).toBeInTheDocument();
    expect(screen.queryByTestId('input-mapping-editor')).not.toBeInTheDocument();
  });

  it('conserve le KeyValueEditor générique pour notify_execution_event', () => {
    const data = {
      ...baseData,
      integration_type: 'notification',
      operation: 'notify_execution_event',
      input_mapping: null,
    };
    const { container } = render(<ServiceCallStepConfig data={data} onUpdate={vi.fn()} />);
    expect(screen.getByTestId('input-mapping-editor')).toBeInTheDocument();
    expect(
      container.querySelector('[data-testid="notification-template-editor-email"]'),
    ).not.toBeInTheDocument();
    expect(
      container.querySelector('[data-testid="notification-template-editor-teams"]'),
    ).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Story 82.6 — useCapabilities integration (T7.6)
// ---------------------------------------------------------------------------

describe('ServiceCallStepConfig — useCapabilities integration (Story 82.6)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('utilise les services du backend pour les options integration_type', () => {
    mockUseCapabilities.mockReturnValue({
      capabilities: mockCapabilitiesWithServices,
      loading: false,
      error: null,
    });

    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} />);

    // ServiceNow doit apparaître via les données backend
    expect(screen.getByText('ServiceNow')).toBeInTheDocument();
  });

  it('capabilities null → integrationTypeOptions = [] (pas de fallback INTEGRATION_LABELS)', () => {
    mockUseCapabilities.mockReturnValue({
      capabilities: null,
      loading: false,
      error: 'API down',
    });

    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} />);

    // Pas de fallback INTEGRATION_LABELS — options vides, 'ServiceNow' non affiché
    expect(screen.queryByText('ServiceNow')).not.toBeInTheDocument();
    // Le composant se rend sans erreur
    expect(screen.getByTestId('service-call-step-config')).toBeInTheDocument();
  });

  it('capabilities null → availableOperations = [] (pas de fallback SERVICE_CALL_OPERATIONS)', () => {
    mockUseCapabilities.mockReturnValue({
      capabilities: null,
      loading: false,
      error: null,
    });

    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} />);

    // Le composant rend sans erreur
    expect(screen.getByTestId('service-call-step-config')).toBeInTheDocument();
    // Pas de liste d'opérations locales — l'opération sélectionnée peut apparaître comme valeur brute
    expect(screen.queryByText('Créer un change')).not.toBeInTheDocument();
  });

  it('integration_type absent des services backend → availableOperations = [] (pas de fallback local)', () => {
    // Backend chargé mais ne contient pas "servicenow" → liste vide (pas de fallback)
    mockUseCapabilities.mockReturnValue({
      capabilities: {
        platforms: [],
        services: [
          { code: 'vault', display_name: 'HashiCorp Vault', credential_mode: 'integration' as const, operations: [{ code: 'get_secret', label: 'Lire un secret' }], supports_health_check: false },
        ],
        stepTypes: [],
      },
      loading: false,
      error: null,
    });

    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} />);

    // servicenow absent du backend → availableOperations = [] → pas de labels FR
    expect(screen.queryByText('Créer un change')).not.toBeInTheDocument();
    expect(screen.getByTestId('service-call-step-config')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Story 82.7 — T8.5: labels opérations depuis {code, label} du hook
// ---------------------------------------------------------------------------

describe('ServiceCallStepConfig — operation labels depuis ServiceOperation (Story 82.7, T8.5)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseCapabilities.mockReturnValue({ capabilities: mockCapabilitiesWithServices, loading: false, error: null });
  });

  it('label opération vient de {code, label} du hook — create_change → Créer un change', () => {
    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} />);
    // Le select opération affiche le label FR de l'objet ServiceOperation
    expect(screen.getByText('Créer un change')).toBeInTheDocument();
  });

  it('label opération send_email → Envoyer un email via ServiceOperation du hook', () => {
    const data = { ...baseData, integration_type: 'notification', operation: 'send_email' };
    render(<ServiceCallStepConfig data={data} onUpdate={vi.fn()} />);
    expect(screen.getByText('Envoyer un email')).toBeInTheDocument();
  });

  it('label opération get_secret → Lire un secret via ServiceOperation du hook', () => {
    const data = { ...baseData, integration_type: 'vault', operation: 'get_secret' };
    render(<ServiceCallStepConfig data={data} onUpdate={vi.fn()} />);
    expect(screen.getByText('Lire un secret')).toBeInTheDocument();
  });

  it('label opération create_issue → Créer un ticket via ServiceOperation du hook', () => {
    const data = { ...baseData, integration_type: 'jira', operation: 'create_issue' };
    render(<ServiceCallStepConfig data={data} onUpdate={vi.fn()} />);
    expect(screen.getByText('Créer un ticket')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Story 82.9 — T8.2: non-régression nouveau plugin visible partout
// ---------------------------------------------------------------------------

describe('ServiceCallStepConfig — T8.2: nouveau service dans capabilities → visible dans integrationTypeOptions', () => {
  it('T8.2 — nouveau service dans capabilities mock → apparaît dans integrationTypeOptions sans modification code', () => {
    const capabilitiesWithNewService = {
      platforms: [],
      services: [
        {
          code: 'my_new_service',
          display_name: 'My New Service',
          credential_mode: 'integration' as const,
          supports_health_check: false,
          operations: [],
        },
      ],
      stepTypes: [],
    };
    mockUseCapabilities.mockReturnValue({ capabilities: capabilitiesWithNewService, loading: false, error: null });

    const data = { ...baseData, integration_type: 'my_new_service', operation: null };
    render(<ServiceCallStepConfig data={data} onUpdate={vi.fn()} />);

    // Le nouveau service doit apparaître sans aucune modification du code frontend
    expect(screen.getByText('My New Service')).toBeInTheDocument();
  });
});
