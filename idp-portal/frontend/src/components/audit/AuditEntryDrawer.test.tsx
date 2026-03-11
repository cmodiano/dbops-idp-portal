/**
 * Tests for AuditEntryDrawer component.
 * Story 43.5 — section "Approbation" pour EXECUTION_APPROVED.
 * Story 43.7 — entity-type conditional rendering, Détails section.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import dayjs from 'dayjs';
import { AuditEntryDrawer } from './AuditEntryDrawer';
import type { AuditExecutionEntry, ExecutionResponse, ExecutionStepResponse } from '../../types/api';

vi.mock('../execution/ExecutionTimeline', () => ({
  ExecutionTimeline: () => <div data-testid="execution-timeline" />,
}));

const executionEntry: AuditExecutionEntry = {
  id: 1,
  timestamp: '2026-02-24T10:00:00Z',
  user_id: 'user-42',
  user_name: 'Jean Dupont',
  action_type: 'EXECUTION_COMPLETED',
  entity_type: 'execution',
  entity_id: 999,
  details: { environment: 'PROD', status: 'COMPLETED', parameters: { target: 'server-01' } },
  ip_address: '10.0.0.1',
  correlation_id: 'corr-abc',
  derived_status: 'success',
};

const actionEntry: AuditExecutionEntry = {
  ...executionEntry,
  action_type: 'ACTION_PUBLISHED',
  entity_type: 'action',
  entity_id: 42,
  details: { action_name: 'Deploy Prod', previous_status: 'DRAFT', new_status: 'PUBLISHED' },
  derived_status: 'unknown',
};

const mockApprovedEntry: AuditExecutionEntry = {
  id: 1,
  entity_id: 123,
  item_type: 'action',
  user_id: '42',
  user_name: 'Jean Dupont',
  action_name: 'Deploy Prod',
  derived_status: 'success',
  timestamp: '2025-01-15T10:30:00Z',
  action_type: 'EXECUTION_APPROVED',
  entity_type: 'execution',
  ip_address: null,
  correlation_id: null,
  details: {
    action_id: 5,
    environment: 'prod',
    servicenow_change_id: undefined,
  },
};

const mockExecution: ExecutionResponse = {
  id: 123,
  action_id: 5,
  action_name: 'Deploy Prod',
  user_id: 10,
  environment: 'prod',
  parameters: null,
  status: 'COMPLETED',
  servicenow_change_id: null,
  started_at: '2025-01-15T10:00:00Z',
  completed_at: '2025-01-15T10:30:00Z',
  created_at: '2025-01-15T09:55:00Z',
};

const mockSteps: ExecutionStepResponse[] = [];

/** Steps with approval info for tests that need approval data (Story 71.2). */
const mockStepsWithApproval: ExecutionStepResponse[] = [
  {
    id: 1,
    execution_id: 123,
    step_order: 1,
    step_name: 'Approval Gate',
    step_type: 'platform',
    status: 'COMPLETED',
    started_at: '2025-01-15T09:57:00Z',
    completed_at: '2025-01-15T09:58:00Z',
    output: null,
    platform_job_id: null,
    error_message: null,
    approved_by_id: 10,
    approved_at: '2025-01-15T09:58:00Z',
    approval_comment: 'Approuvé avec réserves',
  },
];

const defaultProps = {
  open: true,
  entry: mockApprovedEntry,
  execution: null,
  steps: mockSteps,
  loading: false,
  error: null,
  onClose: vi.fn(),
};

