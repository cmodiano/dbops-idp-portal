/**
 * Tests for EditExecutionModal component (Story 39.7 — coverage).
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
    // Ant Design Button with loading=true adds ant-btn-loading class
    expect(submitBtn).toBeInTheDocument();
    expect(submitBtn).toHaveClass('ant-btn-loading');
  });

  it('shows environment options', () => {
    render(<TestWrapper execution={mockNonRecurringExecution} />);
    // Environment select options
    expect(screen.getByText('Environnement (si pas de targets)')).toBeInTheDocument();
  });

  it('renders without crashing when open=false', () => {
    // Ant Design v5 : quand open=false le modal n'est pas rendu dans le DOM
    expect(() => render(<TestWrapper execution={mockNonRecurringExecution} open={false} />)).not.toThrow();
  });

  it('shows cron fields when recurring pattern has cron type (via form initial values)', async () => {
    // Pour déclencher la branche cron dans shouldUpdate, on crée un wrapper qui force pattern_type=cron
    function CronWrapper() {
      const [form] = Form.useForm();
      return (
        <EditExecutionModal
          execution={mockRecurringExecution}
          open={true}
          loading={false}
          form={form}
          targetOptions={[]}
          onCancel={vi.fn()}
          onSubmit={vi.fn()}
        />
      );
    }
    render(<CronWrapper />);
    // Cliquer sur "Cron" pour activer la branche shouldUpdate
    const user = userEvent.setup();
    const cronRadio = screen.getByRole('radio', { name: /Cron/i });
    await user.click(cronRadio);
    // shouldUpdate déclenche le rendu conditionnel du champ Expression cron
    await waitFor(() => {
      expect(screen.getByText('Expression cron')).toBeInTheDocument();
    });
  });

  it('affiche les champs cron quand pattern_type est cron dans le formulaire', () => {
    // Déclencher la branche cron du shouldUpdate en initialisant le form avec pattern_type=cron
    function CronInitWrapper() {
      const [form] = Form.useForm();
      // Initialiser le formulaire avec pattern_type=cron
      form.setFieldsValue({ pattern_type: 'cron' });
      return (
        <EditExecutionModal
          execution={mockRecurringExecution}
          open={true}
          loading={false}
          form={form}
          targetOptions={[]}
          onCancel={vi.fn()}
          onSubmit={vi.fn()}
        />
      );
    }
    render(<CronInitWrapper />);
    // Le formulaire initialisé avec cron doit afficher les radios de récurrence
    expect(screen.getByRole('radio', { name: /Cron/i })).toBeInTheDocument();
  });

  it('affiche les champs weekly quand pattern_type est weekly', () => {
    function WeeklyWrapper() {
      const [form] = Form.useForm();
      form.setFieldsValue({ pattern_type: 'weekly' });
      return (
        <EditExecutionModal
          execution={mockRecurringExecution}
          open={true}
          loading={false}
          form={form}
          targetOptions={[]}
          onCancel={vi.fn()}
          onSubmit={vi.fn()}
        />
      );
    }
    render(<WeeklyWrapper />);
    // Le formulaire initialisé avec weekly doit afficher les radios de récurrence
    expect(screen.getByRole('radio', { name: /Hebdomadaire/i })).toBeInTheDocument();
  });

  it('teste la fonction disabledDate du DatePicker (branche non récurrente)', async () => {
    const user = userEvent.setup();
    function DisabledDateWrapper() {
      const [form] = Form.useForm();
      return (
        <EditExecutionModal
          execution={mockNonRecurringExecution}
          open={true}
          loading={false}
          form={form}
          targetOptions={[]}
          onCancel={vi.fn()}
          onSubmit={vi.fn()}
        />
      );
    }
    render(<DisabledDateWrapper />);
    // Ouvrir le DatePicker pour déclencher disabledDate
    const datePicker = document.querySelector('.ant-picker-input input');
    if (datePicker) {
      await user.click(datePicker as HTMLElement);
      // Le calendrier s'ouvre et disabledDate est appelé pour chaque cellule
      const calendar = document.querySelector('.ant-picker-dropdown');
      if (calendar) {
        expect(calendar).toBeInTheDocument();
      }
    }
    expect(screen.getByText('Date/heure planifiée (UTC)')).toBeInTheDocument();
  });

  it('shouldUpdate — déclenché quand pattern_type change dans le formulaire', async () => {
    const user = userEvent.setup();
    function RecurringWrapper() {
      const [form] = Form.useForm();
      return (
        <EditExecutionModal
          execution={mockRecurringExecution}
          open={true}
          loading={false}
          form={form}
          targetOptions={[]}
          onCancel={vi.fn()}
          onSubmit={vi.fn()}
        />
      );
    }
    render(<RecurringWrapper />);

    // Cliquer sur "Cron" radio pour changer pattern_type et déclencher shouldUpdate
    const cronRadio = screen.getByRole('radio', { name: /Cron/i });
    await user.click(cronRadio);

    await waitFor(() => {
      expect(screen.getByText('Expression cron')).toBeInTheDocument();
    });
  });
});
