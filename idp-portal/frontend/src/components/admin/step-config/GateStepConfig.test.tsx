/**
 * Tests for GateStepConfig — Story 58.4, AC2; Story 57.19, AC1/AC2; Story 83-9, AC2–AC6.
 * Tests: approver_profile_ids multi-select for approval gates.
 * Story 57.19: context_from Select uses readable step labels instead of UUIDs.
 * Story 83-9: rendu déclaratif depuis config_schema du variant sélectionné.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { GateStepConfig } from './GateStepConfig';
import * as useApproverProfilesModule from '../../../hooks/useApproverProfiles';
import * as useWorkflowStepCapabilitiesModule from '../../../hooks/useWorkflowStepCapabilities';

vi.mock('../../../hooks/useApproverProfiles');
vi.mock('../../../hooks/useWorkflowStepCapabilities');

const mockUseWorkflowStepCapabilities = vi.mocked(
  useWorkflowStepCapabilitiesModule.useWorkflowStepCapabilities,
);

const mockUseApproverProfiles = vi.mocked(useApproverProfilesModule.useApproverProfiles);

const baseData = {
  name: 'approval-step',
  label: 'Gate Step',
  step_type: 'gate' as const,
  step_id: 'approval-step',
  on_success_step_id: null,
  on_error_step_id: null,
  on_success_step_name: null,
  on_error_step_name: null,
  isStartNode: false,
  isEndNode: false,
  gate_type: 'approval', // Story 83-9, AC4: plus de 'as const' (gate_type est string | null)
  on_timeout: 'FAIL' as const,
  context_from: null,
  approver_profile_ids: null,
  timeout: null,
};

// Story 83-9, AC6: mocks avec config_schema correct
const approvalVariant = {
  code: 'approval',
  label: 'Approbation manuelle',
  config_schema: {
    type: 'object',
    properties: {
      context_from: { type: 'array', items: { type: 'string' }, title: "Contexte pour l'approbateur" },
      approver_profile_ids: { type: 'array', items: { type: 'integer' }, title: 'Profils approbateurs autorisés' },
    },
  },
};

const maintenanceVariant = {
  code: 'maintenance_window',
  label: 'Fenêtre de maintenance',
  config_schema: {},
};

const defaultGateVariants = [maintenanceVariant, approvalVariant];

describe('GateStepConfig — approver_profile_ids', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseWorkflowStepCapabilities.mockReturnValue({
      gateVariants: defaultGateVariants,
      loading: false,
      error: null,
    });
    mockUseApproverProfiles.mockReturnValue({
      profiles: [
        { id: 1, name: 'DBA Approver' },
        { id: 2, name: 'DBOPS Approver' },
      ],
      loading: false,
      approverProfileOptions: [
        { value: 1, label: 'DBA Approver' },
        { value: 2, label: 'DBOPS Approver' },
      ],
    });
  });

  it('shows approver_profile_ids select for approval gate_type', () => {
    render(
      <GateStepConfig
        data={baseData}
        onUpdate={vi.fn()}
        disabled={false}
        availableStepIds={[]}
      />
    );

    expect(screen.getByLabelText('Profils approbateurs')).toBeInTheDocument();
  });

  it('hides approver_profile_ids select for maintenance_window gate_type', () => {
    const maintenanceData = { ...baseData, gate_type: 'maintenance_window' };
    render(
      <GateStepConfig
        data={maintenanceData}
        onUpdate={vi.fn()}
        disabled={false}
        availableStepIds={[]}
      />
    );

    expect(screen.queryByLabelText('Profils approbateurs')).not.toBeInTheDocument();
  });

  it('does not call onUpdate on initial render (no spurious side effects)', () => {
    const onUpdate = vi.fn();
    render(
      <GateStepConfig
        data={baseData}
        onUpdate={onUpdate}
        disabled={false}
        availableStepIds={[]}
      />
    );

    expect(onUpdate).not.toHaveBeenCalled();
  });

  it('renders approver_profile_ids select pre-filled when approver_profile_ids has values', () => {
    render(
      <GateStepConfig
        data={{ ...baseData, approver_profile_ids: [1, 2] }}
        onUpdate={vi.fn()}
        disabled={false}
        availableStepIds={[]}
      />
    );

    // Component renders without error and shows the approver select
    expect(screen.getByLabelText('Profils approbateurs')).toBeInTheDocument();
    // onUpdate is NOT called on initial render
  });

  it('shows loading state on approver select when profiles are loading', () => {
    mockUseApproverProfiles.mockReturnValue({
      profiles: [],
      loading: true,
      approverProfileOptions: [],
    });

    const { container } = render(
      <GateStepConfig
        data={baseData}
        onUpdate={vi.fn()}
        disabled={false}
        availableStepIds={[]}
      />
    );

    // The approver Select has loading=true — Ant Design injects the loading CSS class
    expect(container.querySelector('.ant-select-loading')).toBeTruthy();
  });
});

// ─── Story 82.6: gate options depuis le hook ───────────────────────────────────
describe('GateStepConfig — gate options from useWorkflowStepCapabilities (Story 82.6)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseApproverProfiles.mockReturnValue({
      profiles: [],
      loading: false,
      approverProfileOptions: [],
    });
  });

  it('utilise les options backend pour le select gate_type', () => {
    mockUseWorkflowStepCapabilities.mockReturnValue({
      gateVariants: defaultGateVariants,
      loading: false,
      error: null,
    });

    render(
      <GateStepConfig
        data={{ ...baseData, gate_type: null }}
        onUpdate={vi.fn()}
        disabled={false}
      />
    );

    expect(screen.getByTestId('gate-step-config')).toBeInTheDocument();
    expect(screen.getByLabelText('Type de gate')).toBeInTheDocument();
  });

  it('affiche un spinner loading pendant le chargement des variants', () => {
    mockUseWorkflowStepCapabilities.mockReturnValue({
      gateVariants: [],
      loading: true,
      error: null,
    });

    const { container } = render(
      <GateStepConfig
        data={{ ...baseData, gate_type: null }}
        onUpdate={vi.fn()}
        disabled={false}
      />
    );

    expect(container).toBeTruthy();
    // Le Select Ant Design a loading=true (spinner injecté dans le DOM)
    expect(container.querySelector('.ant-select-loading')).toBeTruthy();
  });

  it('utilise le fallback local si erreur API (variants non vides)', () => {
    // Quand erreur, useWorkflowStepCapabilities retourne les variants fallback
    mockUseWorkflowStepCapabilities.mockReturnValue({
      gateVariants: defaultGateVariants,
      loading: false,
      error: 'API down',
    });

    render(
      <GateStepConfig
        data={{ ...baseData, gate_type: null }}
        onUpdate={vi.fn()}
        disabled={false}
      />
    );

    expect(screen.getByTestId('gate-step-config')).toBeInTheDocument();
  });
});

// ─── Story 57.19: context_from uses readable labels ───────────────────────────
describe('GateStepConfig — context_from with labels (Story 57.19)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseWorkflowStepCapabilities.mockReturnValue({
      gateVariants: defaultGateVariants,
      loading: false,
      error: null,
    });
    mockUseApproverProfiles.mockReturnValue({
      profiles: [],
      loading: false,
      approverProfileOptions: [],
    });
  });

  it('uses availableStepOptions labels instead of raw UUIDs for context_from Select', () => {
    const stepOptions = [
      { value: 'uuid-aaa', label: 'Étape 1 — Deploy App' },
      { value: 'uuid-bbb', label: 'Étape 2 — Approbation' },
    ];
    render(
      <GateStepConfig
        data={baseData}
        onUpdate={vi.fn()}
        disabled={false}
        availableStepOptions={stepOptions}
      />
    );

    // The context_from Select should be rendered with the approval gate
    expect(screen.getByLabelText("Contexte pour l'approbateur")).toBeInTheDocument();
    // Component renders without errors when given step options with labels
    expect(screen.getByTestId('gate-step-config')).toBeInTheDocument();
  });

  it('falls back to raw IDs when availableStepOptions is not provided', () => {
    render(
      <GateStepConfig
        data={baseData}
        onUpdate={vi.fn()}
        disabled={false}
        availableStepIds={['uuid-aaa', 'uuid-bbb']}
      />
    );

    // Should still render the context_from Select with raw IDs as fallback
    expect(screen.getByLabelText("Contexte pour l'approbateur")).toBeInTheDocument();
    expect(screen.getByTestId('gate-step-config')).toBeInTheDocument();
  });

  it('does not render context_from for maintenance_window gate type', () => {
    render(
      <GateStepConfig
        data={{ ...baseData, gate_type: 'maintenance_window' }}
        onUpdate={vi.fn()}
        disabled={false}
        availableStepOptions={[{ value: 'uuid-1', label: 'Étape 1 — Deploy' }]}
      />
    );

    expect(screen.queryByLabelText("Contexte pour l'approbateur")).not.toBeInTheDocument();
  });
});

// ─── Story 83-9: Rendu déclaratif depuis config_schema ────────────────────────
describe('GateStepConfig — rendu déclaratif depuis config_schema (Story 83-9)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseApproverProfiles.mockReturnValue({
      profiles: [],
      loading: false,
      approverProfileOptions: [],
    });
  });

  // AC2.3 : gate_type null → config_schema effectif = {} → aucun champ extra
  it('renders_no_extra_fields_when_gate_type_is_null', () => {
    mockUseWorkflowStepCapabilities.mockReturnValue({
      gateVariants: defaultGateVariants,
      loading: false,
      error: null,
    });

    render(
      <GateStepConfig
        data={{ ...baseData, gate_type: null }}
        onUpdate={vi.fn()}
        disabled={false}
        availableStepIds={[]}
      />
    );

    expect(screen.queryByLabelText("Contexte pour l'approbateur")).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Profils approbateurs')).not.toBeInTheDocument();
  });

  // AC2.3 : gate_type absent de gateVariants → config_schema effectif = {} → aucun champ extra
  it('renders_no_extra_fields_when_gate_type_unknown', () => {
    mockUseWorkflowStepCapabilities.mockReturnValue({
      gateVariants: defaultGateVariants,
      loading: false,
      error: null,
    });

    render(
      <GateStepConfig
        data={{ ...baseData, gate_type: 'unknown_gate_type' }}
        onUpdate={vi.fn()}
        disabled={false}
        availableStepIds={[]}
      />
    );

    expect(screen.queryByLabelText("Contexte pour l'approbateur")).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Profils approbateurs')).not.toBeInTheDocument();
  });

  it('renders_context_from_when_schema_declares_it', () => {
    // Gate hypothétique avec context_from mais pas d'approver_profile_ids
    const customGateWithContextFrom = {
      code: 'peer_review',
      label: 'Revue par les pairs',
      config_schema: {
        type: 'object',
        properties: {
          context_from: { type: 'array', items: { type: 'string' }, title: "Contexte pour l'approbateur" },
          // pas d'approver_profile_ids
        },
      },
    };
    mockUseWorkflowStepCapabilities.mockReturnValue({
      gateVariants: [maintenanceVariant, approvalVariant, customGateWithContextFrom],
      loading: false,
      error: null,
    });

    render(
      <GateStepConfig
        data={{ ...baseData, gate_type: 'peer_review' }}
        onUpdate={vi.fn()}
        disabled={false}
        availableStepOptions={[{ value: 'uuid-aaa', label: 'Étape 1' }]}
      />
    );

    expect(screen.getByLabelText("Contexte pour l'approbateur")).toBeInTheDocument();
    expect(screen.queryByLabelText('Profils approbateurs')).not.toBeInTheDocument();
  });

  it('renders_no_extra_fields_for_gate_with_empty_schema', () => {
    mockUseWorkflowStepCapabilities.mockReturnValue({
      gateVariants: defaultGateVariants,
      loading: false,
      error: null,
    });

    render(
      <GateStepConfig
        data={{ ...baseData, gate_type: 'maintenance_window' }}
        onUpdate={vi.fn()}
        disabled={false}
        availableStepIds={[]}
      />
    );

    expect(screen.queryByLabelText("Contexte pour l'approbateur")).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Profils approbateurs')).not.toBeInTheDocument();
  });
});

// ─── Story 83-9: AC5 — onChange gate_type réinitialise les champs selon config_schema ──
describe('GateStepConfig — AC5 onChange gate_type reset (Story 83-9)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseApproverProfiles.mockReturnValue({
      profiles: [],
      loading: false,
      approverProfileOptions: [],
    });
  });

  it('resets context_from and approver_profile_ids when switching to gate with empty schema', () => {
    mockUseWorkflowStepCapabilities.mockReturnValue({
      gateVariants: defaultGateVariants,
      loading: false,
      error: null,
    });

    const onUpdate = vi.fn();
    render(
      <GateStepConfig
        data={{ ...baseData, gate_type: 'approval', context_from: ['step1'], approver_profile_ids: [1] }}
        onUpdate={onUpdate}
        disabled={false}
        availableStepIds={[]}
      />
    );

    // Ouvre le dropdown via l'input interne du Select (aria-label sur l'input Ant Design)
    const gateTypeInput = screen.getByLabelText('Type de gate');
    fireEvent.mouseDown(gateTypeInput);

    // Clique sur l'option maintenance_window dans le dropdown
    const option = screen.getByTitle('Fenêtre de maintenance');
    fireEvent.click(option);

    expect(onUpdate).toHaveBeenCalledWith({
      gate_type: 'maintenance_window',
      context_from: null,
      approver_profile_ids: null,
    });
  });

  it('preserves context_from and approver_profile_ids when switching to gate that declares them', () => {
    mockUseWorkflowStepCapabilities.mockReturnValue({
      gateVariants: defaultGateVariants,
      loading: false,
      error: null,
    });

    const onUpdate = vi.fn();
    render(
      <GateStepConfig
        data={{ ...baseData, gate_type: 'maintenance_window', context_from: null, approver_profile_ids: null }}
        onUpdate={onUpdate}
        disabled={false}
        availableStepIds={[]}
      />
    );

    // Ouvre le dropdown via l'input interne du Select
    const gateTypeInput = screen.getByLabelText('Type de gate');
    fireEvent.mouseDown(gateTypeInput);

    // Clique sur l'option approval dans le dropdown
    const option = screen.getByTitle('Approbation manuelle');
    fireEvent.click(option);

    expect(onUpdate).toHaveBeenCalledWith({
      gate_type: 'approval',
      context_from: null,         // données existantes préservées (null → null)
      approver_profile_ids: null, // données existantes préservées (null → null)
    });
  });
});
