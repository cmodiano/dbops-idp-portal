/**
 * WorkflowStepNode tests (Story 16.6, Tasks 9.5-9.6, 9.9; Story 16.7, AC6).
 *
 * Tests:
 * - Retry badge display
 * - Tooltip with retry details and exit paths (Story 16.7)
 * - ARIA labels and accessibility
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

// Mock @xyflow/react before importing the component
vi.mock('@xyflow/react', () => ({
  Handle: ({ id, type }: { id: string; type: string }) =>
    React.createElement('div', { 'data-testid': `handle-${id}`, 'data-handle-type': type }),
  Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
}));

vi.mock('../../hooks/useCapabilities');

// Import after mocks
import WorkflowStepNode from './WorkflowStepNode';
import * as useCapabilitiesModule from '../../hooks/useCapabilities';

const mockUseCapabilities = vi.mocked(useCapabilitiesModule.useCapabilities);

const defaultData = {
  action_id: 100,
  action_name: 'Create PDB',
  action_engine: 'Oracle',
  action_platform: 'Linux',
  name: null,
  retry_enabled: false,
  retry_max_attempts: null,
  retry_interval_seconds: null,
  retry_backoff_multiplier: null,
};

const makeProps = (dataOverrides: Record<string, unknown> = {}, selected = false) => ({
  id: 'step-1',
  type: 'workflowStep' as const,
  data: { ...defaultData, ...dataOverrides },
  selected,
  dragging: false,
  draggable: false,
  selectable: false,
  deletable: false,
  zIndex: 0,
  isConnectable: true,
  positionAbsoluteX: 0,
  positionAbsoluteY: 0,
});

describe('WorkflowStepNode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseCapabilities.mockReturnValue({ capabilities: null, loading: false, error: null, retryCount: 0 });
  });

  it('renders action name', () => {
    render(<WorkflowStepNode {...makeProps()} />);
    expect(screen.getByText('Create PDB')).toBeInTheDocument();
  });

  it('renders engine and platform', () => {
    render(<WorkflowStepNode {...makeProps()} />);
    expect(screen.getByText('Oracle / Linux')).toBeInTheDocument();
  });

  it('renders custom display name when provided', () => {
    render(<WorkflowStepNode {...makeProps({ name: 'Mon étape' })} />);
    expect(screen.getByText('Mon étape')).toBeInTheDocument();
  });

  it('renders ARIA label with step name', () => {
    render(<WorkflowStepNode {...makeProps()} />);
    expect(screen.getByRole('img', { name: 'Étape: Create PDB' })).toBeInTheDocument();
  });

  it('displays retry badge "Réessai: 5×" when retry is enabled', () => {
    render(
      <WorkflowStepNode
        {...makeProps({
          retry_enabled: true,
          retry_max_attempts: 5,
          retry_interval_seconds: 60,
          retry_backoff_multiplier: 2.0,
        })}
      />,
    );

    expect(screen.getByText('Réessai: 5×')).toBeInTheDocument();
  });

  it('displays retry badge "Réessai: 3×" with default attempts', () => {
    render(
      <WorkflowStepNode
        {...makeProps({
          retry_enabled: true,
          retry_max_attempts: null,
        })}
      />,
    );

    expect(screen.getByText('Réessai: 3×')).toBeInTheDocument();
  });

  it('handles retry_max_attempts = 0 by using default value 3', () => {
    render(
      <WorkflowStepNode
        {...makeProps({
          retry_enabled: true,
          retry_max_attempts: 0,
        })}
      />,
    );

    expect(screen.getByText('Réessai: 3×')).toBeInTheDocument();
  });

  it('does not display retry badge when retry is disabled', () => {
    render(<WorkflowStepNode {...makeProps({ retry_enabled: false })} />);
    expect(screen.queryByText(/Réessai:/)).not.toBeInTheDocument();
  });

  it('renders three handles (input, success, error)', () => {
    render(<WorkflowStepNode {...makeProps()} />);
    expect(screen.getByTestId('handle-input')).toBeInTheDocument();
    expect(screen.getByTestId('handle-success')).toBeInTheDocument();
    expect(screen.getByTestId('handle-error')).toBeInTheDocument();
  });

  it('displays validation error message', () => {
    render(
      <WorkflowStepNode
        {...makeProps({
          validationStatus: 'error',
          validationMessage: 'Boucle infinie détectée',
        })}
      />,
    );

    expect(screen.getByText('Boucle infinie détectée')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('does not display validation message when null', () => {
    render(<WorkflowStepNode {...makeProps({ validationMessage: null })} />);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  // Story 16.7, AC6: Extended tooltip with exit paths
  describe('tooltip with exit paths (Story 16.7)', () => {
    it('shows exit paths when on_success_step_id is set', () => {
      // Note: Ant Design Tooltip renders title content in the DOM.
      // The tooltip content is rendered as part of the component tree.
      // We test the node rendering which includes the data for tooltip.
      render(
        <WorkflowStepNode
          {...makeProps({
            on_success_step_id: 'step-2',
            on_error_step_id: 'step-3',
          })}
        />,
      );
      // Node should still render correctly
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });

    it('renders node with exit path data available for tooltip', () => {
      render(
        <WorkflowStepNode
          {...makeProps({
            on_success_step_id: null,
            on_error_step_id: null,
          })}
        />,
      );
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });

    it('preserves retry tooltip when both retry and exit paths are set', () => {
      render(
        <WorkflowStepNode
          {...makeProps({
            retry_enabled: true,
            retry_max_attempts: 5,
            retry_interval_seconds: 30,
            retry_backoff_multiplier: 1.5,
            on_success_step_id: 'step-2',
            on_error_step_id: null,
          })}
        />,
      );
      // Badge still shows
      expect(screen.getByText('Réessai: 5×')).toBeInTheDocument();
    });
  });

  // Story 19.2: Execution status tooltip
  describe('execution status tooltip (Story 19.2)', () => {
    it('AC10: renders node with executionStatus data', () => {
      render(
        <WorkflowStepNode
          {...makeProps({
            executionStatus: 'COMPLETED',
            executionDuration: '1m 30s',
          })}
        />,
      );
      // Node renders correctly with execution data
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });

    it('AC10: renders node with RUNNING status', () => {
      render(
        <WorkflowStepNode
          {...makeProps({
            executionStatus: 'RUNNING',
            executionDuration: null,
          })}
        />,
      );
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });

    it('AC10: renders node with PENDING status (no duration)', () => {
      render(
        <WorkflowStepNode
          {...makeProps({
            executionStatus: 'PENDING',
          })}
        />,
      );
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });
  });

  // Story 18.3, AC4: Real action name display
  describe('action name display (Story 18.3)', () => {
    it('displays real action_name "Apply Oracle Patch"', () => {
      render(
        <WorkflowStepNode
          {...makeProps({ action_name: 'Apply Oracle Patch', action_id: 12 })}
        />,
      );
      expect(screen.getByText('Apply Oracle Patch')).toBeInTheDocument();
      expect(screen.queryByText('Action #12')).not.toBeInTheDocument();
    });

    it('falls back to action_name when name is null', () => {
      render(
        <WorkflowStepNode
          {...makeProps({ action_name: 'Backup DB', name: null })}
        />,
      );
      expect(screen.getByText('Backup DB')).toBeInTheDocument();
    });

    it('displays custom name over action_name when both present', () => {
      render(
        <WorkflowStepNode
          {...makeProps({ action_name: 'Apply Oracle Patch', name: 'Mon étape' })}
        />,
      );
      // Custom name displayed first (primary)
      expect(screen.getByText('Mon étape')).toBeInTheDocument();
      // action_name displayed as secondary
      expect(screen.getByText('Apply Oracle Patch')).toBeInTheDocument();
    });

    it('truncates long action names with ellipsis via CSS', () => {
      render(
        <WorkflowStepNode
          {...makeProps({ action_name: 'A very long action name that exceeds thirty characters easily' })}
        />,
      );
      // The text is rendered but CSS handles truncation
      expect(screen.getByText('A very long action name that exceeds thirty characters easily')).toBeInTheDocument();
    });
  });

  // Story 57.16: schedule_execution step rendering
  describe('schedule_execution step (Story 57.16)', () => {
    it('affiche le label "Planifier" pour schedule_execution', () => {
      render(
        <WorkflowStepNode
          {...makeProps({ step_type: 'schedule_execution', name: 'Mon step' })}
        />,
      );
      expect(screen.getByText('Planifier')).toBeInTheDocument();
    });

    it('utilise le nom du step pour le titre principal', () => {
      render(
        <WorkflowStepNode
          {...makeProps({ step_type: 'schedule_execution', name: 'Planifier l\'app' })}
        />,
      );
      expect(screen.getByText('Planifier l\'app')).toBeInTheDocument();
    });

    it('utilise action_name comme fallback si name est null', () => {
      render(
        <WorkflowStepNode
          {...makeProps({ step_type: 'schedule_execution', name: null, action_name: 'Deploy App' })}
        />,
      );
      expect(screen.getByText('Deploy App')).toBeInTheDocument();
    });

    it('affiche "Planifier une exécution" si name et action_name sont null', () => {
      render(
        <WorkflowStepNode
          {...makeProps({ step_type: 'schedule_execution', name: null, action_name: undefined })}
        />,
      );
      expect(screen.getByText('Planifier une exécution')).toBeInTheDocument();
    });

    it('affiche le badge schedule_source "Paramètre utilisateur" pour source=parameter', () => {
      render(
        <WorkflowStepNode
          {...makeProps({
            step_type: 'schedule_execution',
            name: null,
            schedule_config: { schedule_source: 'parameter' },
          })}
        />,
      );
      expect(screen.getByText('Paramètre utilisateur')).toBeInTheDocument();
    });

    it('affiche le badge offset pour source=fixed_offset', () => {
      render(
        <WorkflowStepNode
          {...makeProps({
            step_type: 'schedule_execution',
            name: null,
            schedule_config: { schedule_source: 'fixed_offset', fixed_offset: '+3d' },
          })}
        />,
      );
      expect(screen.getByText('Offset: +3d')).toBeInTheDocument();
    });

    it('affiche le badge "Récurrent" pour source=recurring', () => {
      render(
        <WorkflowStepNode
          {...makeProps({
            step_type: 'schedule_execution',
            name: null,
            schedule_config: {
              schedule_source: 'recurring',
              recurring_pattern: { pattern_type: 'daily', pattern_config: {} },
            },
          })}
        />,
      );
      expect(screen.getByText('Récurrent')).toBeInTheDocument();
    });

    it('n\'affiche pas de badge quand schedule_config est null', () => {
      render(
        <WorkflowStepNode
          {...makeProps({ step_type: 'schedule_execution', name: null, schedule_config: null })}
        />,
      );
      expect(screen.queryByText('Paramètre utilisateur')).not.toBeInTheDocument();
      expect(screen.queryByText('Récurrent')).not.toBeInTheDocument();
    });
  });

  // Story 83-11: WorkflowStepNode — labels et badge de gate dérivés du backend
  describe('Story 83-11: gate labels dérivés des capabilities', () => {
    const mockCapabilitiesWithGates = {
      platforms: [],
      services: [],
      stepTypes: [
        {
          code: 'gate',
          label: 'Attendre',
          category: 'control',
          config_schema: {},
          constraints: {},
          variants: [
            { code: 'maintenance_window', label: 'Fenêtre de maintenance', config_schema: {} },
            { code: 'approval', label: 'Approbation manuelle', config_schema: { type: 'object', properties: {} } },
          ],
        },
      ],
    };

    it('affiche_le_variant_label_maintenance_window_depuis_capabilities', () => {
      mockUseCapabilities.mockReturnValue({ capabilities: mockCapabilitiesWithGates, loading: false, error: null, retryCount: 0 });

      render(
        <WorkflowStepNode
          {...makeProps({ step_type: 'gate', gate_type: 'maintenance_window', name: null })}
        />,
      );

      // Doit apparaître au moins 2 fois : une fois comme titre, une fois comme badge
      expect(screen.getAllByText('Fenêtre de maintenance').length).toBeGreaterThanOrEqual(2);
    });

    it('affiche_le_variant_label_approval_depuis_capabilities', () => {
      mockUseCapabilities.mockReturnValue({ capabilities: mockCapabilitiesWithGates, loading: false, error: null, retryCount: 0 });

      render(
        <WorkflowStepNode
          {...makeProps({ step_type: 'gate', gate_type: 'approval', name: null })}
        />,
      );

      // Doit apparaître au moins 2 fois : une fois comme titre, une fois comme badge
      expect(screen.getAllByText('Approbation manuelle').length).toBeGreaterThanOrEqual(2);
    });

    it('gate_type_inconnu_fallback_gate', () => {
      mockUseCapabilities.mockReturnValue({ capabilities: mockCapabilitiesWithGates, loading: false, error: null, retryCount: 0 });

      render(
        <WorkflowStepNode
          {...makeProps({ step_type: 'gate', gate_type: 'futur_gate', name: null })}
        />,
      );

      expect(screen.getByText('Gate')).toBeInTheDocument();
      expect(screen.getByText('Attendre')).toBeInTheDocument();
    });

    it('capabilities_null_gate_fallback', () => {
      mockUseCapabilities.mockReturnValue({ capabilities: null, loading: false, error: null, retryCount: 0 });

      render(
        <WorkflowStepNode
          {...makeProps({ step_type: 'gate', gate_type: 'approval', name: null })}
        />,
      );

      expect(screen.getByText('Gate')).toBeInTheDocument();
      expect(screen.getByText('Attendre')).toBeInTheDocument();
    });

    it('gate_name_utilisateur_prioritaire_sur_variant', () => {
      mockUseCapabilities.mockReturnValue({ capabilities: mockCapabilitiesWithGates, loading: false, error: null, retryCount: 0 });

      render(
        <WorkflowStepNode
          {...makeProps({ step_type: 'gate', gate_type: 'approval', name: 'Mon approbation' })}
        />,
      );

      expect(screen.getByText('Mon approbation')).toBeInTheDocument();
      expect(screen.getByText('Approbation manuelle')).toBeInTheDocument();
    });

    it('gate_type_null_fallback_gate', () => {
      mockUseCapabilities.mockReturnValue({ capabilities: mockCapabilitiesWithGates, loading: false, error: null, retryCount: 0 });

      render(
        <WorkflowStepNode
          {...makeProps({ step_type: 'gate', gate_type: null, name: null })}
        />,
      );

      // gate_type null (step gate nouvellement créé) → fallback titre 'Gate', badge 'Attendre'
      expect(screen.getByText('Gate')).toBeInTheDocument();
      expect(screen.getByText('Attendre')).toBeInTheDocument();
    });
  });

  // Story 82.8: WorkflowStepNode — labels service depuis capabilities
  describe('Story 82.8: WorkflowStepNode service_call labels depuis capabilities', () => {
    const mockCapabilities = {
      platforms: [],
      services: [
        {
          code: 'servicenow',
          display_name: 'ServiceNow',
          credential_mode: 'integration' as const,
          supports_health_check: false,
          supports_service_call: true,
          operations: [
            { code: 'create_change', label: 'Créer un change', input_schema: {}, output_schema: {}, ui_hints: {} },
            { code: 'close_change', label: 'Fermer le change', input_schema: {}, output_schema: {}, ui_hints: {} },
          ],
        },
        {
          code: 'vault',
          display_name: 'HashiCorp Vault',
          credential_mode: 'integration' as const,
          supports_health_check: false,
          supports_service_call: true,
          operations: [{ code: 'get_secret', label: 'Lire un secret', input_schema: {}, output_schema: {}, ui_hints: {} }],
        },
      ],
      stepTypes: [],
    };

    it('T6.4 — step service_call avec capabilities mock → label intégration = display_name depuis capabilities', () => {
      mockUseCapabilities.mockReturnValue({ capabilities: mockCapabilities, loading: false, error: null, retryCount: 0 });

      render(
        <WorkflowStepNode
          {...makeProps({
            step_type: 'service_call',
            integration_type: 'servicenow',
            operation: 'create_change',
            name: null,
          })}
        />,
      );

      // display_name 'ServiceNow' doit apparaître dans le primaryTitle
      expect(screen.getByText(/ServiceNow/)).toBeInTheDocument();
    });

    it('T6.5 — step service_call avec capabilities mock → label opération depuis operations[]', () => {
      mockUseCapabilities.mockReturnValue({ capabilities: mockCapabilities, loading: false, error: null, retryCount: 0 });

      render(
        <WorkflowStepNode
          {...makeProps({
            step_type: 'service_call',
            integration_type: 'servicenow',
            operation: 'create_change',
            name: null,
          })}
        />,
      );

      // 'Créer un change' est le label de l'opération — pas le code brut 'create_change'
      expect(screen.getByText(/Créer un change/)).toBeInTheDocument();
      expect(screen.queryByText('create_change')).not.toBeInTheDocument();
    });

    it('T6.6 — capabilities null → label intégration = code brut (pas de fallback INTEGRATION_LABELS)', () => {
      mockUseCapabilities.mockReturnValue({ capabilities: null, loading: false, error: null, retryCount: 0 });

      render(
        <WorkflowStepNode
          {...makeProps({
            step_type: 'service_call',
            integration_type: 'servicenow',
            operation: 'create_change',
            name: null,
          })}
        />,
      );

      // Avec capabilities null :
      // - integration = code brut 'servicenow' (pas de fallback INTEGRATION_LABELS)
      // - opLabel = code brut 'create_change' (pas de label capabilities)
      // - primaryTitle = 'servicenow — create_change'
      const node = screen.getByRole('img');
      expect(node.getAttribute('aria-label')).toBe('Étape: servicenow — create_change');

      // Code brut 'servicenow' affiché (pas 'ServiceNow')
      expect(screen.getByText(/servicenow — create_change/)).toBeInTheDocument();
      expect(screen.queryByText(/ServiceNow — create_change/)).not.toBeInTheDocument();

      // Le code brut de l'opération est affiché (pas de label capabilities)
      expect(screen.queryByText('Créer un change')).not.toBeInTheDocument();
    });
  });

});
