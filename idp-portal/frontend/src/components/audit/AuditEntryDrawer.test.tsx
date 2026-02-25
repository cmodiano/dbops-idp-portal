/**
 * Tests for AuditEntryDrawer component.
 * Story 43.5 — section "Approbation" pour EXECUTION_APPROVED.
 * Story 43.7 — entity-type conditional rendering, Détails section.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import dayjs from 'dayjs';
import { AuditEntryDrawer } from './AuditEntryDrawer';
import type { AuditExecutionEntry, ExecutionResponse, ExecutionStepResponse } from '../../types/api';

vi.mock('../execution/ExecutionTimeline', () => ({
  ExecutionTimeline: () => <div data-testid="execution-timeline" />,
}));

const executionEntry: AuditExecutionEntry = {
  id: 1,
  timestamp: '2026-02-24T10:00:00Z',
  user_id: 'user-42',
  user_name: 'Jean Dupont',
  action_type: 'EXECUTION_COMPLETED',
  entity_type: 'execution',
  entity_id: 999,
  details: { environment: 'PROD', status: 'COMPLETED', parameters: { target: 'server-01' } },
  ip_address: '10.0.0.1',
  correlation_id: 'corr-abc',
  derived_status: 'success',
};

const actionEntry: AuditExecutionEntry = {
  ...executionEntry,
  action_type: 'ACTION_PUBLISHED',
  entity_type: 'action',
  entity_id: 42,
  details: { action_name: 'Deploy Prod', previous_status: 'DRAFT', new_status: 'PUBLISHED' },
  derived_status: 'unknown',
};

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

  // Story 43.7 — entity-type conditional rendering
  it('affiche Environnement et Résultat pour une entrée execution', () => {
    render(<AuditEntryDrawer {...defaultProps} entry={executionEntry} />);
    expect(screen.getByText('Environnement')).toBeInTheDocument();
    expect(screen.getByText('Résultat')).toBeInTheDocument();
  });

  it('masque Environnement et Résultat pour une entrée action', () => {
    render(<AuditEntryDrawer {...defaultProps} entry={actionEntry} />);
    expect(screen.queryByText('Environnement')).not.toBeInTheDocument();
    expect(screen.queryByText('Résultat')).not.toBeInTheDocument();
  });

  it('affiche la section Détails pour une entrée action avec details', () => {
    render(<AuditEntryDrawer {...defaultProps} entry={actionEntry} />);
    expect(screen.getByText('Détails')).toBeInTheDocument();
    expect(screen.getAllByText('Deploy Prod').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Nom de l\'action')).toBeInTheDocument();
  });

  it('affiche le titre dynamique selon entity_type', () => {
    render(<AuditEntryDrawer {...defaultProps} entry={actionEntry} />);
    expect(screen.getByText(/Détail — Action/i)).toBeInTheDocument();
  });

  it('affiche les champs communs (Qui, Quoi, Quand) pour tous les types', () => {
    render(<AuditEntryDrawer {...defaultProps} entry={actionEntry} />);
    expect(screen.getByText('Qui')).toBeInTheDocument();
    expect(screen.getByText('Quoi')).toBeInTheDocument();
    expect(screen.getByText('Quand')).toBeInTheDocument();
  });

  it('ne affiche pas la section Détails pour une entrée execution', () => {
    render(<AuditEntryDrawer {...defaultProps} entry={executionEntry} />);
    expect(screen.queryByText('Détails')).not.toBeInTheDocument();
    expect(screen.queryByText('Nom de l\'action')).not.toBeInTheDocument();
  });
});