describe('AuditEntryDrawer', () => {
  it('test_drawer_shows_approval_section_for_execution_approved — section Approbation présente pour EXECUTION_APPROVED', () => {
    render(<AuditEntryDrawer {...defaultProps} />);
    expect(screen.getByText('Approbation')).toBeInTheDocument();
    // Jean Dupont apparaît dans "Qui" et "Approuvé par" — au moins 2 occurrences
    expect(screen.getAllByText('Jean Dupont').length).toBeGreaterThanOrEqual(2);
  });

  it('test_drawer_shows_approval_comment_when_available — affiche le commentaire si disponible', () => {
    render(<AuditEntryDrawer {...defaultProps} execution={mockExecution} steps={mockStepsWithApproval} />);
    expect(screen.getByText('Approuvé avec réserves')).toBeInTheDocument();
  });

  it('test_drawer_shows_approval_date_when_available — affiche la date d\'approbation si disponible', () => {
    render(<AuditEntryDrawer {...defaultProps} execution={mockExecution} steps={mockStepsWithApproval} />);
    const expectedDate = dayjs(mockStepsWithApproval[0].approved_at!).format('DD/MM/YYYY HH:mm');
    expect(screen.getByText(expectedDate)).toBeInTheDocument();
  });

  it('test_drawer_no_approval_section_for_other_action_types — pas de section Approbation pour EXECUTION_SUBMITTED', () => {
    const submittedEntry: AuditExecutionEntry = {
      ...mockApprovedEntry,
      action_type: 'EXECUTION_SUBMITTED',
    };
    render(<AuditEntryDrawer {...defaultProps} entry={submittedEntry} />);
    expect(screen.queryByText('Approbation')).not.toBeInTheDocument();
  });

  it('test_drawer_approval_section_minimal_without_execution — affiche au minimum Approuvé par sans exécution chargée', () => {
    render(<AuditEntryDrawer {...defaultProps} execution={null} />);
    expect(screen.getByText('Approbation')).toBeInTheDocument();
    expect(screen.getAllByText('Jean Dupont').length).toBeGreaterThanOrEqual(1);
  });

  // Story 43.7 — entity-type conditional rendering
  it('affiche Environnement et Résultat pour une entrée execution', () => {
    render(<AuditEntryDrawer {...defaultProps} entry={executionEntry} />);
    expect(screen.getByText('Environnement')).toBeInTheDocument();
    expect(screen.getByText('Résultat')).toBeInTheDocument();
  });

  it('masque Environnement et Résultat pour une entrée action', () => {
    render(<AuditEntryDrawer {...defaultProps} entry={actionEntry} />);
    expect(screen.queryByText('Environnement')).not.toBeInTheDocument();
    expect(screen.queryByText('Résultat')).not.toBeInTheDocument();
  });

  it('affiche la section Détails pour une entrée action avec details', () => {
    render(<AuditEntryDrawer {...defaultProps} entry={actionEntry} />);
    expect(screen.getByText('Détails')).toBeInTheDocument();
    expect(screen.getAllByText('Deploy Prod').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Nom de l\'action')).toBeInTheDocument();
  });

  it('affiche le titre dynamique selon entity_type', () => {
    render(<AuditEntryDrawer {...defaultProps} entry={actionEntry} />);
    expect(screen.getByText(/Détail — Action/i)).toBeInTheDocument();
  });

  it('affiche les champs communs (Qui, Quoi, Quand) pour tous les types', () => {
    render(<AuditEntryDrawer {...defaultProps} entry={actionEntry} />);
    expect(screen.getByText('Qui')).toBeInTheDocument();
    expect(screen.getByText('Quoi')).toBeInTheDocument();
    expect(screen.getByText('Quand')).toBeInTheDocument();
  });

  it('affiche la section Détails pour une entrée execution avec champs additionnels (Story 72.3)', () => {
    const entryWithExtraDetails: AuditExecutionEntry = {
      ...executionEntry,
      details: {
        ...executionEntry.details,
        step_order: 2,
        step_type: 'platform',
        referenced_action_name: 'Patch Oracle',
      },
    };
    render(<AuditEntryDrawer {...defaultProps} entry={entryWithExtraDetails} />);
    expect(screen.getByText('Détails')).toBeInTheDocument();
    expect(screen.getByText('Ordre de l\'étape')).toBeInTheDocument();
    expect(screen.getByText('Type d\'étape')).toBeInTheDocument();
    expect(screen.getByText('Patch Oracle')).toBeInTheDocument();
  });

  it('Story 72.3 — step_id, execution_id, referenced_action_id ne sont pas affichés dans Détails', () => {
    const entryWithIds: AuditExecutionEntry = {
      ...actionEntry,
      entity_type: 'action',
      entity_id: 7,
      details: {
        step_id: 'uuid-abc-123',
        execution_id: 88888,
        referenced_action_id: 77777,
        step_name: 'Étape AAP',
        referenced_action_name: 'Patch Oracle',
      },
    };
    render(<AuditEntryDrawer {...defaultProps} entry={entryWithIds} />);
    expect(screen.getByText('Détails')).toBeInTheDocument();
    expect(screen.getByText('Étape AAP')).toBeInTheDocument();
    expect(screen.getByText('Patch Oracle')).toBeInTheDocument();
    expect(screen.queryByText('uuid-abc-123')).not.toBeInTheDocument();
    expect(screen.queryByText('88888')).not.toBeInTheDocument();
    expect(screen.queryByText('77777')).not.toBeInTheDocument();
  });
});

