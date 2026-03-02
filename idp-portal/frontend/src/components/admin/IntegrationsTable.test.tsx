/**
 * Tests for IntegrationsTable (Story 2.28, AC2, AC6).
 * Story 5.5: Uses App.useApp().modal.confirm (Ant Design 6.2).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
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

  // Story 51.4: Health column tests
  it('renders Santé column header', () => {
    renderWithApp(<IntegrationsTable {...defaultProps} />);
    expect(screen.getByText('Santé')).toBeInTheDocument();
  });

  it('affiche badge "Inconnu" (default) pour health_status=undefined', () => {
    renderWithApp(<IntegrationsTable {...defaultProps} />);
    // items[0] has no health_status — should default to 'unknown'
    expect(screen.getByText('Inconnu')).toBeInTheDocument();
  });

  it('affiche badge "OK" pour health_status=ok', () => {
    const okItems: IntegrationListItem[] = [
      { ...items[0], health_status: 'ok', health_checked_at: '2026-02-27T10:00:00Z', health_error_message: null },
    ];
    renderWithApp(<IntegrationsTable {...defaultProps} dataSource={okItems} />);
    expect(screen.getByText('OK')).toBeInTheDocument();
  });

  it('affiche badge "Erreur" pour health_status=error', () => {
    const errorItems: IntegrationListItem[] = [
      { ...items[0], health_status: 'error', health_checked_at: '2026-02-27T10:00:00Z', health_error_message: 'Connection refused' },
    ];
    renderWithApp(<IntegrationsTable {...defaultProps} dataSource={errorItems} />);
    expect(screen.getByText('Erreur')).toBeInTheDocument();
  });

  it('badge health a un aria-label descriptif', () => {
    const okItems: IntegrationListItem[] = [
      { ...items[0], health_status: 'ok', health_checked_at: '2026-02-27T10:00:00Z', health_error_message: null },
    ];
    renderWithApp(<IntegrationsTable {...defaultProps} dataSource={okItems} />);
    expect(screen.getByLabelText('Santé : OK')).toBeInTheDocument();
  });

  it('tooltip affiche health_error_message et date pour status=error', async () => {
    const user = userEvent.setup();
    const errorItems: IntegrationListItem[] = [
      {
        ...items[0],
        health_status: 'error',
        health_checked_at: '2026-02-27T10:00:00Z',
        health_error_message: 'Connection refused',
      },
    ];
    renderWithApp(<IntegrationsTable {...defaultProps} dataSource={errorItems} />);
    const badge = screen.getByLabelText('Santé : Erreur');
    await user.hover(badge);
    await waitFor(() => {
      expect(screen.getByText(/Erreur : Connection refused/)).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it('tooltip affiche "Jamais vérifié" quand health_checked_at est null', async () => {
    const user = userEvent.setup();
    const unknownItems: IntegrationListItem[] = [
      { ...items[0], health_status: 'unknown', health_checked_at: null, health_error_message: null },
    ];
    renderWithApp(<IntegrationsTable {...defaultProps} dataSource={unknownItems} />);
    const badge = screen.getByLabelText('Santé : Inconnu');
    await user.hover(badge);
    await waitFor(() => {
      expect(screen.getByText(/Jamais vérifié/)).toBeInTheDocument();
    }, { timeout: 3000 });
  });
});

// === Story 55.6: Extended coverage tests ===

const mockValidateOne = vi.fn();
const mockValidateAll = vi.fn();

vi.mock('../../hooks/useIntegrationValidation', () => ({
  useIntegrationValidation: () => ({
    validateOne: mockValidateOne,
    validateAll: mockValidateAll,
    validatingId: null,
    validatingAll: false,
  }),
}));

describe('IntegrationsTable - Extended coverage 55.6', () => {
  beforeEach(() => {
    mockModalConfirm.mockReset();
    mockValidateOne.mockReset();
    mockValidateAll.mockReset();
  });

  it('handleValidate — succès avec statut valid → message.success', async () => {
    const mockMessageSuccess = vi.fn();
    const mockMessageError = vi.fn();
    const mockMessageWarning = vi.fn();
    const mockOnRefresh = vi.fn();

    vi.spyOn(App, 'useApp').mockReturnValue({
      message: {
        success: mockMessageSuccess,
        error: mockMessageError,
        info: vi.fn(),
        warning: mockMessageWarning,
        loading: vi.fn(),
        open: vi.fn(),
        destroy: vi.fn(),
      },
      notification: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn(), open: vi.fn() },
      modal: { confirm: mockModalConfirm },
    } as unknown as ReturnType<typeof App.useApp>);

    mockValidateOne.mockResolvedValue({ current_status: 'valid' });

    const user = userEvent.setup();
    render(
      <App>
        <IntegrationsTable {...defaultProps} onRefresh={mockOnRefresh} />
      </App>
    );

    const revalidateBtn = screen.getAllByRole('button', { name: /Re-valider/i }).find(
      (btn) => btn.textContent?.includes('Re-valider') && !btn.textContent?.includes('tout')
    );
    await user.click(revalidateBtn!);

    await waitFor(() => {
      expect(mockValidateOne).toHaveBeenCalledWith(1);
      expect(mockMessageSuccess).toHaveBeenCalledWith(expect.stringContaining('Valide'));
      expect(mockOnRefresh).toHaveBeenCalled();
    });
  });

  it('handleValidate — statut deprecated → message.warning', async () => {
    const mockMessageWarning = vi.fn();
    const mockOnRefresh = vi.fn();

    vi.spyOn(App, 'useApp').mockReturnValue({
      message: {
        success: vi.fn(),
        error: vi.fn(),
        info: vi.fn(),
        warning: mockMessageWarning,
        loading: vi.fn(),
        open: vi.fn(),
        destroy: vi.fn(),
      },
      notification: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn(), open: vi.fn() },
      modal: { confirm: mockModalConfirm },
    } as unknown as ReturnType<typeof App.useApp>);

    mockValidateOne.mockResolvedValue({ current_status: 'deprecated' });

    const user = userEvent.setup();
    render(
      <App>
        <IntegrationsTable {...defaultProps} onRefresh={mockOnRefresh} />
      </App>
    );

    const revalidateBtn = screen.getAllByRole('button', { name: /Re-valider/i }).find(
      (btn) => btn.textContent?.includes('Re-valider') && !btn.textContent?.includes('tout')
    );
    await user.click(revalidateBtn!);

    await waitFor(() => {
      expect(mockMessageWarning).toHaveBeenCalledWith(expect.stringContaining('déprécié'));
    });
  });

  it('handleValidate — statut invalid → message.error', async () => {
    const mockMessageError = vi.fn();

    vi.spyOn(App, 'useApp').mockReturnValue({
      message: {
        success: vi.fn(),
        error: mockMessageError,
        info: vi.fn(),
        warning: vi.fn(),
        loading: vi.fn(),
        open: vi.fn(),
        destroy: vi.fn(),
      },
      notification: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn(), open: vi.fn() },
      modal: { confirm: mockModalConfirm },
    } as unknown as ReturnType<typeof App.useApp>);

    mockValidateOne.mockResolvedValue({ current_status: 'invalid' });

    const user = userEvent.setup();
    render(
      <App>
        <IntegrationsTable {...defaultProps} />
      </App>
    );

    const revalidateBtn = screen.getAllByRole('button', { name: /Re-valider/i }).find(
      (btn) => btn.textContent?.includes('Re-valider') && !btn.textContent?.includes('tout')
    );
    await user.click(revalidateBtn!);

    await waitFor(() => {
      expect(mockMessageError).toHaveBeenCalledWith(expect.stringContaining('invalide'));
    });
  });

  it('handleValidate — erreur API → message.error générique', async () => {
    const mockMessageError = vi.fn();

    vi.spyOn(App, 'useApp').mockReturnValue({
      message: {
        success: vi.fn(),
        error: mockMessageError,
        info: vi.fn(),
        warning: vi.fn(),
        loading: vi.fn(),
        open: vi.fn(),
        destroy: vi.fn(),
      },
      notification: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn(), open: vi.fn() },
      modal: { confirm: mockModalConfirm },
    } as unknown as ReturnType<typeof App.useApp>);

    mockValidateOne.mockRejectedValue(new Error('Network error'));

    const user = userEvent.setup();
    render(
      <App>
        <IntegrationsTable {...defaultProps} />
      </App>
    );

    const revalidateBtn = screen.getAllByRole('button', { name: /Re-valider/i }).find(
      (btn) => btn.textContent?.includes('Re-valider') && !btn.textContent?.includes('tout')
    );
    await user.click(revalidateBtn!);

    await waitFor(() => {
      expect(mockMessageError).toHaveBeenCalledWith('Erreur lors de la validation');
    });
  });

  it('handleValidateAll — succès → modal.info avec statistiques', async () => {
    const mockModalInfo = vi.fn();
    const mockOnRefresh = vi.fn();

    vi.spyOn(App, 'useApp').mockReturnValue({
      message: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn(), loading: vi.fn(), open: vi.fn(), destroy: vi.fn() },
      notification: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn(), open: vi.fn() },
      modal: { confirm: mockModalConfirm, info: mockModalInfo },
    } as unknown as ReturnType<typeof App.useApp>);

    mockValidateAll.mockResolvedValue({ valid: 5, invalid: 1, deprecated: 2, updated: 8 });

    const user = userEvent.setup();
    render(
      <App>
        <IntegrationsTable {...defaultProps} onRefresh={mockOnRefresh} />
      </App>
    );

    await user.click(screen.getByRole('button', { name: /Re-valider tout/i }));

    await waitFor(() => {
      expect(mockValidateAll).toHaveBeenCalled();
      expect(mockModalInfo).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Rapport de validation' })
      );
      expect(mockOnRefresh).toHaveBeenCalled();
    });
  });

  it('handleValidateAll — erreur API → notification.error', async () => {
    const mockNotifError = vi.fn();

    vi.spyOn(App, 'useApp').mockReturnValue({
      message: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn(), loading: vi.fn(), open: vi.fn(), destroy: vi.fn() },
      notification: { success: vi.fn(), error: mockNotifError, info: vi.fn(), warning: vi.fn(), open: vi.fn() },
      modal: { confirm: mockModalConfirm, info: vi.fn() },
    } as unknown as ReturnType<typeof App.useApp>);

    mockValidateAll.mockRejectedValue(new Error('Batch error'));

    const user = userEvent.setup();
    render(
      <App>
        <IntegrationsTable {...defaultProps} />
      </App>
    );

    await user.click(screen.getByRole('button', { name: /Re-valider tout/i }));

    await waitFor(() => {
      expect(mockNotifError).toHaveBeenCalledWith(
        expect.objectContaining({ description: 'Erreur lors de la validation batch' })
      );
    });
  });

  it('truncateUrl — URL plus longue que 40 caractères est tronquée avec ellipse', () => {
    const longUrlItem: IntegrationListItem[] = [
      {
        ...items[0],
        base_url: 'https://very-long-url-that-exceeds-forty-characters.example.com/api/v1',
      },
    ];
    renderWithApp(<IntegrationsTable {...defaultProps} dataSource={longUrlItem} />);
    // The URL should be truncated — we check the cell contains the ellipsis character
    expect(document.body.textContent).toContain('…');
  });

  it('auth_flow — affiche le label de flow quand renseigné', () => {
    const itemsWithFlow: IntegrationListItem[] = [
      { ...items[0], auth_flow: 'token' as const },
    ];
    renderWithApp(<IntegrationsTable {...defaultProps} dataSource={itemsWithFlow} />);
    // AUTH_FLOW_LABELS['token'] should be displayed as a Tag
    expect(screen.getByText('Token (Bearer)')).toBeInTheDocument();
  });

  it('auth_flow — affiche "—" quand auth_flow est null', () => {
    renderWithApp(<IntegrationsTable {...defaultProps} />);
    // items[0] has auth_flow: null → should render em dash
    expect(document.body.textContent).toContain('—');
  });
});
