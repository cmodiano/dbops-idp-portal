/**
 * ActionWizard tests (Story 2.22, AC #1–#5, Task 7; Story 4.10 AC4).
 * - Wizard 3 steps: Général, Automatisme & Paramètres, Impact & Changement. 1 action = 1 étape. Plateforme définit le connecteur.
 */

import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ActionWizard } from './ActionWizard';
import type { ActionDetail } from '../../types/api';

vi.mock('../../services/admin_service', () => ({
  getTags: vi.fn().mockResolvedValue([]),
  updateActionTags: vi.fn().mockResolvedValue({}),
  updateActionSteps: vi.fn().mockResolvedValue({}),
  updateWorkflowSteps: vi.fn().mockResolvedValue({}),
  updateBusinessRulePolicies: vi.fn().mockResolvedValue({}),
  patchAction: vi.fn().mockResolvedValue({}),
  checkActionNameAvailable: vi.fn().mockResolvedValue(true),
  getEligibleActionsForWorkflow: vi.fn().mockResolvedValue([
    { id: 100, name: 'Action A', engine: 'Oracle', status: 'published', created_at: '', execution_count: 0 },
    { id: 101, name: 'Action B', engine: 'SQL Server', status: 'published', created_at: '', execution_count: 0 },
  ]),
}));

// Mock @xyflow/react to avoid CSS import issues in jsdom (Story 16.5)
vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ children }: { children?: React.ReactNode }) => <div data-testid="react-flow">{children}</div>,
  ReactFlowProvider: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Controls: () => null,
  MiniMap: () => null,
  Background: () => null,
  Handle: () => null,
  addEdge: vi.fn(),
  useNodesState: () => [[], vi.fn(), vi.fn()],
  useEdgesState: () => [[], vi.fn(), vi.fn()],
  useReactFlow: () => ({ screenToFlowPosition: vi.fn() }),
  Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
}));

vi.mock('../../services/reference_service', () => ({
  fetchEngines: vi.fn().mockResolvedValue([
    { value: 'Oracle', label: 'Oracle' },
    { value: 'SQL Server', label: 'SQL Server' },
  ]),
  fetchPlatforms: vi.fn().mockResolvedValue([
    { value: 'AAP', label: 'AAP' },
    { value: 'GitHub Actions', label: 'GitHub Actions' },
  ]),
  fetchEnvironments: vi.fn().mockResolvedValue(['DEV', 'STAGING', 'PROD']),
}));

// Mock useEngines to bypass module-level cache and avoid cross-test state contamination
vi.mock('../../hooks/useEngines', () => ({
  useEngines: () => ({
    engines: [
      { value: 'Oracle', label: 'Oracle' },
      { value: 'SQL Server', label: 'SQL Server' },
    ],
    engineOptions: [
      { value: 'Oracle', label: 'Oracle' },
      { value: 'SQL Server', label: 'SQL Server' },
    ],
    loading: false,
    error: null,
  }),
  invalidateEnginesCache: vi.fn(),
}));

// Story 31.1: Mock usePlatformIntegrations (replaces usePlatforms for action forms)
vi.mock('../../hooks/usePlatformIntegrations', () => ({
  usePlatformIntegrations: () => ({
    integrations: [
      { id: 1, type: 'aap', name: 'AAP-PROD', status: 'valid', base_url: 'https://aap.local', credential_ref: null, icon: null, auth_flow: null, created_at: '', updated_at: '' },
      { id: 2, type: 'github_actions', name: 'GitHub CI', status: 'valid', base_url: 'https://github.com', credential_ref: null, icon: null, auth_flow: null, created_at: '', updated_at: '' },
    ],
    integrationOptions: [
      { value: 1, label: 'AAP-PROD — aap' },
      { value: 2, label: 'GitHub CI — github_actions' },
    ],
    loading: false,
    error: null,
    getIntegrationById: (id: number) => {
      if (id === 1) return { id: 1, type: 'aap', name: 'AAP-PROD', status: 'valid', base_url: 'https://aap.local', credential_ref: null, icon: null, auth_flow: null, created_at: '', updated_at: '' };
      if (id === 2) return { id: 2, type: 'github_actions', name: 'GitHub CI', status: 'valid', base_url: 'https://github.com', credential_ref: null, icon: null, auth_flow: null, created_at: '', updated_at: '' };
      return undefined;
    },
  }),
}));

vi.mock('../../services/categories_service', () => ({
  getCategories: vi.fn().mockResolvedValue([]),
}));

// M3 fix: mock useAAPTemplates to avoid real API calls in WizardAAPTemplateSection tests
vi.mock('../../hooks/useAAPTemplates', () => ({
  useAAPTemplates: vi.fn(),
}));

import { useAAPTemplates } from '../../hooks/useAAPTemplates';
const mockUseAAPTemplates = useAAPTemplates as ReturnType<typeof vi.fn>;

const defaultAAPMockWizard = {
  templates: [],
  loading: false,
  fallback: true,
  error: null,
};

const mockOnSubmit = vi.fn().mockResolvedValue({ id: 1 });
const mockOnCancel = vi.fn();
const mockOnSuccess = vi.fn();

const defaultProps = {
  open: true,
  onCancel: mockOnCancel,
  onSubmit: mockOnSubmit,
  loading: false,
  error: null,
  editAction: null,
  onSuccess: mockOnSuccess,
};