// ─── Coverage extras ──────────────────────────────────────────────────────────
describe('AuditEntryDrawer — coverage extras', () => {
  it('shows skeleton when loading=true', () => {
    render(<AuditEntryDrawer {...defaultProps} loading={true} />);
    expect(document.querySelector('.ant-skeleton')).toBeInTheDocument();
  });

  it('shows error alert when error is set', () => {
    render(<AuditEntryDrawer {...defaultProps} loading={false} error="Fetch failed" />);
    expect(screen.getByText('Fetch failed')).toBeInTheDocument();
    expect(screen.getByText('Erreur de chargement')).toBeInTheDocument();
  });

  it('renders null when entry is null and not loading and no error', () => {
    render(<AuditEntryDrawer {...defaultProps} entry={null} />);
    // The Drawer is open, but its inner content is null — no detail text visible
    expect(screen.queryByText('Qui')).not.toBeInTheDocument();
  });

  it('ne affiche pas la section Détails quand details est vide pour non-execution', () => {
    const emptyDetailsEntry: AuditExecutionEntry = {
      ...actionEntry,
      details: {},
    };
    render(<AuditEntryDrawer {...defaultProps} entry={emptyDetailsEntry} />);
    expect(screen.queryByText('Détails')).not.toBeInTheDocument();
  });

  it('affiche les valeurs de type objet dans la section Détails avec JSON.stringify', () => {
    const entryWithObjectDetail: AuditExecutionEntry = {
      ...actionEntry,
      details: { action_name: 'Deploy', nested_obj: { key: 'value' } },
    };
    render(<AuditEntryDrawer {...defaultProps} entry={entryWithObjectDetail} />);
    // Object value should be rendered with JSON.stringify inside <pre>
    expect(screen.getByText(/"key"/)).toBeInTheDocument();
  });

  it('utilise user_id comme fallback dans la section Approbation quand user_name est null', () => {
    const entryNoName: AuditExecutionEntry = {
      ...mockApprovedEntry,
      user_name: undefined,
      user_id: 'uid-99',
    };
    render(<AuditEntryDrawer {...defaultProps} entry={entryNoName} />);
    // user_id should appear as "Approuvé par" value
    const uidElements = screen.getAllByText('uid-99');
    expect(uidElements.length).toBeGreaterThanOrEqual(1);
  });

  it('affiche le timeline quand execution et steps sont fournis', () => {
    const step: ExecutionStepResponse = {
      id: 1,
      execution_id: 123,
      step_order: 0,
      step_name: 'Step 1',
      step_type: 'platform',
      status: 'COMPLETED',
      started_at: '2025-01-15T10:00:00Z',
      completed_at: '2025-01-15T10:05:00Z',
      output: null,
      platform_job_id: null,
      error_message: null,
    };
    render(
      <AuditEntryDrawer
        {...defaultProps}
        entry={executionEntry}
        execution={mockExecution}
        steps={[step]}
      />
    );
    expect(screen.getByTestId('execution-timeline')).toBeInTheDocument();
  });

  it('affiche le servicenow_change_id quand présent pour une entrée execution', () => {
    const entryWithSNow: AuditExecutionEntry = {
      ...executionEntry,
      details: {
        ...executionEntry.details,
        servicenow_change_id: 'CHG0001234',
      },
    };
    render(<AuditEntryDrawer {...defaultProps} entry={entryWithSNow} />);
    expect(screen.getByText('CHG0001234')).toBeInTheDocument();
  });

  it('affiche le titre "Détail d\'audit" quand entry est null', () => {
    render(<AuditEntryDrawer {...defaultProps} entry={null} />);
    expect(screen.getByText("Détail d'audit")).toBeInTheDocument();
  });
});

