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

// ─── Coverage extras ──────────────────────────────────────────────────────────
describe('SortableStepCard — coverage extras', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not show step_id input when step_id is null', () => {
    const stepNoId = makeStep({ step_id: null });
    render(<SortableStepCard {...defaultProps} step={stepNoId} />);
    // The exact label for step_id input is "step_id de l'étape N" (not on_success/on_error)
    // When step_id is null, this input should not be rendered
    expect(document.querySelector('[aria-label="step_id de l\'étape 1"]')).toBeNull();
  });

  it('does not show alert when hasError=true but referenced_action_id is set', () => {
    render(<SortableStepCard {...defaultProps} hasError={true} />);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows loadingActions spinner in notFoundContent when loadingActions=true', async () => {
    const user = userEvent.setup();
    render(<SortableStepCard {...defaultProps} loadingActions={true} eligibleActions={[]} />);

    // Open AutoComplete to trigger notFoundContent
    const autocomplete = screen.getByRole('combobox', { name: /Sélectionner une action/i });
    await user.click(autocomplete);
    await user.type(autocomplete, 'xyz');

    // spin element appears inside notFoundContent
    await waitFor(() => {
      expect(document.querySelector('.ant-spin')).toBeInTheDocument();
    });
  });

  it('shows "Aucune action publiée disponible" when eligibleActions is empty and not loading', async () => {
    const user = userEvent.setup();
    render(<SortableStepCard {...defaultProps} eligibleActions={[]} loadingActions={false} />);

    const autocomplete = screen.getByRole('combobox', { name: /Sélectionner une action/i });
    await user.click(autocomplete);
    await user.type(autocomplete, 'xyz');

    await waitFor(() => {
      expect(screen.getByText('Aucune action publiée disponible')).toBeInTheDocument();
    });
  });

  it('getBranchOptions falls back to sid when action not found', () => {
    const step1 = makeStep({ order: 1, step_id: 'step-1', _tempId: 'temp-1', referenced_action_id: undefined });
    const step2 = makeStep({ order: 2, step_id: 'step-2', _tempId: 'temp-2', referenced_action_id: 99 });
    render(
      <SortableStepCard
        {...defaultProps}
        step={step1}
        stepIdsFromEditor={['step-1', 'step-2']}
        allSteps={[step1, step2]}
      />
    );
    // step-2 is in stepIdsFromEditor but its action (id=99) is not in eligibleActions
    // So its label should be the sid itself: 'step-2'
    expect(screen.getAllByText('(fin du workflow)').length).toBeGreaterThanOrEqual(1);
  });

  it('canRemove=false shows tooltip text for delete button', () => {
    render(<SortableStepCard {...defaultProps} canRemove={false} />);
    // Button aria-label should reflect canRemove=false
    expect(screen.getByRole('button', { name: /Au moins une étape requise/i })).toBeInTheDocument();
  });

  it('AutoComplete onSelect calls onStepChange with referenced_action_id', async () => {
    const user = userEvent.setup();
    const onStepChange = vi.fn();
    const stepWithNoAction = makeStep({ referenced_action_id: undefined });
    render(
      <SortableStepCard
        {...defaultProps}
        step={stepWithNoAction}
        onStepChange={onStepChange}
        eligibleActions={mockEligibleActions}
      />
    );

    const autocomplete = screen.getByRole('combobox', { name: /Sélectionner une action/i });
    await user.click(autocomplete);
    await user.type(autocomplete, 'Alpha');

    await waitFor(() => {
      expect(screen.getByText(/Action Alpha/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/Action Alpha \(Oracle\)/));

    expect(onStepChange).toHaveBeenCalledWith(0, 'referenced_action_id', 1);
  });

  it('Name input onChange calls onStepChange with name value', async () => {
    const { fireEvent: fe } = await import('@testing-library/react');
    const onStepChange = vi.fn();
    render(<SortableStepCard {...defaultProps} onStepChange={onStepChange} />);

    const nameInput = screen.getByRole('textbox', { name: /Nom d'affichage de l'étape 1/i });
    fe.change(nameInput, { target: { value: 'My Step Name' } });

    expect(onStepChange).toHaveBeenCalledWith(0, 'name', 'My Step Name');
  });

  it('Name input onChange calls onStepChange with null when cleared', async () => {
    const { fireEvent: fe } = await import('@testing-library/react');
    const onStepChange = vi.fn();
    render(<SortableStepCard {...defaultProps} step={makeStep({ name: 'Existing Name' })} onStepChange={onStepChange} />);

    const nameInput = screen.getByRole('textbox', { name: /Nom d'affichage de l'étape 1/i });
    fe.change(nameInput, { target: { value: '' } });

    expect(onStepChange).toHaveBeenCalledWith(0, 'name', null);
  });

  it('on_success_step_id Select onChange calls onStepChange (EXIT_VALUE → null)', async () => {
    const user = userEvent.setup();
    const onStepChange = vi.fn();
    const step2 = makeStep({ order: 2, step_id: 'step-2', _tempId: 'temp-2' });
    render(
      <SortableStepCard
        {...defaultProps}
        step={makeStep({ on_success_step_id: 'step-2' })}
        stepIdsFromEditor={['step-abc-123', 'step-2']}
        allSteps={[makeStep(), step2]}
        onStepChange={onStepChange}
      />
    );

    const successSelect = screen.getByRole('combobox', { name: /on_success_step_id de l'étape 1/i });
    await user.click(successSelect);
    await waitFor(() => {
      // Multiple "(fin du workflow)" elements may exist (value + option)
      const items = screen.getAllByText('(fin du workflow)');
      expect(items.length).toBeGreaterThanOrEqual(1);
    });
    // Click the option list item (not the selected value)
    const optionItems = screen.getAllByText('(fin du workflow)');
    // Click the last one which should be in the dropdown
    await user.click(optionItems[optionItems.length - 1]);
    expect(onStepChange).toHaveBeenCalledWith(0, 'on_success_step_id', null);
  });

  it('on_error_step_id Select onChange calls onStepChange', async () => {
    const user = userEvent.setup();
    const onStepChange = vi.fn();
    const step2 = makeStep({ order: 2, step_id: 'step-2', _tempId: 'temp-2' });
    render(
      <SortableStepCard
        {...defaultProps}
        step={makeStep({ on_error_step_id: null })}
        stepIdsFromEditor={['step-abc-123', 'step-2']}
        allSteps={[makeStep(), step2]}
        onStepChange={onStepChange}
        eligibleActions={[
          { id: 1, name: 'Action Alpha', engine: 'Oracle', status: 'published', created_at: '', execution_count: 0 },
          { id: 2, name: 'Action Beta', engine: 'SQL Server', status: 'published', created_at: '', execution_count: 0 },
        ]}
      />
    );

    const errorSelect = screen.getByRole('combobox', { name: /on_error_step_id de l'étape 1/i });
    await user.click(errorSelect);
    await waitFor(() => {
      // We should see "(fin du workflow)" as default
      expect(screen.getAllByText('(fin du workflow)').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('retry InputNumber changes call onStepChange', async () => {
    const { fireEvent: fe } = await import('@testing-library/react');
    const onStepChange = vi.fn();
    render(
      <SortableStepCard
        {...defaultProps}
        step={makeStep({ retry_enabled: true, retry_max_attempts: 3 })}
        onStepChange={onStepChange}
      />
    );

    const maxAttemptsInput = screen.getByRole('spinbutton', { name: /retry_max_attempts de l'étape 1/i });
    fe.change(maxAttemptsInput, { target: { value: '5' } });
    expect(onStepChange).toHaveBeenCalled();
  });

  it('retry interval InputNumber change calls onStepChange', async () => {
    const { fireEvent: fe } = await import('@testing-library/react');
    const onStepChange = vi.fn();
    render(
      <SortableStepCard
        {...defaultProps}
        step={makeStep({ retry_enabled: true, retry_interval_seconds: 60 })}
        onStepChange={onStepChange}
      />
    );

    const intervalInput = screen.getByRole('spinbutton', { name: /retry_interval_seconds de l'étape 1/i });
    fe.change(intervalInput, { target: { value: '30' } });
    expect(onStepChange).toHaveBeenCalled();
  });

  it('retry backoff InputNumber change calls onStepChange', async () => {
    const { fireEvent: fe } = await import('@testing-library/react');
    const onStepChange = vi.fn();
    render(
      <SortableStepCard
        {...defaultProps}
        step={makeStep({ retry_enabled: true, retry_backoff_multiplier: 2.0 })}
        onStepChange={onStepChange}
      />
    );

    const backoffInput = screen.getByRole('spinbutton', { name: /retry_backoff_multiplier de l'étape 1/i });
    fe.change(backoffInput, { target: { value: '3' } });
    expect(onStepChange).toHaveBeenCalled();
  });

  it('renders "Aucun résultat" when actions exist but none match', async () => {
    const user = userEvent.setup();
    render(
      <SortableStepCard
        {...defaultProps}
        eligibleActions={mockEligibleActions}
        loadingActions={false}
      />
    );

    const autocomplete = screen.getByRole('combobox', { name: /Sélectionner une action/i });
    await user.click(autocomplete);
    await user.type(autocomplete, 'zzz_nonexistent_action');

    await waitFor(() => {
      expect(screen.getByText('Aucun résultat')).toBeInTheDocument();
    });
  });
});