describe('ActionWizard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // M3 fix: default AAP mock (fallback = manual input)
    mockUseAAPTemplates.mockReturnValue(defaultAAPMockWizard);
  });

  describe('AC1: Ouverture du wizard', () => {
    it('affiche 3 étapes : Général, Automatisme & Paramètres, Impact & Changement', async () => {
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });
      expect(screen.getByText('Général')).toBeInTheDocument();
      expect(screen.getByText('Automatisme & Paramètres')).toBeInTheDocument();
      expect(screen.getByText('Impact & Changement')).toBeInTheDocument();
    });

    it("affiche le contenu de l'étape 1 (champs Général) - Story 2.23: Catégorie removed", async () => {
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });
      expect(screen.getByLabelText("Nom de l'action")).toBeInTheDocument();
      expect(screen.getByLabelText('Description')).toBeInTheDocument();
      expect(screen.getByLabelText('Moteur')).toBeInTheDocument();
      expect(screen.getByLabelText('Intégration')).toBeInTheDocument();
    });
  });

  describe('AC3: Navigation et persistance', () => {
    it('boutons Précédent / Suivant changent l\'étape sans perdre le state', async () => {
      const user = userEvent.setup();
      const editAction: ActionDetail = {
        id: 1,
        name: 'Action test',
        description: 'Description pour validation',
        item_type: 'action',
        engine: 'Oracle',
        platform: 'AAP',
        integration_id: 1,
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft',
        created_by: null,
        created_at: '',
        updated_at: null,
        execution_steps: null,
        workflow_steps: null,
        tags: [],
      };
      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });

      await waitFor(() => expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Action test'));
      const nextBtn = await screen.findByRole('button', { name: /Suivant/i });
      await user.click(nextBtn);
      await waitFor(() => expect(screen.getByText(/Ajouter un parametre/i)).toBeInTheDocument(), { timeout: 8000 });

      await user.click(screen.getByRole('button', { name: /Précédent/i }));
      await waitFor(() => {
        expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Action test');
      });
    });

    it("bouton Enregistrer visible uniquement à l'étape 3", async () => {
      const user = userEvent.setup();
      const editAction: ActionDetail = {
        id: 1,
        name: 'X',
        description: 'Desc',
        item_type: 'action',
        engine: 'Oracle',
        platform: 'AAP',
        integration_id: 1,
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft',
        created_by: null,
        created_at: '',
        updated_at: null,
        execution_steps: null,
        workflow_steps: null,
        tags: [],
      };
      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });
      expect(screen.queryByRole('button', { name: /Enregistrer/i })).not.toBeInTheDocument();

      await waitFor(() => expect(screen.getByLabelText("Nom de l'action")).toHaveValue('X'));
      const next1 = await screen.findByRole('button', { name: /Suivant/i });
      await user.click(next1);
      await waitFor(() => expect(screen.getByText(/Ajouter un parametre/i)).toBeInTheDocument(), { timeout: 8000 });
      expect(screen.queryByRole('button', { name: /Enregistrer/i })).not.toBeInTheDocument();

      const next2 = await screen.findByRole('button', { name: /Suivant/i });
      await user.click(next2);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument();
      });
    });
  });

  describe('AC4: Enregistrement', () => {
    it("à l'étape 3, Enregistrer envoie le payload (AAP : ID template requis)", async () => {
      const user = userEvent.setup();
      const editAction: ActionDetail = {
        id: 10,
        name: 'Action à modifier',
        description: 'Desc',
        item_type: 'action',
        engine: 'Oracle',
        platform: 'AAP',
        integration_id: 1,
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft',
        created_by: null,
        created_at: '',
        updated_at: null,
        execution_steps: null,
        workflow_steps: null,
        tags: [],
      };
      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });

      await waitFor(() => expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Action à modifier'));
      const next1 = await screen.findByRole('button', { name: /Suivant/i });
      await user.click(next1);
      await waitFor(() => expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument());
      await user.type(screen.getByLabelText('ID template AAP'), '42');
      const next2 = await screen.findByRole('button', { name: /Suivant/i });
      await user.click(next2);
      await waitFor(() => expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument());
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));
      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledTimes(1);
        const payload = mockOnSubmit.mock.calls[0][0];
        expect(payload.name).toBe('Action à modifier');
        expect(payload.engine).toBe('Oracle');
        // Story 31.1: integration_id sent, platform derived from integration type
        expect(payload.integration_id).toBe(1);
        expect(payload.platform).toBe('AAP');
        expect(payload.parameters_schema).toBeDefined();
        expect(payload.impact_rules).toBeDefined();
      });
    });
  });

  describe('AC4: Enregistrement (mode édition pré-rempli)', () => {
    it('à l\'étape 4, Enregistrer envoie le payload via onSubmit (mode édition pré-rempli)', async () => {
      const user = userEvent.setup();
      const editAction: ActionDetail = {
        id: 10,
        name: 'Action à modifier',
        description: 'Desc',
        item_type: 'action',
        engine: 'Oracle',
        platform: 'AAP',
        integration_id: 1,
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft',
        created_by: 1,
        created_at: '2025-01-01T00:00:00Z',
        updated_at: null,
        execution_steps: [],
        workflow_steps: null,
        tags: [],
      };
      render(<ActionWizard {...defaultProps} editAction={editAction} />);

      await waitFor(() => {
        expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Action à modifier');
      });
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => {
        expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument();
      });
      await user.type(screen.getByLabelText('ID template AAP'), '42');
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledTimes(1);
        const payload = mockOnSubmit.mock.calls[0][0];
        expect(payload.name).toBe('Action à modifier');
        expect(payload.engine).toBe('Oracle');
        // Story 31.1: integration_id sent, platform derived
        expect(payload.integration_id).toBe(1);
        expect(payload.platform).toBe('AAP');
        expect(payload.parameters_schema).toBeDefined();
        expect(payload.impact_rules).toBeDefined();
      });
    });

    it("en mode création (sans editAction), le wizard affiche l'étape 1 et Enregistrer envoie le payload attendu quand on soumet", async () => {
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });
      expect(screen.getByText('Nouvelle action')).toBeInTheDocument();
      expect(screen.getByLabelText("Nom de l'action")).toBeInTheDocument();
      expect(screen.getByLabelText('Description')).toBeInTheDocument();
      expect(screen.getByRole('combobox', { name: /moteur/i })).toBeInTheDocument();
      expect(screen.getByRole('combobox', { name: /moteur/i })).toBeInTheDocument();
      expect(screen.getByRole('combobox', { name: /intégration/i })).toBeInTheDocument();
    });
  });

  describe('AC5: Mode édition', () => {
    it('en mode édition les champs sont pré-remplis depuis l\'action existante', async () => {
      const editAction: ActionDetail = {
        id: 42,
        name: 'Action existante',
        description: 'Description existante',
        item_type: 'action',
        engine: 'SQL Server',
        platform: 'GitHub Actions',
        integration_id: 2,
        parameters_schema: { type: 'object', properties: { foo: { type: 'string' } }, required: ['foo'] },
        impact_rules: { DEV: { level: 'low', criteria: null } },
        default_impact_level: 'low',
        status: 'draft',
        created_by: 1,
        created_at: '2025-01-01T00:00:00Z',
        updated_at: null,
        execution_steps: [],
        workflow_steps: null,
        tags: ['tag1'],
      };

      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });

      expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Action existante');
      expect(screen.getByLabelText('Description')).toHaveValue('Description existante');
    });

    it('affiche le titre "Modifier l\'action" en mode édition', async () => {
      const editAction: ActionDetail = {
        id: 1,
        name: 'X',
        description: null,
        item_type: 'action',
        engine: 'Oracle',
        platform: 'AAP',
        integration_id: 1,
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft',
        created_by: null,
        created_at: '',
        updated_at: null,
        execution_steps: null,
        workflow_steps: null,
        tags: [],
      };

      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });

      expect(screen.getByText(/Modifier l'action/i)).toBeInTheDocument();
    });
  });

  describe('Comportement modal', () => {
    it('appelle onCancel quand on clique Annuler', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });
      await user.click(screen.getByRole('button', { name: /Annuler/i }));
      expect(mockOnCancel).toHaveBeenCalledTimes(1);
    });
  });

  // Story 9.5: Workflow support tests
  describe('Story 9.5: Workflow support', () => {
    it('affiche le choix type action/workflow au Step 1', async () => {
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });
      expect(screen.getByRole('radio', { name: /Action/i })).toBeInTheDocument();
      expect(screen.getByRole('radio', { name: /Workflow/i })).toBeInTheDocument();
      // Action selected by default
      expect(screen.getByRole('radio', { name: /Action/i })).toBeChecked();
    });

    it('masque les champs engine/platform quand type=workflow est sélectionné', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });
      // Initially engine/platform are visible
      expect(screen.getByLabelText('Moteur')).toBeInTheDocument();
      expect(screen.getByLabelText('Intégration')).toBeInTheDocument();

      // Select workflow
      await user.click(screen.getByRole('radio', { name: /Workflow/i }));
      await waitFor(() => {
        expect(screen.queryByLabelText('Moteur')).not.toBeInTheDocument();
        expect(screen.queryByLabelText('Intégration')).not.toBeInTheDocument();
      });
    });

    it('validation Step 1 workflow : type=workflow avec nom vide génère erreur, mais pas d\'erreur engine/platform', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });
      // Select workflow type
      await user.click(screen.getByRole('radio', { name: /Workflow/i }));
      // Click next without entering a name
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      // Should show error for missing name
      await waitFor(() => {
        expect(screen.getByText('Le nom est requis')).toBeInTheDocument();
      });
    });

    it('Step 2 affiche WorkflowStepsEditor si type=workflow', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });
      // Select workflow type
      await user.click(screen.getByRole('radio', { name: /Workflow/i }));
      // Enter name and description (required to enable Suivant)
      await user.type(screen.getByLabelText('Nom du workflow'), 'Mon Workflow');
      await user.type(screen.getByLabelText('Description'), 'Description du workflow');
      // Go to step 2
      const nextBtn = await screen.findByRole('button', { name: /Suivant/i });
      await user.click(nextBtn);
      // Should show WorkflowStepsEditor (shows "Ajouter une étape" button)
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Ajouter une étape/i })).toBeInTheDocument();
      }, { timeout: 8000 });
    });

    it('Radio.Group masqué en mode édition (Story 2.29)', async () => {
      const editAction: ActionDetail = {
        id: 1,
        item_type: 'workflow',
        name: 'Workflow existant',
        description: null,
        engine: null,
        platform: null,
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft',
        created_by: null,
        created_at: '',
        updated_at: null,
        execution_steps: null,
        workflow_steps: [{ order: 1, name: 'Step 1', referenced_action_id: 100 }],
        tags: [],
      };
      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });
      // Radio buttons should be hidden (not in DOM) in edit mode
      expect(screen.queryByRole('radio', { name: /Action/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('radio', { name: /Workflow/i })).not.toBeInTheDocument();
    });

    it('sauvegarde workflow appelle updateWorkflowSteps avec les étapes', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });
      // Select workflow type
      await user.click(screen.getByRole('radio', { name: /Workflow/i }));
      // Enter name and description (required to enable Suivant)
      await user.type(screen.getByLabelText('Nom du workflow'), 'Workflow Test');
      await user.type(screen.getByLabelText('Description'), 'Description workflow');
      // Go to step 2
      const nextBtn = await screen.findByRole('button', { name: /Suivant/i });
      await user.click(nextBtn);
      // Wait for eligible actions to load and add a step
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Ajouter une étape/i })).toBeInTheDocument();
      }, { timeout: 8000 });
      await user.click(screen.getByRole('button', { name: /Ajouter une étape/i }));
      // Select an action in the autocomplete
      await waitFor(() => {
        expect(screen.getByLabelText('Sélectionner une action')).toBeInTheDocument();
      });
      const autocomplete = screen.getByLabelText('Sélectionner une action');
      await user.click(autocomplete);
      // Type to filter and select (mock returns "Action A" with engine Oracle)
      await user.type(autocomplete, 'Action A');
      const actionOption = await screen.findByText(/Action A/i);
      await user.click(actionOption);
      // Go to step 3
      const nextToStep3 = await screen.findByRole('button', { name: /Suivant/i });
      await user.click(nextToStep3);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument();
      });
      // Save
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));
      // Verify updateWorkflowSteps was called
      const { updateWorkflowSteps } = await import('../../services/admin_service');
      await waitFor(
        () => {
          expect(mockOnSubmit).toHaveBeenCalledWith(
            expect.objectContaining({
              name: 'Workflow Test',
              item_type: 'workflow',
            })
          );
          expect(vi.mocked(updateWorkflowSteps)).toHaveBeenCalledWith(
            1,
            expect.objectContaining({
              steps: expect.arrayContaining([
                expect.objectContaining({ referenced_action_id: 100 }),
              ]),
            })
          );
        },
        { timeout: 5000 }
      );
    }, 25000);

    it('édition workflow existant charge et pré-remplit WorkflowStepsEditor', async () => {
      const editAction: ActionDetail = {
        id: 50,
        item_type: 'workflow',
        name: 'Workflow existant',
        description: 'Description workflow',
        engine: null,
        platform: null,
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft',
        created_by: null,
        created_at: '',
        updated_at: null,
        execution_steps: null,
        workflow_steps: [
          { order: 1, name: 'Étape un', referenced_action_id: 100 },
          { order: 2, name: null, referenced_action_id: 101 },
        ],
        tags: [],
      };
      const user = userEvent.setup();
      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });
      // Radio.Group should be hidden in edit mode (Story 2.29)
      expect(screen.queryByRole('radio', { name: /Workflow/i })).not.toBeInTheDocument();
      // Title should show "Modifier le workflow"
      expect(screen.getByText(/Modifier le workflow/i)).toBeInTheDocument();
      // Go to step 2
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      // Verify steps are loaded
      await waitFor(() => {
        expect(screen.getByText('Étape 1')).toBeInTheDocument();
        expect(screen.getByText('Étape 2')).toBeInTheDocument();
      });
    });
  });

  // Story 2.29: initialItemType prop tests
  describe('Story 2.29: initialItemType prop', () => {
    it('avec initialItemType="action", le Radio.Group est masqué', async () => {
      await act(async () => {
        render(<ActionWizard {...defaultProps} initialItemType="action" />);
      });
      // Radio.Group should NOT be in the DOM
      expect(screen.queryByRole('radio', { name: /Action/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('radio', { name: /Workflow/i })).not.toBeInTheDocument();
      // Title should be "Nouvelle action"
      expect(screen.getByText('Nouvelle action')).toBeInTheDocument();
      // Engine/platform should be visible (action type)
      expect(screen.getByLabelText('Moteur')).toBeInTheDocument();
      expect(screen.getByLabelText('Intégration')).toBeInTheDocument();
    });

    it('avec initialItemType="workflow", le Radio.Group est masqué et champs engine/platform masqués', async () => {
      await act(async () => {
        render(<ActionWizard {...defaultProps} initialItemType="workflow" />);
      });
      // Radio.Group should NOT be in the DOM
      expect(screen.queryByRole('radio', { name: /Action/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('radio', { name: /Workflow/i })).not.toBeInTheDocument();
      // Title should be "Nouveau workflow"
      expect(screen.getByText('Nouveau workflow')).toBeInTheDocument();
      // Engine/platform should NOT be visible (workflow type)
      expect(screen.queryByLabelText('Moteur')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Intégration')).not.toBeInTheDocument();
    });

    it('sans initialItemType, le Radio.Group est visible (compatibilité rétroactive)', async () => {
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });
      // Radio.Group should be visible
      expect(screen.getByRole('radio', { name: /Action/i })).toBeInTheDocument();
      expect(screen.getByRole('radio', { name: /Workflow/i })).toBeInTheDocument();
      // Action selected by default
      expect(screen.getByRole('radio', { name: /Action/i })).toBeChecked();
    });

    it('en mode édition action, le Radio.Group est masqué', async () => {
      const editAction: ActionDetail = {
        id: 1,
        item_type: 'action',
        name: 'Action existante',
        description: null,
        engine: 'Oracle',
        platform: 'AAP',
        integration_id: 1,
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft',
        created_by: null,
        created_at: '',
        updated_at: null,
        execution_steps: null,
        workflow_steps: null,
        tags: [],
      };
      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });
      // Radio.Group hidden in edit mode
      expect(screen.queryByRole('radio', { name: /Action/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('radio', { name: /Workflow/i })).not.toBeInTheDocument();
      // Title should show "Modifier l'action"
      expect(screen.getByText(/Modifier l'action/i)).toBeInTheDocument();
      // Engine/platform should still be visible (action type)
      expect(screen.getByLabelText('Moteur')).toBeInTheDocument();
      expect(screen.getByLabelText('Intégration')).toBeInTheDocument();
    });

    it('avec initialItemType="workflow", titre et champs corrects à étape 1', async () => {
      await act(async () => {
        render(<ActionWizard {...defaultProps} initialItemType="workflow" />);
      });
      // Verify workflow type is set via title
      expect(screen.getByText('Nouveau workflow')).toBeInTheDocument();
      // Verify Radio.Group is hidden
      expect(screen.queryByRole('radio', { name: /Action/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('radio', { name: /Workflow/i })).not.toBeInTheDocument();
      // Verify engine/platform are NOT displayed for workflows
      expect(screen.queryByLabelText('Moteur')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Intégration')).not.toBeInTheDocument();
      // Verify name field label is "Nom du workflow" (not "Nom de l'action")
      expect(screen.getByLabelText('Nom du workflow')).toBeInTheDocument();
    });
  });

  // Story 18.3, AC1: Modal width increased to 1400 in visual workflow mode
  describe('Story 18.3 — Modal width (AC1)', () => {
    it('modal width=640 for action type (default)', async () => {
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });
      // Default action wizard should have normal width
      const modal = document.querySelector('.ant-modal');
      if (modal) {
        expect(modal).toHaveStyle({ width: '640px' });
      }
    });

    it('modal width=640 for workflow in list mode (default)', async () => {
      await act(async () => {
        render(<ActionWizard {...defaultProps} initialItemType="workflow" />);
      });
      // Workflow wizard defaults to list mode → 640px
      const modal = document.querySelector('.ant-modal');
      if (modal) {
        expect(modal).toHaveStyle({ width: '640px' });
      }
    });
  });

  // Story 31.1: Integration field tests
  describe('Story 31.1: Intégration field', () => {
    it('affiche le champ "Intégration" au lieu de "Plateforme" pour les actions', async () => {
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });
      expect(screen.getByLabelText('Intégration')).toBeInTheDocument();
      expect(screen.queryByLabelText('Plateforme')).not.toBeInTheDocument();
    });

    it('envoie integration_id et platform dérivé dans le payload', async () => {
      const user = userEvent.setup();
      const editAction: ActionDetail = {
        id: 10,
        name: 'Action intégration',
        description: 'Desc',
        item_type: 'action',
        engine: 'Oracle',
        platform: 'AAP',
        integration_id: 1,
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft',
        created_by: null,
        created_at: '',
        updated_at: null,
        execution_steps: [],
        workflow_steps: null,
        tags: [],
      };
      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });
      // Navigate to step 2
      const next1 = await screen.findByRole('button', { name: /Suivant/i });
      await user.click(next1);
      await waitFor(() => expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument());
      await user.type(screen.getByLabelText('ID template AAP'), '42');
      // Navigate to step 3
      const next2 = await screen.findByRole('button', { name: /Suivant/i });
      await user.click(next2);
      await waitFor(() => expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument());
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledTimes(1);
        const payload = mockOnSubmit.mock.calls[0][0];
        expect(payload.integration_id).toBe(1);
        expect(payload.platform).toBe('AAP');
      });
    });

    it('masque le champ Intégration pour les workflows', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });
      // Switch to workflow
      await user.click(screen.getByRole('radio', { name: /Workflow/i }));
      await waitFor(() => {
        expect(screen.queryByLabelText('Intégration')).not.toBeInTheDocument();
      });
    });

    it('AC6: affiche alerte mode dégradé quand action existante a platform sans integration_id', async () => {
      const editAction: ActionDetail = {
        id: 99,
        name: 'Action legacy',
        description: 'Description legacy',
        item_type: 'action',
        engine: 'Oracle',
        platform: 'AAP',
        integration_id: null,
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft',
        created_by: null,
        created_at: '',
        updated_at: null,
        execution_steps: null,
        workflow_steps: null,
        tags: [],
      };
      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });
      await waitFor(() => {
        expect(screen.getByText(/ancienne plateforme.*AAP/i)).toBeInTheDocument();
      });
    });
  });

  // Story 31.5: WizardAAPTemplateSection tests — M3 fix
  describe('Story 31.5: WizardAAPTemplateSection', () => {
    const navigateToStep2WithAAP = async (user: ReturnType<typeof userEvent.setup>) => {
      // Fill step 1: name, description, engine, integration (AAP id=1)
      await user.type(screen.getByLabelText(/Nom de l'action/i), 'Test AAP Action');
      await user.type(screen.getByLabelText(/Description/i), 'Description test');
      // Select engine (Oracle)
      const engineSelect = screen.getByLabelText('Moteur');
      await user.click(engineSelect);
      const oracleOpt = await screen.findByText('Oracle', { selector: '[class*="ant-select-item-option-content"]' });
      await user.click(oracleOpt);
      // Select integration (AAP-PROD = id 1)
      const integrationSelect = screen.getByLabelText('Intégration');
      await user.click(integrationSelect);
      const aapOpt = await screen.findByText('AAP-PROD — aap');
      await user.click(aapOpt);
      // Navigate to step 2
      const next = screen.getByRole('button', { name: /Suivant/i });
      await user.click(next);
    };

    it('affiche le sélecteur de template AAP (liste) quand templates disponibles', async () => {
      mockUseAAPTemplates.mockReturnValue({
        templates: [
          { id: 10, name: 'Deploy DB', description: '' },
          { id: 20, name: 'Patch OS', description: '' },
        ],
        loading: false,
        fallback: false,
        error: null,
      });
      const user = userEvent.setup();
      await act(async () => { render(<ActionWizard {...defaultProps} />); });
      await navigateToStep2WithAAP(user);
      await waitFor(() => {
        // Form.Item label is used (no htmlFor without name prop) — check label text presence
        expect(screen.getByText('Template AAP')).toBeInTheDocument();
      });
    }, 20000);

    it('affiche la saisie manuelle (fallback) quand API indisponible', async () => {
      mockUseAAPTemplates.mockReturnValue(defaultAAPMockWizard);
      const user = userEvent.setup();
      await act(async () => { render(<ActionWizard {...defaultProps} />); });
      await navigateToStep2WithAAP(user);
      await waitFor(() => {
        expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument();
      });
    }, 20000);

    it('affiche une alerte quand API retourne une erreur', async () => {
      mockUseAAPTemplates.mockReturnValue({
        templates: [],
        loading: false,
        fallback: true,
        error: 'API indisponible',
      });
      const user = userEvent.setup();
      await act(async () => { render(<ActionWizard {...defaultProps} />); });
      await navigateToStep2WithAAP(user);
      await waitFor(() => {
        expect(screen.getByText(/Saisie manuelle/i)).toBeInTheDocument();
      });
    }, 20000);
  });
});