// ─── Story 61.9 — Section Modifications ──────────────────────────────────────
describe('Story 61.9 — Section Modifications', () => {
  const integrationUpdatedEntry: AuditExecutionEntry = {
    ...actionEntry,
    action_type: 'INTEGRATION_UPDATED',
    entity_type: 'integration',
    details: {
      name: 'Mon Intégration',
      changes: {
        base_url: { old: 'https://old.example.com', new: 'https://new.example.com' },
        credential_ref: { old: '***', new: '***' },
      },
    },
  };

  it('test_modifications_section_shown_when_changes_present — section affichée si changes non vide', () => {
    render(<AuditEntryDrawer {...defaultProps} entry={integrationUpdatedEntry} />);
    expect(screen.getByText('Modifications')).toBeInTheDocument();
    expect(screen.getByText('base_url')).toBeInTheDocument();
    expect(screen.getByText('https://old.example.com')).toBeInTheDocument();
    expect(screen.getByText('https://new.example.com')).toBeInTheDocument();
    expect(screen.getAllByText('***').length).toBeGreaterThanOrEqual(2);
  });

  it('test_modifications_section_hidden_when_no_changes — section absente si pas de changes', () => {
    const noChangesEntry = { ...integrationUpdatedEntry, details: { name: 'Mon Intégration' } };
    render(<AuditEntryDrawer {...defaultProps} entry={noChangesEntry} />);
    expect(screen.queryByText('Modifications')).not.toBeInTheDocument();
  });

  it('test_modifications_section_hidden_when_changes_empty — section absente si changes vide', () => {
    const emptyChanges = { ...integrationUpdatedEntry, details: { changes: {} } };
    render(<AuditEntryDrawer {...defaultProps} entry={emptyChanges} />);
    expect(screen.queryByText('Modifications')).not.toBeInTheDocument();
  });

  it('test_changes_key_excluded_from_details_section — changes absent de la section Détails', () => {
    render(<AuditEntryDrawer {...defaultProps} entry={integrationUpdatedEntry} />);
    // La section Détails doit exister (name est présent) mais ne doit pas afficher "changes" comme clé brute
    const detailsCards = screen.getAllByText('Détails');
    expect(detailsCards.length).toBeGreaterThanOrEqual(1);
    // "changes" ne doit pas apparaître comme label de ligne dans Détails
    const changesLabels = screen.queryAllByText('changes');
    expect(changesLabels.length).toBe(0);
  });

  it('test_modifications_section_absent_for_execution_entity — pas de section Modifications pour execution', () => {
    const execWithChanges: AuditExecutionEntry = {
      ...executionEntry,
      details: { ...executionEntry.details, changes: { status: { old: 'RUNNING', new: 'COMPLETED' } } },
    };
    render(<AuditEntryDrawer {...defaultProps} entry={execWithChanges} />);
    expect(screen.queryByText('Modifications')).not.toBeInTheDocument();
  });

  it('test_null_undefined_values_display_as_dash — valeurs null/undefined affichées comme — (AC4)', () => {
    const nullValueEntry: AuditExecutionEntry = {
      ...integrationUpdatedEntry,
      details: {
        changes: {
          field_with_null: { old: null, new: 'new_value' },
          field_with_undefined: { old: undefined, new: null },
        },
      },
    };
    render(<AuditEntryDrawer {...defaultProps} entry={nullValueEntry} />);
    expect(screen.getByText('Modifications')).toBeInTheDocument();
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText('new_value')).toBeInTheDocument();
  });

  it('test_object_values_rendered_as_json_pre — valeurs objets affichées en JSON dans pre (AC5)', () => {
    const objectValueEntry: AuditExecutionEntry = {
      ...integrationUpdatedEntry,
      details: {
        changes: {
          config: { old: { host: 'old-host' }, new: { host: 'new-host' } },
        },
      },
    };
    render(<AuditEntryDrawer {...defaultProps} entry={objectValueEntry} />);
    expect(screen.getByText('Modifications')).toBeInTheDocument();
    expect(screen.getByText(/"old-host"/)).toBeInTheDocument();
    expect(screen.getByText(/"new-host"/)).toBeInTheDocument();
  });

  it('test_masked_values_displayed_as_is — valeurs masquées *** affichées telles quelles (AC3)', () => {
    const maskedEntry: AuditExecutionEntry = {
      ...integrationUpdatedEntry,
      details: {
        changes: {
          credential_ref: { old: '***', new: '***' },
        },
      },
    };
    render(<AuditEntryDrawer {...defaultProps} entry={maskedEntry} />);
    expect(screen.getByText('Modifications')).toBeInTheDocument();
    expect(screen.getAllByText('***').length).toBeGreaterThanOrEqual(2);
  });
});

