/**
 * Tests for AuditEntryDrawer component.
 * Story 43.5 — section "Approbation" pour EXECUTION_APPROVED.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import dayjs from 'dayjs';
import { AuditEntryDrawer } from './AuditEntryDrawer';
import type { AuditExecutionEntry, ExecutionResponse, ExecutionStepResponse } from '../../types/api';

vi.mock('../execution/ExecutionTimeline', () => ({
  ExecutionTimeline: () => <div data-testid="execution-timeline" />,
}));

const mockApprovedEntry: AuditExecutionEntry = {
  id: 1,
  entity_id: 123,
  item_type: 'action',
  user_id: '42',
  user_name: 'Jean Dupont',
  action_name: 'Deploy Prod',
  derived_status: 'success',
  timestamp: '2025-01-15T10:30:00Z',
  action_type: 'EXECUTION_APPROVED',
  entity_type: 'execution',
  ip_address: null,
  correlation_id: null,
  details: {
    action_id: 5,
    environment: 'prod',
    servicenow_change_id: undefined,
  },
};

const mockExecution: ExecutionResponse = {
  id: 123,
  action_id: 5,
  action_name: 'Deploy Prod',
  user_id: 10,
  environment: 'prod',
  parameters: null,
  status: 'COMPLETED',
  servicenow_change_id: null,
  started_at: '2025-01-15T10:00:00Z',
  completed_at: '2025-01-15T10:30:00Z',
  created_at: '2025-01-15T09:55:00Z',
  approved_at: '2025-01-15T09:58:00Z',
  approval_comment: 'Approuvé avec réserves',
};

const mockSteps: ExecutionStepResponse[] = [];

const defaultProps = {
  open: true,
  entry: mockApprovedEntry,
  execution: null,
  steps: mockSteps,
  loading: false,
  error: null,
  onClose: vi.fn(),
};

describe('AuditEntryDrawer', () => {
  it('test_drawer_shows_approval_section_for_execution_approved — section Approbation présente pour EXECUTION_APPROVED', () => {
    render(<AuditEntryDrawer {...defaultProps} />);
    expect(screen.getByText('Approbation')).toBeInTheDocument();
    // Jean Dupont apparaît dans "Qui" et "Approuvé par" — au moins 2 occurrences
    expect(screen.getAllByText('Jean Dupont').length).toBeGreaterThanOrEqual(2);
  });

  it('test_drawer_shows_approval_comment_when_available — affiche le commentaire si disponible', () => {
    render(<AuditEntryDrawer {...defaultProps} execution={mockExecution} />);
    expect(screen.getByText('Approuvé avec réserves')).toBeInTheDocument();
  });

  it('test_drawer_shows_approval_date_when_available — affiche la date d\'approbation si disponible', () => {
    render(<AuditEntryDrawer {...defaultProps} execution={mockExecution} />);
    const expectedDate = dayjs(mockExecution.approved_at!).format('DD/MM/YYYY HH:mm');
    expect(screen.getByText(expectedDate)).toBeInTheDocument();
  });

  it('test_drawer_no_approval_section_for_other_action_types — pas de section Approbation pour EXECUTION_SUBMITTED', () => {
    const submittedEntry: AuditExecutionEntry = {
      ...mockApprovedEntry,
      action_type: 'EXECUTION_SUBMITTED',
    };
    render(<AuditEntryDrawer {...defaultProps} entry={submittedEntry} />);
    expect(screen.queryByText('Approbation')).not.toBeInTheDocument();
  });

  it('test_drawer_approval_section_minimal_without_execution — affiche au minimum Approuvé par sans exécution chargée', () => {
    render(<AuditEntryDrawer {...defaultProps} execution={null} />);
    expect(screen.getByText('Approbation')).toBeInTheDocument();
    expect(screen.getAllByText('Jean Dupont').length).toBeGreaterThanOrEqual(1);
  });
});
