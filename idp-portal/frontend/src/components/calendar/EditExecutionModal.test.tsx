/**
 * Tests for EditExecutionModal — Story 11.11 AC4.
 * Only date field is editable (scheduled_at for one-time, next_execution_date for recurring).
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { App, Form } from 'antd';
import { EditExecutionModal } from './EditExecutionModal';
import type { ScheduledExecutionListItem } from '../../types/api';

const oneTimeExecution: ScheduledExecutionListItem = {
  scheduled_execution_id: 1,
  action_id: 10,
  action_name: 'Test Action',
  user_id: 1,
  user_name: 'test_user',
  environment: 'dev',
  scheduled_at: '2026-04-01T10:00:00Z',
  status: 'pending',
  created_at: '2026-03-01T10:00:00Z',
  parameters: null,
};

const recurringExecution: ScheduledExecutionListItem = {
  ...oneTimeExecution,
  scheduled_execution_id: 2,
  scheduled_at: null,
  recurring_pattern: {
    pattern_type: 'daily',
    pattern_config: { hour: 10, minute: 0 },
    next_execution_date: '2026-04-01T10:00:00Z',
    is_active: true,
  },
};

function Wrapper({ execution, open }: { execution: ScheduledExecutionListItem | null; open: boolean }) {
  const [form] = Form.useForm();
  return (
    <App>
      <EditExecutionModal
        execution={execution}
        open={open}
        loading={false}
        form={form}
        onCancel={vi.fn()}
        onSubmit={vi.fn()}
      />
    </App>
  );
}

describe('EditExecutionModal — Story 11.11 AC4', () => {
  it('shows scheduled_at field for one-time execution', () => {
    render(<Wrapper execution={oneTimeExecution} open />);
    expect(screen.getByText("Date/heure planifiée (heure locale)")).toBeInTheDocument();
    expect(screen.queryByText("Prochaine date d'exécution (heure locale)")).not.toBeInTheDocument();
  });

  it('shows next_execution_date field for recurring execution', () => {
    render(<Wrapper execution={recurringExecution} open />);
    expect(screen.getByText("Prochaine date d'exécution (heure locale)")).toBeInTheDocument();
    expect(screen.queryByText("Date/heure planifiée (heure locale)")).not.toBeInTheDocument();
  });

  it('does not show environment, parameters, or target fields', () => {
    render(<Wrapper execution={oneTimeExecution} open />);
    expect(screen.queryByText('Environnement')).not.toBeInTheDocument();
    expect(screen.queryByText('Paramètres')).not.toBeInTheDocument();
    expect(screen.queryByText('Cibles')).not.toBeInTheDocument();
    expect(screen.queryByText('Type de planification')).not.toBeInTheDocument();
  });

  it('renders nothing when execution is null', () => {
    render(<Wrapper execution={null} open />);
    // Modal is open but no form content
    expect(screen.queryByText("Date/heure planifiée (heure locale)")).not.toBeInTheDocument();
    expect(screen.queryByText("Prochaine date d'exécution (heure locale)")).not.toBeInTheDocument();
  });
});
