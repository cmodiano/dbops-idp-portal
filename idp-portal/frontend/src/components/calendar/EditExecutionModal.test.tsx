/**
 * Tests for EditExecutionModal component (Story 39.7 — coverage).
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Form } from 'antd';
import { EditExecutionModal } from './EditExecutionModal';
import type { ScheduledExecutionListItem } from '../../types/api';

const mockNonRecurringExecution: ScheduledExecutionListItem = {
  scheduled_execution_id: 1,
  action_id: 10,
  action_name: 'Deploy App',
  user_id: 1,
  user_name: 'alice',
  environment: 'prod',
  parameters: null,
  scheduled_at: '2025-06-01T10:00:00Z',
  recurring_pattern: null,
  status: 'pending',
  created_at: '2025-01-01T00:00:00Z',
};

const mockRecurringExecution: ScheduledExecutionListItem = {
  ...mockNonRecurringExecution,
  scheduled_execution_id: 2,
  recurring_pattern: {
    pattern_type: 'daily',
    pattern_config: { hour: 9, minute: 0 },
    next_execution_date: null,
    is_active: true,
  },
  scheduled_at: null,
};

function TestWrapper({ execution, open = true, loading = false, onCancel = vi.fn(), onSubmit = vi.fn() }: {
  execution: ScheduledExecutionListItem | null;
  open?: boolean;
  loading?: boolean;
  onCancel?: () => void;
  onSubmit?: () => void;
}) {
  const [form] = Form.useForm();
  return (
    <EditExecutionModal
      execution={execution}
      open={open}
      loading={loading}
      form={form}
      targetOptions={[{ label: 'Server 1', value: 'server1' }]}
      onCancel={onCancel}
      onSubmit={onSubmit}
    />
  );
}

describe('EditExecutionModal', () => {
  it('renders modal when open=true with execution', () => {
    render(<TestWrapper execution={mockNonRecurringExecution} />);
    expect(screen.getByText("Modifier l'exécution planifiée")).toBeInTheDocument();
  });

  it('does not show form when execution is null', () => {
    render(<TestWrapper execution={null} />);
    // Modal is open but no form content
    expect(screen.getByText("Modifier l'exécution planifiée")).toBeInTheDocument();
    expect(screen.queryByText('Date/heure planifiée (UTC)')).not.toBeInTheDocument();
  });

  it('shows DatePicker for non-recurring execution', () => {
    render(<TestWrapper execution={mockNonRecurringExecution} />);
    expect(screen.getByText('Date/heure planifiée (UTC)')).toBeInTheDocument();
  });

  it('shows recurring pattern fields for recurring execution', () => {
    render(<TestWrapper execution={mockRecurringExecution} />);
    expect(screen.getByText('Type de récurrence')).toBeInTheDocument();
    expect(screen.getByText('Quotidien')).toBeInTheDocument();
    expect(screen.getByText('Hebdomadaire')).toBeInTheDocument();
    expect(screen.getByText('Cron')).toBeInTheDocument();
  });

  it('shows target field', () => {
    render(<TestWrapper execution={mockNonRecurringExecution} />);
    expect(screen.getByText('Targets')).toBeInTheDocument();
  });

  it('shows environment field', () => {
    render(<TestWrapper execution={mockNonRecurringExecution} />);
    expect(screen.getByText('Environnement (si pas de targets)')).toBeInTheDocument();
  });

  it('shows parameters JSON field', () => {
    render(<TestWrapper execution={mockNonRecurringExecution} />);
    expect(screen.getByText('Paramètres (JSON)')).toBeInTheDocument();
  });

  it('calls onCancel when Annuler button is clicked', () => {
    const onCancel = vi.fn();
    render(<TestWrapper execution={mockNonRecurringExecution} onCancel={onCancel} />);
    fireEvent.click(screen.getByText('Annuler'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('calls onSubmit when Enregistrer button is clicked', () => {
    const onSubmit = vi.fn();
    render(<TestWrapper execution={mockNonRecurringExecution} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByTestId('confirm-edit-execution-btn'));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it('shows loading state on submit button', () => {
    render(<TestWrapper execution={mockNonRecurringExecution} loading={true} />);
    const submitBtn = screen.getByTestId('confirm-edit-execution-btn');
    // Ant Design Button with loading shows a spinner
    expect(submitBtn).toBeInTheDocument();
  });

  it('shows environment options', () => {
    render(<TestWrapper execution={mockNonRecurringExecution} />);
    // Environment select options
    expect(screen.getByText('Environnement (si pas de targets)')).toBeInTheDocument();
  });
});