// ─── Story 61.10 — Contexte d'exécution ───────────────────────────────────────
describe("Story 61.10 — Contexte d'exécution", () => {
  const submittedEntry: AuditExecutionEntry = {
    ...executionEntry,
    action_type: 'EXECUTION_SUBMITTED',
    entity_type: 'execution',
    details: {
      action_id: 42,
      action_name: 'Patch Oracle PROD',
      environment: 'prod',
      targets: ['oracle-prod-01', 'oracle-prod-02'],
      parameters: { patch_version: '19.21' },
    },
  };

  const approvedWithContextEntry: AuditExecutionEntry = {
    ...mockApprovedEntry,
    action_type: 'EXECUTION_APPROVED',
    entity_type: 'execution',
    details: {
      action_id: 5,
      action_name: 'Deploy Prod',
      environment: 'prod',
      targets: ['server-prod-01'],
      parameters: { deploy_version: '2.4.1' },
      approval_comment: 'OK',
    },
  };

  it("test_execution_context_shown_for_submitted_with_full_context — section affichée pour EXECUTION_SUBMITTED avec action_name, targets, parameters", () => {
    render(<AuditEntryDrawer {...defaultProps} entry={submittedEntry} />);
    expect(screen.getByText("Contexte d'exécution")).toBeInTheDocument();
  });

  it("test_execution_context_shown_for_approved_with_context — section affichée pour EXECUTION_APPROVED après story 61.7", () => {
    render(<AuditEntryDrawer {...defaultProps} entry={approvedWithContextEntry} />);
    expect(screen.getByText("Contexte d'exécution")).toBeInTheDocument();
  });

  it("test_action_name_displayed_under_action_label — action_name affiché sous label 'Action'", () => {
    render(<AuditEntryDrawer {...defaultProps} entry={submittedEntry} />);
    expect(screen.getByText('Action')).toBeInTheDocument();
    expect(screen.getByText('Patch Oracle PROD')).toBeInTheDocument();
  });

  it("test_targets_displayed_under_cibles_label — targets affichés sous 'Cibles'", () => {
    render(<AuditEntryDrawer {...defaultProps} entry={submittedEntry} />);
    expect(screen.getByText('Cibles')).toBeInTheDocument();
    expect(screen.getByText('oracle-prod-01, oracle-prod-02')).toBeInTheDocument();
  });

  it("test_parameters_displayed_as_json — parameters affichés en JSON indenté sous label Paramètres (AC4)", () => {
    render(<AuditEntryDrawer {...defaultProps} entry={submittedEntry} />);
    expect(screen.getByText('Paramètres')).toBeInTheDocument();
    expect(screen.getByText(/"patch_version"/)).toBeInTheDocument();
  });

  it("test_section_absent_when_no_context — section absente si aucun champ présent", () => {
    const noContextEntry: AuditExecutionEntry = {
      ...executionEntry,
      action_type: 'EXECUTION_COMPLETED',
      details: { environment: 'prod', status: 'COMPLETED' },
    };
    render(<AuditEntryDrawer {...defaultProps} entry={noContextEntry} />);
    expect(screen.queryByText("Contexte d'exécution")).not.toBeInTheDocument();
  });

  it("test_section_absent_for_non_execution_entity — section absente pour entity_type !== 'execution'", () => {
    const actionEntryWithContext: AuditExecutionEntry = {
      ...actionEntry,
      details: { action_name: 'Deploy', targets: ['server-01'] },
    };
    render(<AuditEntryDrawer {...defaultProps} entry={actionEntryWithContext} />);
    expect(screen.queryByText("Contexte d'exécution")).not.toBeInTheDocument();
  });

  it("test_section_shown_for_step_with_action_name_only — section affichée pour EXECUTION_STEP_STARTED avec seulement action_name (AC1)", () => {
    // EXECUTION_STEP_STARTED enrichi par 61.8 : action_name présent, pas de targets ni parameters
    const stepStartedEntry: AuditExecutionEntry = {
      ...executionEntry,
      action_type: 'EXECUTION_STEP_STARTED',
      entity_type: 'execution',
      details: { step_id: 1, step_name: 'AAP step', action_name: 'Patch Oracle', execution_id: 99 },
    };
    render(<AuditEntryDrawer {...defaultProps} entry={stepStartedEntry} />);
    expect(screen.getByText("Contexte d'exécution")).toBeInTheDocument();
    expect(screen.getByText('Action')).toBeInTheDocument();
    expect(screen.getByText('Patch Oracle')).toBeInTheDocument();
    expect(screen.queryByText('Cibles')).not.toBeInTheDocument();
    expect(screen.queryByText('Paramètres')).not.toBeInTheDocument();
  });

  it("test_targets_absent_label_not_shown_when_empty_array — label Cibles absent si targets est []", () => {
    const noTargetsEntry: AuditExecutionEntry = {
      ...submittedEntry,
      details: { action_name: 'Deploy', targets: [] },
    };
    render(<AuditEntryDrawer {...defaultProps} entry={noTargetsEntry} />);
    // Section affichée car action_name présent, mais "Cibles" absent car targets vide
    expect(screen.getByText("Contexte d'exécution")).toBeInTheDocument();
    expect(screen.queryByText('Cibles')).not.toBeInTheDocument();
  });
});
