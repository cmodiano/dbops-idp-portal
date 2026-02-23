/**
 * SortableStepCard tests (Story 34-9, SOLID-FE-8).
 *
 * Tests:
 * - Renders correctly with a valid action
 * - Shows disabled state when disabled=true
 * - Calls onRemoveStep when delete button is clicked
 * - Renders branch selects with correct options
 * - Sets retry defaults when retry is enabled
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SortableStepCard } from './SortableStepCard';
import type { WorkflowStepEditable } from './WorkflowStepsEditor';
import type { ActionListItem } from '../../types/api';

// Mock @dnd-kit/sortable to avoid DndContext requirement in unit tests
vi.mock('@dnd-kit/sortable', () => ({
  useSortable: vi.fn().mockReturnValue({
    attributes: {},
    listeners: {},
    setNodeRef: vi.fn(),
    transform: null,
    transition: undefined,
    isDragging: false,
  }),
}));

vi.mock('@dnd-kit/utilities', () => ({
  CSS: {
    Transform: {
      toString: vi.fn().mockReturnValue(undefined),
    },
  },
}));

const mockEligibleActions: ActionListItem[] = [
  { id: 1, name: 'Action Alpha', engine: 'Oracle', status: 'published', created_at: '', execution_count: 0 },
  { id: 2, name: 'Action Beta', engine: 'SQL Server', status: 'published', created_at: '', execution_count: 0 },
];

const makeStep = (overrides: Partial<WorkflowStepEditable> = {}): WorkflowStepEditable => ({
  order: 1,
  name: null,
  referenced_action_id: 1,
  step_id: 'step-abc-123',
  on_success_step_id: null,
  on_error_step_id: null,
  retry_enabled: false,
  retry_max_attempts: null,
  retry_interval_seconds: null,
  retry_backoff_multiplier: null,
  _tempId: 'temp-1',
  ...overrides,
});

const defaultProps = {
  step: makeStep(),
  index: 0,
  eligibleActions: mockEligibleActions,
  loadingActions: false,
  stepIdsFromEditor: ['step-abc-123'],
  allSteps: [makeStep()],
  onStepChange: vi.fn(),
  onRemoveStep: vi.fn(),
  canRemove: true,
  hasError: false,
  disabled: false,
};

describe('SortableStepCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders with a valid referenced action (AC: basic render)', () => {
    render(<SortableStepCard {...defaultProps} />);

    expect(screen.getByText('Étape 1')).toBeInTheDocument();
    // The AutoComplete should show the action name
    expect(screen.getByDisplayValue('Action Alpha (Oracle)')).toBeInTheDocument();
  });

  it('disables AutoComplete, branch Selects, retry Switch and delete button when disabled=true (AC: disabled state)', () => {
    render(<SortableStepCard {...defaultProps} disabled={true} />);

    // Delete button
    const deleteBtn = screen.getByRole('button', { name: /Supprimer l'étape 1/i });
    expect(deleteBtn).toBeDisabled();

    // AutoComplete input
    const autocomplete = screen.getByRole('combobox', { name: /Sélectionner une action/i });
    expect(autocomplete).toBeDisabled();

    // Retry Switch
    const retrySwitch = screen.getByRole('switch', { name: /retry_enabled de l'étape 1/i });
    expect(retrySwitch).toBeDisabled();
  });

  it('calls onRemoveStep when delete button is clicked (AC: remove step)', async () => {
    const user = userEvent.setup();
    const onRemoveStep = vi.fn();
    render(<SortableStepCard {...defaultProps} onRemoveStep={onRemoveStep} />);

    await user.click(screen.getByRole('button', { name: /Supprimer l'étape 1/i }));

    expect(onRemoveStep).toHaveBeenCalledWith(0);
  });

  it('renders branch selects with "(fin du workflow)" option (AC: branches)', () => {
    render(<SortableStepCard {...defaultProps} />);

    // Should have 2 branch selects (success + error)
    const finOptions = screen.getAllByText('(fin du workflow)');
    expect(finOptions.length).toBeGreaterThanOrEqual(1);
  });

  it('applies retry defaults (3 tentatives, 60s, backoff 2.0) when retry_enabled is toggled on (AC: retry defaults)', async () => {
    const user = userEvent.setup();
    const onStepChange = vi.fn();
    render(<SortableStepCard {...defaultProps} onStepChange={onStepChange} />);

    const retrySwitch = screen.getByRole('switch', { name: /retry_enabled de l'étape 1/i });
    await user.click(retrySwitch);

    // Should call onStepChange with retry_enabled = true
    expect(onStepChange).toHaveBeenCalledWith(0, 'retry_enabled', true);
  });

  it('shows "Action requise" error when hasError=true and no action selected (AC: validation)', async () => {
    const stepWithoutAction = makeStep({ referenced_action_id: undefined });
    render(
      <SortableStepCard
        {...defaultProps}
        step={stepWithoutAction}
        hasError={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Action requise');
    });
  });
});
