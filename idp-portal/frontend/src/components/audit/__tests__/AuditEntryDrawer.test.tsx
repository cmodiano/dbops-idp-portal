import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AuditEntryDrawer } from '../AuditEntryDrawer';
import type { AuditExecutionEntry } from '../../../types/api';

// Mock ExecutionTimeline to avoid dependency chain
vi.mock('../../execution/ExecutionTimeline', () => ({
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

const defaultProps = {
  open: true,
  execution: null,
  steps: [],
  loading: false,
  error: null,
  onClose: () => {},
};

describe('AuditEntryDrawer', () => {
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
    // "Deploy Prod" appears twice: in "Quoi" (via getEntityLabel → details.action_name) and in "Détails" section
    expect(screen.getAllByText('Deploy Prod').length).toBeGreaterThanOrEqual(1);
    // key "action_name" is shown as label in Détails section
    expect(screen.getByText('action_name')).toBeInTheDocument();
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
    // The non-execution Détails Card must not render for execution entries
    expect(screen.queryByText('Détails')).not.toBeInTheDocument();
    // The execution-specific detail keys (from Détails section) must not appear
    expect(screen.queryByText('action_name')).not.toBeInTheDocument();
  });
});
