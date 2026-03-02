/**
 * Tests for RemediationPanel (Story 34.12, SOLID-FE-1).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RemediationPanel } from './RemediationPanel';
import type { ExecutionResponse, ExecutionStepResponse, ExecutionStatusType } from '../../../types/api';

vi.mock('../StructuredErrorCard', () => ({
  StructuredErrorCard: ({
    quoi,
    pourquoi,
  }: {
    quoi: string;
    pourquoi: string;
  }) => (
    <div data-testid="structured-error-card">
      <span>{quoi}</span>
      <span>{pourquoi}</span>
    </div>
  ),
}));

const failedExecution: ExecutionResponse = {
  id: 1,
  action_id: 10,
  action_name: 'Deploy',
  user_id: 1,
  user_display_name: 'Alice',
  environment: 'prod',
  parameters: null,
  status: 'FAILED',
  servicenow_change_id: null,
  started_at: null,
  completed_at: null,
  created_at: new Date().toISOString(),
  item_type: 'action',
  engine: 'Oracle',
  parent_execution_id: null,
  parent_item_type: null,
};

const failedStep: ExecutionStepResponse = {
  id: 42,
  execution_id: 1,
  step_order: 1,
  step_name: 'Install packages',
  status: 'FAILED',
  error_message: 'Package not found',
  started_at: null,
  completed_at: null,
  output: null,
  platform_job_id: null,
  step_type: 'prerequisite',
};

const baseProps = {
  execution: failedExecution,
  failedStep,
  executionId: 1,
  onViewLogs: vi.fn(),
  suggestionsLoading: false,
  remediationContext: null,
  remediationLoading: false,
};

describe('RemediationPanel', () => {
  it('renders StructuredErrorCard when execution is FAILED and failedStep is present', () => {
    render(<RemediationPanel {...baseProps} />);
    expect(screen.getByTestId('structured-error-card')).toBeInTheDocument();
    expect(screen.getByText('Install packages')).toBeInTheDocument();
    expect(screen.getByText('Package not found')).toBeInTheDocument();
  });

  it('uses fallback error message when error_message is null', () => {
    const stepNoError: ExecutionStepResponse = { ...failedStep, error_message: null };
    render(<RemediationPanel {...baseProps} failedStep={stepNoError} />);
    expect(screen.getByText('Erreur inconnue')).toBeInTheDocument();
  });

  it('does not render StructuredErrorCard when execution is not FAILED', () => {
    const runningExecution = { ...failedExecution, status: 'RUNNING' as const };
    render(<RemediationPanel {...baseProps} execution={runningExecution} />);
    expect(screen.queryByTestId('structured-error-card')).not.toBeInTheDocument();
  });

  it('does not render StructuredErrorCard when failedStep is undefined', () => {
    render(<RemediationPanel {...baseProps} failedStep={undefined} />);
    expect(screen.queryByTestId('structured-error-card')).not.toBeInTheDocument();
  });

  it('does not render when execution is null', () => {
    render(<RemediationPanel {...baseProps} execution={null} />);
    expect(screen.queryByTestId('structured-error-card')).not.toBeInTheDocument();
    expect(screen.queryByText(/Chargement/)).not.toBeInTheDocument();
  });

  it('shows remediation loading skeleton when remediationLoading=true and execution is FAILED', () => {
    render(<RemediationPanel {...baseProps} remediationLoading={true} />);
    expect(screen.getByText('Chargement du contexte de remédiation...')).toBeInTheDocument();
  });

  it('does not show loading skeleton when execution is not FAILED', () => {
    const runningExecution = { ...failedExecution, status: 'RUNNING' as const };
    render(<RemediationPanel {...baseProps} execution={runningExecution} remediationLoading={true} />);
    expect(screen.queryByText('Chargement du contexte de remédiation...')).not.toBeInTheDocument();
  });

  it('shows remediation context card when has_remediation=true and not loading', () => {
    const remediationContext = {
      has_remediation: true,
      successful_remediation: true,
      remediation_actions: [
        {
          execution_id: 99,
          action_name: 'Fix Action',
          status: 'COMPLETED' as ExecutionStatusType,
          created_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
        },
      ],
    };
    render(
      <RemediationPanel
        {...baseProps}
        remediationContext={remediationContext}
        remediationLoading={false}
      />
    );
    expect(screen.getByTestId('remediation-context-card')).toBeInTheDocument();
    expect(screen.getByText('Actions correctives appliquées')).toBeInTheDocument();
    expect(screen.getByText('Fix Action')).toBeInTheDocument();
    expect(screen.getByText('Voir exécution →')).toBeInTheDocument();
  });

  it('shows warning title when successful_remediation=false', () => {
    const remediationContext = {
      has_remediation: true,
      successful_remediation: false,
      remediation_actions: [
        {
          execution_id: 100,
          action_name: 'Failed Fix',
          status: 'FAILED' as ExecutionStatusType,
          created_at: new Date().toISOString(),
          completed_at: null,
        },
      ],
    };
    render(
      <RemediationPanel
        {...baseProps}
        remediationContext={remediationContext}
        remediationLoading={false}
      />
    );
    expect(screen.getByText('Tentatives de correction')).toBeInTheDocument();
    expect(screen.getByText('Échec')).toBeInTheDocument();
  });

  it('does not show context card when has_remediation=false', () => {
    const remediationContext = {
      has_remediation: false,
      successful_remediation: false,
      remediation_actions: [],
    };
    render(
      <RemediationPanel
        {...baseProps}
        remediationContext={remediationContext}
        remediationLoading={false}
      />
    );
    expect(screen.queryByTestId('remediation-context-card')).not.toBeInTheDocument();
  });

  it('does not show context card when remediationContext is null', () => {
    render(<RemediationPanel {...baseProps} remediationContext={null} remediationLoading={false} />);
    expect(screen.queryByTestId('remediation-context-card')).not.toBeInTheDocument();
  });

  it('renders action with RUNNING status tag', () => {
    const remediationContext = {
      has_remediation: true,
      successful_remediation: false,
      remediation_actions: [
        {
          execution_id: 101,
          action_name: 'Running Fix',
          status: 'RUNNING' as ExecutionStatusType,
          created_at: new Date().toISOString(),
          completed_at: null,
        },
      ],
    };
    render(
      <RemediationPanel
        {...baseProps}
        remediationContext={remediationContext}
        remediationLoading={false}
      />
    );
    expect(screen.getByText('RUNNING')).toBeInTheDocument();
  });

  it('renders action with PENDING status (default tag color)', () => {
    const remediationContext = {
      has_remediation: true,
      successful_remediation: false,
      remediation_actions: [
        {
          execution_id: 102,
          action_name: 'Pending Fix',
          status: 'SUBMITTED' as ExecutionStatusType,
          created_at: new Date().toISOString(),
          completed_at: null,
        },
      ],
    };
    render(
      <RemediationPanel
        {...baseProps}
        remediationContext={remediationContext}
        remediationLoading={false}
      />
    );
    expect(screen.getByText('SUBMITTED')).toBeInTheDocument();
  });

  it('shows completed_at when present', () => {
    const completedAt = '2026-01-15T12:30:00Z';
    const remediationContext = {
      has_remediation: true,
      successful_remediation: true,
      remediation_actions: [
        {
          execution_id: 103,
          action_name: 'Done Fix',
          status: 'COMPLETED' as ExecutionStatusType,
          created_at: new Date().toISOString(),
          completed_at: completedAt,
        },
      ],
    };
    render(
      <RemediationPanel
        {...baseProps}
        remediationContext={remediationContext}
        remediationLoading={false}
      />
    );
    // completed_at is rendered in the date text
    expect(screen.getByText(/Terminée:/)).toBeInTheDocument();
  });
});
