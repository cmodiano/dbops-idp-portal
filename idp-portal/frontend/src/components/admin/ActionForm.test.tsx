import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ActionForm } from './ActionForm';
import type { ActionDetail } from '../../types/api';
import { useMediaQuery } from '../../hooks/useMediaQuery';

import { updateActionSteps } from '../../services/admin_service';

// Mock the admin_service module (Story 2.6: getTags, updateActionTags)
vi.mock('../../services/admin_service', () => ({
  updateActionSteps: vi.fn().mockResolvedValue({}),
  updateActionRbac: vi.fn().mockResolvedValue({}),
  getTags: vi.fn().mockResolvedValue([]),
  updateActionTags: vi.fn().mockResolvedValue({}),
}));

// Mock useMediaQuery so layout is stable in tests (split view)
vi.mock('../../hooks/useMediaQuery', () => ({ useMediaQuery: vi.fn(() => true) }));

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

describe('ActionForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Split View Layout (Story 2.5, AC #3)', () => {
    it('stacks layout when viewport < 1280px (useMediaQuery false)', async () => {
      vi.mocked(useMediaQuery).mockReturnValueOnce(false);
      await act(async () => {
        render(<ActionForm {...defaultProps} />);
      });
      expect(screen.getByText('Preview')).toBeInTheDocument();
      expect(screen.getByLabelText("Nom de l'action")).toBeInTheDocument();
    });

    it('renders AdminPreview component in split view', async () => {
      await act(async () => {
        render(<ActionForm {...defaultProps} />);
      });

      // AdminPreview should be present with its header
      expect(screen.getByText('Preview')).toBeInTheDocument();
    });

    it('renders both form and preview sections', async () => {
      await act(async () => {
        render(<ActionForm {...defaultProps} />);
      });

      // Form elements
      expect(screen.getByLabelText('Nom de l\'action')).toBeInTheDocument();
      expect(screen.getByLabelText('Description de l\'action')).toBeInTheDocument();

      // Preview elements
      expect(screen.getByText('Carte catalogue')).toBeInTheDocument();
      expect(screen.getByText('Fiche action (drawer)')).toBeInTheDocument();
    });

    it('has aria-live="polite" region for accessibility (AC #5)', async () => {
      await act(async () => {
        render(<ActionForm {...defaultProps} />);
      });

      // Modal renders in a portal, so we need to search the entire document
      const liveRegion = document.querySelector('[aria-live="polite"]');
      expect(liveRegion).toBeInTheDocument();
    });
  });

  describe('Preview Read-Only (Story 2.5, AC #4)', () => {
    it('renders disabled Execute button in preview', async () => {
      await act(async () => {
        render(<ActionForm {...defaultProps} />);
      });

      const executeButton = screen.getByRole('button', { name: /Executer/i });
      expect(executeButton).toBeDisabled();
    });
  });

  describe('Real-time preview (Story 2.5, AC #1, Task 4.5)', () => {
    it('updates preview when form fields change', async () => {
      const user = userEvent.setup();

      await act(async () => {
        render(<ActionForm {...defaultProps} />);
      });

      const nameInput = screen.getByLabelText("Nom de l'action");
      await user.type(nameInput, 'Ma super action');

      await waitFor(() => {
        const cards = screen.getAllByText('Ma super action');
        expect(cards.length).toBeGreaterThanOrEqual(1);
      });
    });
  });

  describe('Form Validation', () => {
    it('shows validation error when name is empty on submit', async () => {
      const user = userEvent.setup();

      await act(async () => {
        render(<ActionForm {...defaultProps} />);
      });

      // Try to submit without filling required fields
      const submitButton = screen.getByText('Creer');
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Le nom est requis')).toBeInTheDocument();
      });
    });

    it('shows error when JSON is invalid', async () => {
      const user = userEvent.setup();

      await act(async () => {
        render(<ActionForm {...defaultProps} />);
      });

      const schemaInput = screen.getByLabelText('Schema des parametres au format JSON');
      await user.type(schemaInput, 'invalid json');
      await user.tab(); // Trigger blur

      await waitFor(() => {
        expect(screen.getByText('JSON invalide')).toBeInTheDocument();
      });
    });
  });

  describe('Edit Mode', () => {
    const mockEditAction: ActionDetail = {
      id: 1,
      name: 'Existing Action',
      description: 'Existing description',
      category: 'Provisioning',
      engine: 'Oracle',
      platform: 'AAP',
      parameters_schema: { type: 'object', properties: { param1: { type: 'string' } } },
      impact_rules: { DEV: { level: 'low' } },
      status: 'draft',
      created_by: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: null,
      rbac_policies: null,
      execution_steps: null,
      change_type_config: null,
    };

    it('populates form with existing action data in edit mode', async () => {
      await act(async () => {
        render(<ActionForm {...defaultProps} editAction={mockEditAction} />);
      });

      await waitFor(() => {
        expect(screen.getByDisplayValue('Existing Action')).toBeInTheDocument();
        expect(screen.getByDisplayValue('Existing description')).toBeInTheDocument();
      });
    });

    it('shows "Modifier l\'action" title in edit mode', async () => {
      await act(async () => {
        render(<ActionForm {...defaultProps} editAction={mockEditAction} />);
      });

      expect(screen.getByText("Modifier l'action")).toBeInTheDocument();
    });

    it('shows "Enregistrer" button in edit mode', async () => {
      await act(async () => {
        render(<ActionForm {...defaultProps} editAction={mockEditAction} />);
      });

      expect(screen.getByText('Enregistrer')).toBeInTheDocument();
    });

    it('save sends change_type_config with only pre_approved, never cab (Story 2.8, AC4)', async () => {
      const user = userEvent.setup();
      const editWithSteps: ActionDetail = {
        ...mockEditAction,
        execution_steps: [
          {
            order: 1,
            name: 'Step',
            type: 'prerequisite',
            connector_type: 'none',
            conditional_environments: null,
          },
        ],
        change_type_config: { DEV: 'pre_approved', PROD: 'pre_approved' },
      };
      await act(async () => {
        render(<ActionForm {...defaultProps} editAction={editWithSteps} />);
      });
      await user.click(screen.getByText('Enregistrer'));

      await waitFor(() => {
        expect(vi.mocked(updateActionSteps)).toHaveBeenCalled();
      });
      const call = vi.mocked(updateActionSteps).mock.calls[0];
      const payload = call[1];
      expect(payload.change_type_config).toBeDefined();
      expect(Object.values(payload.change_type_config!).every((v) => v === 'pre_approved')).toBe(true);
      expect(Object.values(payload.change_type_config!).includes('cab')).toBe(false);
    });
  });

  describe('Modal Behavior', () => {
    it('does not render when open is false', async () => {
      await act(async () => {
        render(<ActionForm {...defaultProps} open={false} />);
      });

      expect(screen.queryByText('Preview')).not.toBeInTheDocument();
    });

    it('calls onCancel when cancel button is clicked', async () => {
      const user = userEvent.setup();

      await act(async () => {
        render(<ActionForm {...defaultProps} />);
      });

      const cancelButton = screen.getByText('Annuler');
      await user.click(cancelButton);

      expect(mockOnCancel).toHaveBeenCalled();
    });
  });
});
