/**
 * ActionWizard tests (Story 2.22, AC #1–#5, Task 7; Story 4.10 AC4).
 * - Wizard 3 steps: Général, Automatisme & Paramètres, Impact & Changement. 1 action = 1 étape. Plateforme définit le connecteur.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ActionWizard } from './ActionWizard';
import type { ActionDetail } from '../../types/api';
import { updateActionSteps, updateWorkflowSteps } from '../../services/admin_service';

vi.mock('../../services/admin_service', () => ({
  getTags: vi.fn().mockResolvedValue([]),
  updateActionTags: vi.fn().mockResolvedValue({}),
  updateActionSteps: vi.fn().mockResolvedValue({}),
  updateWorkflowSteps: vi.fn().mockResolvedValue({}),
  getEligibleActionsForWorkflow: vi.fn().mockResolvedValue([
    { id: 100, name: 'Action A', engine: 'Oracle', status: 'published', created_at: '', execution_count: 0 },
    { id: 101, name: 'Action B', engine: 'SQL Server', status: 'published', created_at: '', execution_count: 0 },
  ]),
}));

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
      expect(screen.getByLabelText('Plateforme')).toBeInTheDocument();
    });
  });

  describe('AC3: Navigation et persistance', () => {
    it('boutons Précédent / Suivant changent l’étape sans perdre le state', async () => {
      const user = userEvent.setup();
      const editAction: ActionDetail = {
        id: 1,
        name: 'Action test',
        description: null,
        engine: 'Oracle',
        platform: 'AAP',
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft',
        created_by: null,
        created_at: '',
        updated_at: null,
        execution_steps: null,
        change_type_config: null,
        tags: [],
      };
      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });

      await waitFor(() => expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Action test'));
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByText(/Ajouter un parametre/i)).toBeInTheDocument());

      await user.click(screen.getByRole('button', { name: /Précédent/i }));
      await waitFor(() => {
        expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Action test');
      });
    });

    it("bouton Enregistrer visible uniquement à l’étape 3", async () => {
      const user = userEvent.setup();
      const editAction: ActionDetail = {
        id: 1,
        name: 'X',
        description: null,
        engine: 'Oracle',
        platform: 'AAP',
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft',
        created_by: null,
        created_at: '',
        updated_at: null,
        execution_steps: null,
        change_type_config: null,
        tags: [],
      };
      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });
      expect(screen.queryByRole('button', { name: /Enregistrer/i })).not.toBeInTheDocument();

      await waitFor(() => expect(screen.getByLabelText("Nom de l'action")).toHaveValue('X'));
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByText(/Ajouter un parametre/i)).toBeInTheDocument());
      expect(screen.queryByRole('button', { name: /Enregistrer/i })).not.toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: /Suivant/i }));
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
        engine: 'Oracle',
        platform: 'AAP',
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft',
        created_by: null,
        created_at: '',
        updated_at: null,
        execution_steps: null,
        change_type_config: null,
        tags: [],
      };
      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });

      await waitFor(() => expect(screen.getByLabelText("Nom de l'action")).toHaveValue('Action à modifier'));
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument());
      await user.type(screen.getByLabelText('ID template AAP'), '42');
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument());
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));
      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledTimes(1);
        const payload = mockOnSubmit.mock.calls[0][0];
        expect(payload.name).toBe('Action à modifier');
        expect(payload.engine).toBe('Oracle');
        expect(payload.platform).toBe('AAP');
        expect(payload.parameters_schema).toBeDefined();
        expect(payload.impact_rules).toBeDefined();
      });
    });
  });

  describe('AC4: Enregistrement', () => {
    it('à l’étape 4, Enregistrer envoie le payload via onSubmit (mode édition pré-rempli)', async () => {
      const user = userEvent.setup();
      const editAction: ActionDetail = {
        id: 10,
        name: 'Action à modifier',
        description: 'Desc',
        engine: 'Oracle',
        platform: 'AAP',
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft',
        created_by: 1,
        created_at: '2025-01-01T00:00:00Z',
        updated_at: null,
        execution_steps: [],
        change_type_config: null,
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
        expect(payload.platform).toBe('AAP');
        expect(payload.parameters_schema).toBeDefined();
        expect(payload.impact_rules).toBeDefined();
      });
    });

    it('en mode création (sans editAction), le wizard affiche l’étape 1 et Enregistrer envoie le payload attendu quand on soumet', async () => {
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });
      expect(screen.getByText('Nouvelle action')).toBeInTheDocument();
      expect(screen.getByLabelText("Nom de l'action")).toBeInTheDocument();
      expect(screen.getByLabelText('Description')).toBeInTheDocument();
      expect(screen.getByRole('combobox', { name: /moteur/i })).toBeInTheDocument();
      expect(screen.getByRole('combobox', { name: /moteur/i })).toBeInTheDocument();
      expect(screen.getByRole('combobox', { name: /plateforme/i })).toBeInTheDocument();
    });
  });

  describe('AC5: Mode édition', () => {
    it('en mode édition les champs sont pré-remplis depuis l’action existante', async () => {
      const editAction: ActionDetail = {
        id: 42,
        name: 'Action existante',
        description: 'Description existante',
        engine: 'SQL Server',
        platform: 'GitHub Actions',
        parameters_schema: { type: 'object', properties: { foo: { type: 'string' } }, required: ['foo'] },
        impact_rules: { DEV: { level: 'low', criteria: null } },
        default_impact_level: 'low',
        status: 'draft',
        created_by: 1,
        created_at: '2025-01-01T00:00:00Z',
        updated_at: null,
        execution_steps: [],
        change_type_config: { PROD: { required: true, change_model_code: '1516B' } },
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
        engine: 'Oracle',
        platform: 'AAP',
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft',
        created_by: null,
        created_at: '',
        updated_at: null,
        execution_steps: null,
        change_type_config: null,
        tags: [],
      };

      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });

      expect(screen.getByText(/Modifier l'action/i)).toBeInTheDocument();
    });
  });

  describe('Story 2.24: change_type_config payload', () => {
    it('calls updateActionSteps with single step and change_type_config when user submits at step 3', async () => {
      const user = userEvent.setup();
      const editAction: ActionDetail = {
        id: 1,
        name: 'Action existante',
        description: null,
        engine: 'Oracle',
        platform: 'AAP',
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft',
        created_by: 1,
        created_at: '2025-01-01T00:00:00Z',
        updated_at: null,
        execution_steps: [],
        change_type_config: null,
        tags: [],
      };
      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument());
      await user.type(screen.getByLabelText('ID template AAP'), '1');
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument());
      const prodSwitch = screen.getByLabelText(/Changement requis pour PROD/i);
      await user.click(prodSwitch);
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));
      await waitFor(() => {
        expect(updateActionSteps).toHaveBeenCalledWith(
          1,
          expect.objectContaining({
            steps: expect.any(Array),
            change_type_config: expect.objectContaining({
              PROD: expect.objectContaining({ required: true }),
            }),
          })
        );
      });
      const callPayload = vi.mocked(updateActionSteps).mock.calls[0][1];
      expect(callPayload.steps).toHaveLength(1);
      expect(callPayload.change_type_config).toBeDefined();
      expect(callPayload.change_type_config!.PROD.required).toBe(true);
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
      expect(screen.getByLabelText('Plateforme')).toBeInTheDocument();

      // Select workflow
      await user.click(screen.getByRole('radio', { name: /Workflow/i }));
      await waitFor(() => {
        expect(screen.queryByLabelText('Moteur')).not.toBeInTheDocument();
        expect(screen.queryByLabelText('Plateforme')).not.toBeInTheDocument();
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
      // Enter a name
      await user.type(screen.getByLabelText('Nom du workflow'), 'Mon Workflow');
      // Go to step 2
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      // Should show WorkflowStepsEditor (shows "Ajouter une étape" button)
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Ajouter une étape/i })).toBeInTheDocument();
      });
    });

    it('type radio est désactivé en mode édition', async () => {
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
        change_type_config: null,
        tags: [],
      };
      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });
      // Radio buttons should be disabled in edit mode
      await waitFor(() => {
        const actionRadio = screen.getByRole('radio', { name: /Action/i });
        expect(actionRadio).toBeDisabled();
        const workflowRadio = screen.getByRole('radio', { name: /Workflow/i });
        expect(workflowRadio).toBeDisabled();
      });
    });

    it('sauvegarde workflow appelle updateWorkflowSteps avec les étapes', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<ActionWizard {...defaultProps} />);
      });
      // Select workflow type
      await user.click(screen.getByRole('radio', { name: /Workflow/i }));
      // Enter a name
      await user.type(screen.getByLabelText('Nom du workflow'), 'Workflow Test');
      // Go to step 2
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      // Wait for eligible actions to load and add a step
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Ajouter une étape/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /Ajouter une étape/i }));
      // Select an action in the autocomplete
      await waitFor(() => {
        expect(screen.getByLabelText('Sélectionner une action')).toBeInTheDocument();
      });
      const autocomplete = screen.getByLabelText('Sélectionner une action');
      await user.click(autocomplete);
      // Type to filter and select
      await user.type(autocomplete, 'Action A');
      await waitFor(() => {
        expect(screen.getByText(/Action A \(Oracle\)/i)).toBeInTheDocument();
      });
      await user.click(screen.getByText(/Action A \(Oracle\)/i));
      // Go to step 3
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument();
      });
      // Save
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));
      // Verify updateWorkflowSteps was called
      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'Workflow Test',
            item_type: 'workflow',
          })
        );
        expect(updateWorkflowSteps).toHaveBeenCalledWith(
          1,
          expect.objectContaining({
            steps: expect.arrayContaining([
              expect.objectContaining({ referenced_action_id: 100 }),
            ]),
          })
        );
      });
    });

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
        change_type_config: null,
        tags: [],
      };
      const user = userEvent.setup();
      await act(async () => {
        render(<ActionWizard {...defaultProps} editAction={editAction} />);
      });
      // Verify workflow type is selected
      await waitFor(() => {
        expect(screen.getByRole('radio', { name: /Workflow/i })).toBeChecked();
      });
      // Go to step 2
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      // Verify steps are loaded
      await waitFor(() => {
        expect(screen.getByText('Étape 1')).toBeInTheDocument();
        expect(screen.getByText('Étape 2')).toBeInTheDocument();
      });
    });
  });
});