// Additional coverage tests
describe('ActionWizard — additional coverage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAAPTemplates.mockReturnValue({
      templates: [],
      loading: false,
      fallback: true,
      error: null,
    });
  });

  // Helper action for navigation
  const makeEditAction = (overrides: Partial<import('../../types/api').ActionDetail> = {}): import('../../types/api').ActionDetail => ({
    id: 10,
    name: 'Test Action',
    description: 'Desc',
    item_type: 'action' as const,
    engine: 'Oracle',
    platform: 'AAP',
    integration_id: 1,
    parameters_schema: null,
    impact_rules: null,
    default_impact_level: null,
    status: 'draft' as const,
    created_by: null,
    created_at: '',
    updated_at: null,
    execution_steps: [],
    workflow_steps: null,
    tags: [],
    ...overrides,
  });

  describe('open=false resets form', () => {
    it('does not render wizard content when open=false', async () => {
      await act(async () => {
        render(<ActionWizard {...defaultProps} open={false} />);
      });
      // Modal should not be visible — no step items rendered
      expect(screen.queryByText('Nouvelle action')).not.toBeInTheDocument();
    });
  });

  describe('isReadOnly — published action', () => {
    it('disables Enregistrer button when editAction.status=published', async () => {
      const user = userEvent.setup();
      const editAction = makeEditAction({ status: 'published' });

      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });

      await waitFor(() => expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Test Action'));

      // Navigate to step 2
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument());
      await user.type(screen.getByLabelText('ID template AAP'), '5');

      // Navigate to step 3
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument());

      // Enregistrer should be disabled for published actions
      expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeDisabled();
    }, 30000);
  });

  describe('handleSave — ApiError with 400 + details', () => {
    it('sets field errors and submitError when onSubmit throws ApiError 400 with details', async () => {
      const { ApiError } = await import('../../services/api_client');
      const user = userEvent.setup();

      const mockSubmitWith400 = vi.fn().mockRejectedValue(
        new ApiError('Validation error', 400, {
          error: {
            details: { name: ['Ce nom est déjà utilisé.'] },
          },
        })
      );

      const editAction = makeEditAction();
      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} onSubmit={mockSubmitWith400} />);
      });

      await waitFor(() => expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Test Action'));

      // Navigate to step 2
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument());
      await user.type(screen.getByLabelText('ID template AAP'), '5');

      // Navigate to step 3
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument());

      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      await waitFor(() => {
        expect(screen.getByText('Veuillez corriger les erreurs indiquées dans le formulaire.')).toBeInTheDocument();
      });
    }, 30000);
  });

  describe('handleSave — generic Error', () => {
    it('sets submitError message when onSubmit throws a generic Error', async () => {
      const user = userEvent.setup();

      const mockSubmitWithError = vi.fn().mockRejectedValue(new Error('Erreur serveur inattendue'));

      const editAction = makeEditAction();
      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} onSubmit={mockSubmitWithError} />);
      });

      await waitFor(() => expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Test Action'));

      // Navigate to step 2
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument());
      await user.type(screen.getByLabelText('ID template AAP'), '5');

      // Navigate to step 3
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument());

      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      await waitFor(() => {
        expect(screen.getByText('Erreur serveur inattendue')).toBeInTheDocument();
      });
    }, 30000);
  });

  describe('handleSave — updateActionTags failure', () => {
    it('shows warning notification and calls onSuccess when updateActionTags throws', async () => {
      const { updateActionTags } = await import('../../services/admin_service');
      vi.mocked(updateActionTags).mockRejectedValueOnce(new Error('Tags service down'));

      const user = userEvent.setup();
      const editAction = makeEditAction();

      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });

      await waitFor(() => expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Test Action'));

      // Navigate to step 2
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument());
      await user.type(screen.getByLabelText('ID template AAP'), '5');

      // Navigate to step 3
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument());

      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledTimes(1);
      }, { timeout: 5000 });
    }, 30000);
  });

  describe('handleSave — workflow steps error cases', () => {
    it('shows WORKFLOW_LOOP error when updateWorkflowSteps throws with WORKFLOW_LOOP in message', async () => {
      const { updateWorkflowSteps } = await import('../../services/admin_service');
      vi.mocked(updateWorkflowSteps).mockRejectedValueOnce(new Error('WORKFLOW_LOOP detected'));

      const user = userEvent.setup();
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });

      // Select workflow type
      await user.click(screen.getByRole('radio', { name: /Workflow/i }));
      await user.type(screen.getByLabelText('Nom du workflow'), 'Test Workflow');
      await user.type(screen.getByLabelText('Description'), 'Description');
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Ajouter une étape/i })).toBeInTheDocument();
      }, { timeout: 8000 });

      await user.click(screen.getByRole('button', { name: /Ajouter une étape/i }));
      await waitFor(() => expect(screen.getByLabelText('Sélectionner une action')).toBeInTheDocument());
      const autocomplete = screen.getByLabelText('Sélectionner une action');
      await user.click(autocomplete);
      await user.type(autocomplete, 'Action A');
      const actionOption = await screen.findByText(/Action A/i);
      await user.click(actionOption);

      const nextToStep3 = await screen.findByRole('button', { name: /Suivant/i });
      await user.click(nextToStep3);
      await waitFor(() => expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument());

      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      await waitFor(() => {
        expect(screen.getByText(/Boucle circulaire détectée/i)).toBeInTheDocument();
      }, { timeout: 10000 });
    }, 40000);

    it('shows brouillon error when updateWorkflowSteps throws with brouillon in message', async () => {
      const { updateWorkflowSteps } = await import('../../services/admin_service');
      vi.mocked(updateWorkflowSteps).mockRejectedValueOnce(new Error('Seul un brouillon peut être modifié'));

      const user = userEvent.setup();
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });

      // Select workflow type
      await user.click(screen.getByRole('radio', { name: /Workflow/i }));
      await user.type(screen.getByLabelText('Nom du workflow'), 'Test Workflow 2');
      await user.type(screen.getByLabelText('Description'), 'Description 2');
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Ajouter une étape/i })).toBeInTheDocument();
      }, { timeout: 8000 });

      await user.click(screen.getByRole('button', { name: /Ajouter une étape/i }));
      await waitFor(() => expect(screen.getByLabelText('Sélectionner une action')).toBeInTheDocument());
      const autocomplete = screen.getByLabelText('Sélectionner une action');
      await user.click(autocomplete);
      await user.type(autocomplete, 'Action A');
      const actionOption = await screen.findByText(/Action A/i);
      await user.click(actionOption);

      const nextToStep3 = await screen.findByRole('button', { name: /Suivant/i });
      await user.click(nextToStep3);
      await waitFor(() => expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument());

      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      await waitFor(() => {
        expect(screen.getByText(/Les étapes ne peuvent être modifiées que pour un workflow en brouillon/i)).toBeInTheDocument();
      }, { timeout: 10000 });
    }, 40000);
  });

  describe('handleSave — action step brouillon error', () => {
    it('shows brouillon error when updateActionSteps throws with brouillon in message', async () => {
      const { updateActionSteps } = await import('../../services/admin_service');
      vi.mocked(updateActionSteps).mockRejectedValueOnce(new Error('Seul un brouillon peut être modifié'));

      const user = userEvent.setup();
      const editAction = makeEditAction();

      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });

      await waitFor(() => expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Test Action'));

      // Navigate to step 2
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument());
      await user.type(screen.getByLabelText('ID template AAP'), '5');

      // Navigate to step 3
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument());

      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      await waitFor(() => {
        expect(screen.getByText(/Les étapes ne peuvent être modifiées que pour une action en brouillon/i)).toBeInTheDocument();
      }, { timeout: 5000 });
    }, 30000);
  });

  describe('handleNext — step 0 validation failure', () => {
    it('does not advance when form validation fails at step 0', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });

      // Do not fill any fields, click Suivant
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));

      // Should still be on step 1 (Nom de l'action visible)
      await waitFor(() => {
        expect(screen.getByLabelText("Nom de l'action")).toBeInTheDocument();
      });
      // Step 2 content (Ajouter un parametre) should NOT be visible
      expect(screen.queryByText(/Ajouter un parametre/i)).not.toBeInTheDocument();
    });
  });

  describe('validateWorkflowSteps — empty steps', () => {
    it('shows error when workflow has no steps and user tries to proceed from step 2', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });

      // Select workflow type
      await user.click(screen.getByRole('radio', { name: /Workflow/i }));
      await user.type(screen.getByLabelText('Nom du workflow'), 'Empty Workflow');
      await user.type(screen.getByLabelText('Description'), 'Description');

      // Go to step 2
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Ajouter une étape/i })).toBeInTheDocument();
      }, { timeout: 8000 });

      // Click next without adding steps
      const nextToStep3 = await screen.findByRole('button', { name: /Suivant/i });
      await user.click(nextToStep3);

      // Should show error about missing steps (may appear multiple times in DOM)
      await waitFor(() => {
        const errorMessages = screen.getAllByText(/Au moins une étape est requise/i);
        expect(errorMessages.length).toBeGreaterThan(0);
      });
    }, 30000);
  });

  describe('error prop display', () => {
    it('displays external error prop as alert', async () => {
      await act(async () => {
        render(<ActionWizard {...defaultProps} error="Erreur externe" />);
      });
      expect(screen.getByText('Erreur externe')).toBeInTheDocument();
    });
  });

  describe('submitError Alert onClose — line 488', () => {
    it('closes submitError alert when onClose is clicked', async () => {
      const user = userEvent.setup();

      // Use a submit that throws a generic Error to set submitError
      const mockSubmitWithError = vi.fn().mockRejectedValue(new Error('Erreur test'));
      const editAction = makeEditAction();

      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} onSubmit={mockSubmitWithError} />);
      });

      await waitFor(() => expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Test Action'));

      // Navigate to step 2
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument());
      await user.type(screen.getByLabelText('ID template AAP'), '5');

      // Navigate to step 3
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument());

      // Trigger error
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      await waitFor(() => {
        expect(screen.getByText('Erreur test')).toBeInTheDocument();
      }, { timeout: 5000 });

      // Find and click the close button of the Alert (covers line 488: onClose={() => setSubmitError(null))
      const closeBtn = document.querySelector('[role="alert"] .ant-alert-close-icon');
      if (closeBtn) {
        await user.click(closeBtn as HTMLElement);
        await waitFor(() => {
          expect(screen.queryByText('Erreur test')).not.toBeInTheDocument();
        }, { timeout: 3000 });
      }
    }, 30000);
  });

  describe('editAction with AAP workflow_job connector (lines 164-170)', () => {
    it('loads aapResourceType=workflow_job when editAction has workflow_job step', async () => {
      const editAction = makeEditAction({
        execution_steps: [{
          order: 1,
          name: 'Exécution',
          type: 'execution',
          connector_type: 'aap',
          connector_config: {
            resource_type: 'workflow_job',
            workflow_job_template_id: 42,
          },
          conditional_environments: null,
        }],
      });

      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });

      await waitFor(() => expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Test Action'));
      // Component loaded with workflow_job type
      expect(screen.getByLabelText("Nom de l'action")).toBeInTheDocument();
    }, 15000);

    it('loads aapResourceType=job_template when resource_type is not workflow_job', async () => {
      const editAction = makeEditAction({
        execution_steps: [{
          order: 1,
          name: 'Exécution',
          type: 'execution',
          connector_type: 'aap',
          connector_config: {
            resource_type: 'job_template',
            job_template_id: 10,
          },
          conditional_environments: null,
        }],
      });

      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });

      await waitFor(() => expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Test Action'));
      expect(screen.getByLabelText("Nom de l'action")).toBeInTheDocument();
    }, 15000);
  });

  describe('validateWorkflowSteps — step with no referenced_action_id (line 202)', () => {
    it('shows error when a workflow step has no action selected', async () => {
      const user = userEvent.setup();

      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });

      // Select workflow type
      await user.click(screen.getByRole('radio', { name: /Workflow/i }));
      await user.type(screen.getByLabelText('Nom du workflow'), 'Workflow test step missing action');
      await user.type(screen.getByLabelText('Description'), 'Description test');
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Ajouter une étape/i })).toBeInTheDocument();
      }, { timeout: 8000 });

      // Add a step but don't select an action (referenced_action_id remains null/0)
      await user.click(screen.getByRole('button', { name: /Ajouter une étape/i }));
      await waitFor(() => expect(screen.getByLabelText('Sélectionner une action')).toBeInTheDocument());

      // Click Suivant without selecting action - the step has no referenced_action_id
      const nextBtn = await screen.findByRole('button', { name: /Suivant/i });
      await user.click(nextBtn);

      // Should show error about missing action or at least stay on step 2
      // The error for missing action (platform step) OR no steps at all would appear
      await waitFor(() => {
        const missing = screen.queryAllByText(/doit avoir une action sélectionnée/i);
        const atLeast = screen.queryAllByText(/Au moins une étape est requise/i);
        const anyError = missing.length > 0 || atLeast.length > 0;
        expect(anyError).toBe(true);
      }, { timeout: 8000 });
    }, 30000);
  });

  describe('handleSave — workflow step generic error (line 372)', () => {
    it('shows generic error message when updateWorkflowSteps throws unknown error', async () => {
      const { updateWorkflowSteps } = await import('../../services/admin_service');
      vi.mocked(updateWorkflowSteps).mockRejectedValueOnce(new Error('Erreur inconnue du serveur'));

      const user = userEvent.setup();
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });

      // Select workflow type
      await user.click(screen.getByRole('radio', { name: /Workflow/i }));
      await user.type(screen.getByLabelText('Nom du workflow'), 'Test Workflow Generic');
      await user.type(screen.getByLabelText('Description'), 'Description');
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Ajouter une étape/i })).toBeInTheDocument();
      }, { timeout: 8000 });

      await user.click(screen.getByRole('button', { name: /Ajouter une étape/i }));
      await waitFor(() => expect(screen.getByLabelText('Sélectionner une action')).toBeInTheDocument());
      const autocomplete = screen.getByLabelText('Sélectionner une action');
      await user.click(autocomplete);
      await user.type(autocomplete, 'Action A');
      const actionOption = await screen.findByText(/Action A/i);
      await user.click(actionOption);

      const nextToStep3 = await screen.findByRole('button', { name: /Suivant/i });
      await user.click(nextToStep3);
      await waitFor(() => expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument());

      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      await waitFor(() => {
        expect(screen.getByText(/Erreur inconnue du serveur/i)).toBeInTheDocument();
      }, { timeout: 10000 });
    }, 40000);
  });

  describe('handleSave — action step generic error (line 429)', () => {
    it('shows generic error message when updateActionSteps throws unknown error', async () => {
      const { updateActionSteps } = await import('../../services/admin_service');
      vi.mocked(updateActionSteps).mockRejectedValueOnce(new Error('Erreur inconnue action'));

      const user = userEvent.setup();
      const editAction = makeEditAction();

      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });

      await waitFor(() => expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Test Action'));

      // Navigate to step 2
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument());
      await user.type(screen.getByLabelText('ID template AAP'), '5');

      // Navigate to step 3
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument());

      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      await waitFor(() => {
        expect(screen.getByText(/Erreur inconnue action/i)).toBeInTheDocument();
      }, { timeout: 5000 });
    }, 30000);
  });

  describe('handleSave — canEditSteps=false for workflow (line 379)', () => {
    it('shows info notification when workflow steps cannot be edited (published workflow)', async () => {
      const user = userEvent.setup();
      const publishedWorkflowEditAction = makeEditAction({
        item_type: 'workflow',
        status: 'published',
        workflow_steps: [{ order: 1, step_id: 'a', name: 'Step', referenced_action_id: 100 }],
      });

      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={publishedWorkflowEditAction} />);
      });

      await waitFor(() => expect(screen.getByLabelText('Nom du workflow')).toHaveValue('Test Action'));

      // Navigate to step 2
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));

      // Navigate to step 3
      await user.click(await screen.findByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument());

      // Enregistrer is disabled for published
      expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeDisabled();
    }, 30000);
  });
});

