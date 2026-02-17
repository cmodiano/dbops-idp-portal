/**
 * WorkflowStepsEditor tests (Story 9.5, AC #2, #4).
 * - Add/remove/reorder workflow steps
 * - AutoComplete for action selection
 * - Validation (at least 1 step, each step needs action)
 * - Accessibility (aria-labels, role="alert")
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WorkflowStepsEditor } from './WorkflowStepsEditor';
import type { WorkflowStep } from '../../types/api';

// Mock the admin service
vi.mock('../../services/admin_service', () => ({
  getEligibleActionsForWorkflow: vi.fn().mockResolvedValue([
    { id: 1, name: 'Action Alpha', engine: 'Oracle', status: 'published', created_at: '', execution_count: 0 },
    { id: 2, name: 'Action Beta', engine: 'SQL Server', status: 'published', created_at: '', execution_count: 0 },
    { id: 3, name: 'Action Gamma', engine: 'DB2', status: 'published', created_at: '', execution_count: 0 },
  ]),
}));

const mockOnChange = vi.fn();

const defaultProps = {
  steps: [] as WorkflowStep[],
  onChange: mockOnChange,
  loading: false,
};

describe('WorkflowStepsEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Affichage initial', () => {
    it('affiche "Au moins une étape est requise" quand la liste est vide', async () => {
      await act(async () => {
        render(<WorkflowStepsEditor {...defaultProps} steps={[]} />);
      });
      await waitFor(() => {
        expect(screen.getByText(/Au moins une étape est requise/i)).toBeInTheDocument();
      });
    });

    it('affiche le bouton "Ajouter une étape"', async () => {
      await act(async () => {
        render(<WorkflowStepsEditor {...defaultProps} />);
      });
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Ajouter une étape/i })).toBeInTheDocument();
      });
    });
  });

  describe('Ajout d\'étape', () => {
    it('ajoute une nouvelle étape avec ordre=1 quand on clique "Ajouter"', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<WorkflowStepsEditor {...defaultProps} />);
      });
      // Wait for eligible actions to load
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Ajouter une étape/i })).toBeEnabled();
      });
      await user.click(screen.getByRole('button', { name: /Ajouter une étape/i }));
      // Should show "Étape 1"
      await waitFor(() => {
        expect(screen.getByText('Étape 1')).toBeInTheDocument();
      });
    });

    it('ajouter 2 étapes génère ordres 1 et 2', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<WorkflowStepsEditor {...defaultProps} />);
      });
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Ajouter une étape/i })).toBeEnabled();
      });
      // Add first step
      await user.click(screen.getByRole('button', { name: /Ajouter une étape/i }));
      await waitFor(() => expect(screen.getByText('Étape 1')).toBeInTheDocument());
      // Add second step
      await user.click(screen.getByRole('button', { name: /Ajouter une étape/i }));
      await waitFor(() => {
        expect(screen.getByText('Étape 1')).toBeInTheDocument();
        expect(screen.getByText('Étape 2')).toBeInTheDocument();
      });
    });
  });

  describe('Suppression d\'étape', () => {
    it('supprimer 1 étape sur 2 renumérote les ordres correctement', async () => {
      const user = userEvent.setup();
      const initialSteps: WorkflowStep[] = [
        { order: 1, name: 'First', referenced_action_id: 1 },
        { order: 2, name: 'Second', referenced_action_id: 2 },
      ];
      await act(async () => {
        render(<WorkflowStepsEditor {...defaultProps} steps={initialSteps} />);
      });
      await waitFor(() => {
        expect(screen.getByText('Étape 1')).toBeInTheDocument();
        expect(screen.getByText('Étape 2')).toBeInTheDocument();
      });
      // Delete first step
      const deleteButtons = screen.getAllByRole('button', { name: /Supprimer/i });
      await user.click(deleteButtons[0]);
      // onChange should be called with renumbered steps
      await waitFor(() => {
        expect(mockOnChange).toHaveBeenLastCalledWith([
          expect.objectContaining({ order: 1, referenced_action_id: 2 }),
        ]);
      });
    });

    it('bouton supprimer désactivé quand une seule étape (au moins 1 requise)', async () => {
      const initialSteps: WorkflowStep[] = [
        { order: 1, name: 'Only', referenced_action_id: 1 },
      ];
      await act(async () => {
        render(<WorkflowStepsEditor {...defaultProps} steps={initialSteps} />);
      });
      await waitFor(() => {
        expect(screen.getByText('Étape 1')).toBeInTheDocument();
      });
      // Delete button should be disabled
      const deleteButton = screen.getByRole('button', { name: /Au moins une étape requise/i });
      expect(deleteButton).toBeDisabled();
    });
  });

  describe('Sélection d\'action via AutoComplete', () => {
    it('sélectionner une action met à jour referenced_action_id et appelle onChange', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<WorkflowStepsEditor {...defaultProps} />);
      });
      // Add a step
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Ajouter une étape/i })).toBeEnabled();
      });
      await user.click(screen.getByRole('button', { name: /Ajouter une étape/i }));
      // Find the autocomplete
      await waitFor(() => {
        expect(screen.getByLabelText('Sélectionner une action')).toBeInTheDocument();
      });
      const autocomplete = screen.getByLabelText('Sélectionner une action');
      await user.click(autocomplete);
      await user.type(autocomplete, 'Alpha');
      // Select from dropdown
      await waitFor(() => {
        expect(screen.getByText(/Action Alpha \(Oracle\)/i)).toBeInTheDocument();
      });
      await user.click(screen.getByText(/Action Alpha \(Oracle\)/i));
      // onChange should be called with the selected action
      await waitFor(() => {
        expect(mockOnChange).toHaveBeenLastCalledWith([
          expect.objectContaining({ referenced_action_id: 1 }),
        ]);
      });
    });
  });

  describe('Story 16.2 — champs branches & retry', () => {
    it('activer retry applique les défauts (3, 60, 2.0) et les remonte via onChange', async () => {
      const user = userEvent.setup();
      const initialSteps: WorkflowStep[] = [{ order: 1, name: 'Step 1', referenced_action_id: 1 }];
      await act(async () => {
        render(<WorkflowStepsEditor {...defaultProps} steps={initialSteps} />);
      });
      await waitFor(() => {
        expect(screen.getByLabelText(/retry_enabled de l'étape 1/i)).toBeInTheDocument();
      });

      // Toggle retry ON
      await user.click(screen.getByLabelText(/retry_enabled de l'étape 1/i));

      await waitFor(() => {
        expect(mockOnChange).toHaveBeenLastCalledWith([
          expect.objectContaining({
            retry_enabled: true,
            retry_max_attempts: 3,
            retry_interval_seconds: 60,
            retry_backoff_multiplier: 2.0,
          }),
        ]);
      });
    });
  });

  describe('Validation', () => {
    it('affiche validateStatus=error sur AutoComplete quand action non sélectionnée', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<WorkflowStepsEditor {...defaultProps} />);
      });
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Ajouter une étape/i })).toBeEnabled();
      });
      // Add a step without selecting action
      await user.click(screen.getByRole('button', { name: /Ajouter une étape/i }));
      await waitFor(() => {
        expect(screen.getByText('Étape 1')).toBeInTheDocument();
      });
      // The "Action requise" error should appear
      await waitFor(() => {
        expect(screen.getByRole('alert')).toHaveTextContent(/Action requise/i);
      });
    });
  });

  describe('Loading state', () => {
    it('affiche Spin quand loading=true', async () => {
      await act(async () => {
        render(<WorkflowStepsEditor {...defaultProps} loading={true} />);
      });
      // Should show spinner - Ant Design Spin has aria-busy="true" and specific class
      const spinner = document.querySelector('.ant-spin');
      expect(spinner).toBeInTheDocument();
    });
  });

  describe('Accessibilité', () => {
    it('AutoComplete a aria-label "Sélectionner une action"', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<WorkflowStepsEditor {...defaultProps} />);
      });
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Ajouter une étape/i })).toBeEnabled();
      });
      await user.click(screen.getByRole('button', { name: /Ajouter une étape/i }));
      await waitFor(() => {
        expect(screen.getByLabelText('Sélectionner une action')).toBeInTheDocument();
      });
    });

    it('bouton Ajouter a aria-label', async () => {
      await act(async () => {
        render(<WorkflowStepsEditor {...defaultProps} />);
      });
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Ajouter une étape/i })).toBeInTheDocument();
      });
    });

    it('erreurs affichées avec role="alert"', async () => {
      await act(async () => {
        render(<WorkflowStepsEditor {...defaultProps} steps={[]} />);
      });
      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });
    });
  });

  describe('Pré-remplissage pour édition', () => {
    it('affiche les étapes existantes avec leurs actions sélectionnées', async () => {
      const existingSteps: WorkflowStep[] = [
        { order: 1, name: 'Step One', referenced_action_id: 1 },
        { order: 2, name: 'Step Two', referenced_action_id: 2 },
      ];
      await act(async () => {
        render(<WorkflowStepsEditor {...defaultProps} steps={existingSteps} />);
      });
      await waitFor(() => {
        expect(screen.getByText('Étape 1')).toBeInTheDocument();
        expect(screen.getByText('Étape 2')).toBeInTheDocument();
      });
      // Check that actions are displayed (after eligible actions load)
      await waitFor(() => {
        // The autocomplete should show the action name
        const autocompletes = screen.getAllByLabelText('Sélectionner une action');
        expect(autocompletes).toHaveLength(2);
      });
    });
  });
});
