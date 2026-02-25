/**
 * Tests for IntegrationsTable (Story 2.28, AC2, AC6).
 * Story 5.5: Uses App.useApp().modal.confirm (Ant Design 6.2).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { IntegrationsTable } from './IntegrationsTable';
import type { IntegrationListItem } from '../../types/api';

const mockModalConfirm = vi.fn();

function renderWithApp(ui: React.ReactElement) {
  vi.spyOn(App, 'useApp').mockReturnValue({
    message: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn(), loading: vi.fn(), open: vi.fn(), destroy: vi.fn() },
    notification: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn(), open: vi.fn() },
    modal: { confirm: mockModalConfirm },
  } as unknown as ReturnType<typeof App.useApp>);
  return render(<App>{ui}</App>);
}

const items: IntegrationListItem[] = [
  {
    id: 1,
    type: 'aap',
    name: 'AAP Prod',
    base_url: 'https://aap.example.com',
    credential_ref: null,
    icon: null,
    auth_flow: null,
    token_url: null,
    status: 'valid',
    created_at: '2026-01-28T10:00:00Z',
    updated_at: '2026-01-28T10:00:00Z',
  },
];

const mockOnEdit = vi.fn();
const mockOnDelete = vi.fn().mockResolvedValue(undefined);
const mockOnNew = vi.fn();

const defaultProps = {
  dataSource: items,
  loading: false,
  onEdit: mockOnEdit,
  onDelete: mockOnDelete,
  onNew: mockOnNew,
};

describe('IntegrationsTable', () => {
  beforeEach(() => {
    mockModalConfirm.mockReset();
  });

  it('renders table with columns Icône, Nom, Type, URL, Date de création', () => {
    renderWithApp(<IntegrationsTable {...defaultProps} />);
    expect(screen.getByText('Icône')).toBeInTheDocument();
    expect(screen.getByText('Nom')).toBeInTheDocument();
    expect(screen.getByText('Type')).toBeInTheDocument();
    expect(screen.getByText('URL')).toBeInTheDocument();
    expect(screen.getByText('Date de création')).toBeInTheDocument();
  });

  it('renders integrations and Nouvelle intégration button', () => {
    renderWithApp(<IntegrationsTable {...defaultProps} />);
    expect(screen.getByText('AAP Prod')).toBeInTheDocument();
    expect(screen.getByText('aap')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Nouvelle intégration/i })).toBeInTheDocument();
  });

  it('calls onNew when Nouvelle intégration clicked', async () => {
    const user = userEvent.setup();
    renderWithApp(<IntegrationsTable {...defaultProps} />);
    await user.click(screen.getByRole('button', { name: /Nouvelle intégration/i }));
    expect(mockOnNew).toHaveBeenCalled();
  });

  it('calls onEdit when Modifier clicked', async () => {
    const user = userEvent.setup();
    renderWithApp(<IntegrationsTable {...defaultProps} />);
    await user.click(screen.getByRole('button', { name: /Modifier/i }));
    expect(mockOnEdit).toHaveBeenCalledWith(items[0]);
  });

  it('shows confirmation modal and calls onDelete when Supprimer clicked and confirmed', async () => {
    let confirmOnOk: () => void = () => {};
    mockModalConfirm.mockImplementation((opts: { onOk?: () => void }) => {
      confirmOnOk = opts?.onOk ?? (() => {});
      return { destroy: vi.fn(), update: vi.fn() };
    });
    const user = userEvent.setup();
    renderWithApp(<IntegrationsTable {...defaultProps} />);
    await user.click(screen.getByRole('button', { name: /Supprimer/i }));
    expect(mockModalConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Supprimer l\'intégration',
        content: expect.stringContaining('AAP Prod'),
        okText: 'Supprimer',
        okType: 'danger',
        cancelText: 'Annuler',
      })
    );
    await confirmOnOk();
    expect(mockOnDelete).toHaveBeenCalledWith(items[0]);
  });

  it('shows empty state when no integrations', () => {
    renderWithApp(<IntegrationsTable {...defaultProps} dataSource={[]} />);
    expect(screen.getByText('Aucune intégration')).toBeInTheDocument();
  });

  it('renders Avatar when integration has icon URL', () => {
    const itemsWithIcon: IntegrationListItem[] = [
      {
        id: 2,
        type: 'terraform',
        name: 'Terraform Cloud',
        base_url: 'https://terraform.example.com',
        credential_ref: null,
        icon: 'https://example.com/terraform-icon.png',
        auth_flow: null,
        token_url: null,
        created_at: '2026-01-28T10:00:00Z',
        updated_at: '2026-01-28T10:00:00Z',
      },
    ];
    renderWithApp(<IntegrationsTable {...defaultProps} dataSource={itemsWithIcon} />);
    // When icon is a URL, an img element should be rendered inside Avatar
    const avatarImg = document.querySelector('img[src="https://example.com/terraform-icon.png"]');
    expect(avatarImg).toBeInTheDocument();
  });

  it('renders preset icon when integration has no icon URL', () => {
    // items[0] has icon: null, so it should render the preset icon for 'aap' type
    renderWithApp(<IntegrationsTable {...defaultProps} />);
    // Avatar with URL would have img tag, preset icon doesn't have img
    // Find the icon column cell and verify it doesn't contain an Avatar img
    const rows = document.querySelectorAll('.ant-table-row');
    expect(rows.length).toBeGreaterThan(0);
    const firstRow = rows[0];
    const iconCell = firstRow.querySelector('td');
    const avatarImg = iconCell?.querySelector('img');
    expect(avatarImg).not.toBeInTheDocument();
  });

  it('calls onRefresh when Actualiser clicked', async () => {
    const mockOnRefresh = vi.fn();
    const user = userEvent.setup();
    renderWithApp(<IntegrationsTable {...defaultProps} onRefresh={mockOnRefresh} />);
    await user.click(screen.getByRole('button', { name: /Actualiser/i }));
    expect(mockOnRefresh).toHaveBeenCalled();
  });

  // Story 24.3: Status column tests
  it('renders Statut column header', () => {
    renderWithApp(<IntegrationsTable {...defaultProps} />);
    expect(screen.getByText('Statut')).toBeInTheDocument();
  });

  it('renders Valide badge for status=valid', () => {
    renderWithApp(<IntegrationsTable {...defaultProps} />);
    expect(screen.getByText('Valide')).toBeInTheDocument();
  });

  it('renders Invalide badge for status=invalid', () => {
    const invalidItems: IntegrationListItem[] = [
      { ...items[0], id: 2, name: 'Invalid One', status: 'invalid' },
    ];
    renderWithApp(<IntegrationsTable {...defaultProps} dataSource={invalidItems} />);
    expect(screen.getByText('Invalide')).toBeInTheDocument();
  });

  it('renders Déprécié badge for status=deprecated', () => {
    const deprecatedItems: IntegrationListItem[] = [
      { ...items[0], id: 3, name: 'Deprecated One', status: 'deprecated' },
    ];
    renderWithApp(<IntegrationsTable {...defaultProps} dataSource={deprecatedItems} />);
    expect(screen.getByText('Déprécié')).toBeInTheDocument();
  });

  it('renders Re-valider button per row', () => {
    renderWithApp(<IntegrationsTable {...defaultProps} />);
    // Both "Re-valider" (per row) and "Re-valider tout" (toolbar) exist
    const buttons = screen.getAllByRole('button', { name: /Re-valider/i });
    expect(buttons.length).toBeGreaterThanOrEqual(2);
  });

  it('renders Re-valider tout button in toolbar', () => {
    renderWithApp(<IntegrationsTable {...defaultProps} onRefresh={vi.fn()} />);
    expect(screen.getByRole('button', { name: /Re-valider tout/i })).toBeInTheDocument();
  });
});
