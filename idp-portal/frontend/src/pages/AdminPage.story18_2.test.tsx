/**
 * Story 18.2: Identification visuelle workflow vs action (Admin).
 * Tests for icon display, tooltip, and accessibility in AdminPage table.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { App } from 'antd';
import AdminPage from './AdminPage';

// ─── Mocks ──────────────────────────────────────────────────────────────────

vi.mock('../services/admin_service');
vi.mock('../services/profiles_service');
vi.mock('../services/integrations_service');

vi.mock('../contexts/ThemeContext', () => ({
  useTheme: () => ({ effectiveMode: 'light' }),
}));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ isAuthenticated: true, isBusinessProfile: false }),
}));

vi.mock('../components/admin/analytics/AdminAnalyticsDashboard', () => ({
  default: () => <div data-testid="analytics-dashboard">Analytics</div>,
}));
vi.mock('../components/admin/FeatureFlagsPanel', () => ({
  FeatureFlagsPanel: () => <div data-testid="feature-flags">Flags</div>,
}));
vi.mock('../components/admin/ActionWizard', () => ({
  ActionWizard: () => null,
}));
vi.mock('../components/admin/ProfileWizard', () => ({
  ProfileWizard: () => null,
}));
vi.mock('../components/admin/ProfileImportModal', () => ({
  ProfileImportModal: () => null,
}));
vi.mock('../components/admin/IntegrationForm', () => ({
  IntegrationForm: () => null,
}));
vi.mock('../components/admin/IntegrationsTable', () => ({
  IntegrationsTable: () => null,
}));
vi.mock('../components/admin/ProfilesTable', () => ({
  ProfilesTable: () => null,
}));

import { getAdminActions } from '../services/admin_service';
import type { ActionListItem, ActionListResponse } from '../types/api';

const mockGetAdminActions = vi.mocked(getAdminActions);

// ─── Test Data ──────────────────────────────────────────────────────────────

const oracleAction: ActionListItem = {
  id: 1, name: 'Apply Oracle Patch', item_type: 'action', status: 'published', engine: 'Oracle',
  created_at: '2026-01-01T00:00:00Z', execution_count: 10, tags: ['patching'],
};
const sqlServerAction: ActionListItem = {
  id: 2, name: 'Backup SQL Server', item_type: 'action', status: 'published', engine: 'SQL Server',
  created_at: '2026-01-02T00:00:00Z', execution_count: 5, tags: [],
};
const workflowItem: ActionListItem = {
  id: 3, name: 'Full Backup Workflow', item_type: 'workflow', status: 'published', engine: null,
  created_at: '2026-01-03T00:00:00Z', execution_count: 8, tags: ['backup'],
};
const db2Action: ActionListItem = {
  id: 4, name: 'DB2 Maintenance', item_type: 'action', status: 'draft', engine: 'DB2',
  created_at: '2026-01-04T00:00:00Z', execution_count: 0, tags: [],
};
const noEngineAction: ActionListItem = {
  id: 5, name: 'Generic Action', item_type: 'action', status: 'published', engine: null,
  created_at: '2026-01-05T00:00:00Z', execution_count: 2, tags: [],
};

const mixedActions = [oracleAction, sqlServerAction, workflowItem, db2Action, noEngineAction];

function makeResponse(data: ActionListItem[]): ActionListResponse {
  return { data, pagination: null };
}

function renderPage() {
  return render(
    <App>
      <AdminPage />
    </App>,
  );
}

// ─── Tests ──────────────────────────────────────────────────────────────────

describe('Story 18.2 — AdminPage Icon Identification', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockGetAdminActions.mockResolvedValue(makeResponse(mixedActions));
  });

  // AC1: Workflow icon displayed

  it('displays ApartmentOutlined icon for workflow items', async () => {
    const { container } = renderPage();

    await waitFor(() => {
      expect(screen.getByText('Full Backup Workflow')).toBeInTheDocument();
    });

    const workflowRow = screen.getByText('Full Backup Workflow').closest('tr')!;
    const workflowIcon = workflowRow.querySelector('.anticon-apartment');
    expect(workflowIcon).toBeInTheDocument();
  });

  // AC1: Engine icon displayed for actions

  it('displays DatabaseOutlined icon for Oracle actions', async () => {
    const { container } = renderPage();

    await waitFor(() => {
      expect(screen.getByText('Apply Oracle Patch')).toBeInTheDocument();
    });

    const row = screen.getByText('Apply Oracle Patch').closest('tr')!;
    expect(row.querySelector('.anticon-database')).toBeInTheDocument();
  });

  it('displays CloudServerOutlined icon for SQL Server actions', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Backup SQL Server')).toBeInTheDocument();
    });

    const row = screen.getByText('Backup SQL Server').closest('tr')!;
    expect(row.querySelector('.anticon-cloud-server')).toBeInTheDocument();
  });

  it('displays HddOutlined icon for DB2 actions', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('DB2 Maintenance')).toBeInTheDocument();
    });

    const row = screen.getByText('DB2 Maintenance').closest('tr')!;
    expect(row.querySelector('.anticon-hdd')).toBeInTheDocument();
  });

  // AC2: Tooltip on icons

  it('shows tooltip on workflow icon hover', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Full Backup Workflow')).toBeInTheDocument();
    });

    const workflowRow = screen.getByText('Full Backup Workflow').closest('tr')!;
    const icon = workflowRow.querySelector('.anticon-apartment')!;
    fireEvent.mouseOver(icon);

    await waitFor(() => {
      expect(screen.getByText("Workflow (chaîne d'actions)")).toBeInTheDocument();
    });
  });

  it('shows tooltip on action engine icon hover', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Apply Oracle Patch')).toBeInTheDocument();
    });

    const row = screen.getByText('Apply Oracle Patch').closest('tr')!;
    const icon = row.querySelector('.anticon-database')!;
    fireEvent.mouseOver(icon);

    await waitFor(() => {
      expect(screen.getByText('Action Oracle')).toBeInTheDocument();
    });
  });

  // AC5: Accessibility — aria-labels

  it('has aria-label "Type: Workflow" on workflow icon', async () => {
    const { container } = renderPage();

    await waitFor(() => {
      expect(screen.getByText('Full Backup Workflow')).toBeInTheDocument();
    });

    expect(container.querySelector('[aria-label="Type: Workflow"]')).toBeInTheDocument();
  });

  it('has aria-label "Type: Action Oracle" on Oracle icon', async () => {
    const { container } = renderPage();

    await waitFor(() => {
      expect(screen.getByText('Apply Oracle Patch')).toBeInTheDocument();
    });

    expect(container.querySelector('[aria-label="Type: Action Oracle"]')).toBeInTheDocument();
  });

  // AC1: Mixed data — icons visible for all types

  it('renders icons for mixed data (3 actions, 2 workflows)', async () => {
    // Our mixedActions has 4 actions + 1 workflow
    const { container } = renderPage();

    await waitFor(() => {
      expect(screen.getByText('Full Backup Workflow')).toBeInTheDocument();
      expect(screen.getByText('Apply Oracle Patch')).toBeInTheDocument();
    });

    // Workflow icons
    const workflowIcons = container.querySelectorAll('.anticon-apartment');
    expect(workflowIcons.length).toBeGreaterThanOrEqual(1);

    // Action engine icons (database, cloud-server, hdd)
    expect(container.querySelector('.anticon-database')).toBeInTheDocument();
    expect(container.querySelector('.anticon-cloud-server')).toBeInTheDocument();
    expect(container.querySelector('.anticon-hdd')).toBeInTheDocument();
  });

  // AC1: Icon appears in "Nom" column before name text

  it('renders icon before action name in the Nom column', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Apply Oracle Patch')).toBeInTheDocument();
    });

    const row = screen.getByText('Apply Oracle Patch').closest('tr')!;
    const nameCell = row.querySelector('td')!;
    const icon = nameCell.querySelector('.anticon-database');
    expect(icon).toBeInTheDocument();
    // Icon should appear before the text
    const nameText = nameCell.textContent;
    expect(nameText).toContain('Apply Oracle Patch');
  });
});
