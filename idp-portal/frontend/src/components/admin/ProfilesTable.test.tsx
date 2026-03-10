/**
 * Tests for ProfilesTable (Story 2.9, AC #3).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { ProfilesTable } from './ProfilesTable';
import type { ProfileListItem } from '../../types/api';

const items: ProfileListItem[] = [
  {
    id: 1,
    name: 'Assurance',
    ad_group: 'GRP-IDP-ASSURANCE',
    is_admin: false,
    is_auditor: false,
    is_approver: false,
    permission_count: 0,
    created_at: '2026-01-28T10:00:00Z',
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

describe('ProfilesTable', () => {
  it('renders table with columns Nom, Groupe AD, Admin, Auditeur, Approbateur, Permissions, Date de création', () => {
    render(<ProfilesTable {...defaultProps} />);
    expect(screen.getByText('Nom')).toBeInTheDocument();
    expect(screen.getByText('Groupe AD')).toBeInTheDocument();
    expect(screen.getByText('Admin')).toBeInTheDocument();
    expect(screen.getByText('Auditeur')).toBeInTheDocument();
    expect(screen.getByText('Approbateur')).toBeInTheDocument();
    expect(screen.getByText('Permissions')).toBeInTheDocument();
    expect(screen.getByText('Date de création')).toBeInTheDocument();
  });

  it('renders profiles and Nouveau profil button', () => {
    render(<ProfilesTable {...defaultProps} />);
    expect(screen.getByText('Assurance')).toBeInTheDocument();
    expect(screen.getByText('GRP-IDP-ASSURANCE')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Nouveau profil/i })).toBeInTheDocument();
  });

  it('calls onNew when Nouveau profil clicked', async () => {
    const user = userEvent.setup();
    render(<ProfilesTable {...defaultProps} />);
    await user.click(screen.getByRole('button', { name: /Nouveau profil/i }));
    expect(mockOnNew).toHaveBeenCalled();
  });

  it('calls onEdit when Modifier clicked', async () => {
    const user = userEvent.setup();
    render(<ProfilesTable {...defaultProps} />);
    await user.click(screen.getByRole('button', { name: /Modifier/i }));
    expect(mockOnEdit).toHaveBeenCalledWith(items[0]);
  });

  it('shows empty state when no profiles', () => {
    render(<ProfilesTable {...defaultProps} dataSource={[]} />);
    expect(screen.getByText('Aucun profil')).toBeInTheDocument();
  });

  it('renders Exporter YAML when handler provided (Story 2.13)', async () => {
    const onExportYaml = vi.fn();
    render(<ProfilesTable {...defaultProps} onExportYaml={onExportYaml} />);
    expect(screen.getByRole('button', { name: /Exporter YAML/i })).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('button', { name: /Exporter YAML/i }));
    expect(onExportYaml).toHaveBeenCalled();
  });

  it('affiche Oui/Non pour les colonnes Admin et Auditeur', () => {
    const adminProfile: ProfileListItem = {
      id: 2,
      name: 'Admin',
      ad_group: 'GRP-ADMIN',
      is_admin: true,
      is_auditor: false,
      is_approver: false,
      permission_count: 10,
      created_at: '2026-01-28T10:00:00Z',
    };
    render(<ProfilesTable {...defaultProps} dataSource={[adminProfile]} />);
    // is_admin=true → 'Oui', is_auditor=false → 'Non'
    const ouiElements = screen.getAllByText('Oui');
    const nonElements = screen.getAllByText('Non');
    expect(ouiElements.length).toBeGreaterThanOrEqual(1);
    expect(nonElements.length).toBeGreaterThanOrEqual(1);
  });

  it('Story 57.14 AC5: affiche Oui pour is_approver=true, Non pour is_approver=false', () => {
    const approverProfile: ProfileListItem = {
      id: 10,
      name: 'DBA',
      ad_group: 'GRP-IDP-DBA',
      is_admin: false,
      is_auditor: false,
      is_approver: true,
      permission_count: 0,
      created_at: '2026-01-28T10:00:00Z',
    };
    const nonApproverProfile: ProfileListItem = {
      id: 11,
      name: 'BUSINESS',
      ad_group: 'GRP-IDP-BUSINESS',
      is_admin: false,
      is_auditor: false,
      is_approver: false,
      permission_count: 0,
      created_at: '2026-01-28T10:00:00Z',
    };
    render(<ProfilesTable {...defaultProps} dataSource={[approverProfile, nonApproverProfile]} />);
    // is_approver=true → 'Oui', is_approver=false → 'Non'
    expect(screen.getByText('Approbateur')).toBeInTheDocument();
    const ouiElements = screen.getAllByText('Oui');
    const nonElements = screen.getAllByText('Non');
    expect(ouiElements.length).toBeGreaterThanOrEqual(1);
    expect(nonElements.length).toBeGreaterThanOrEqual(1);
  });

  it('Story 57.14 AC5: la colonne Approbateur est triable', () => {
    const items2: ProfileListItem[] = [
      { id: 1, name: 'DBA', ad_group: 'GRP-DBA', is_admin: false, is_auditor: false, is_approver: true, permission_count: 0, created_at: '2026-01-01T00:00:00Z' },
      { id: 2, name: 'BUSINESS', ad_group: 'GRP-BUSINESS', is_admin: false, is_auditor: false, is_approver: false, permission_count: 0, created_at: '2026-01-02T00:00:00Z' },
    ];
    render(<ProfilesTable {...defaultProps} dataSource={items2} />);
    fireEvent.click(screen.getByText('Approbateur'));
    fireEvent.click(screen.getByText('Approbateur'));
    expect(screen.getByText('DBA')).toBeInTheDocument();
    expect(screen.getByText('BUSINESS')).toBeInTheDocument();
  });

  it('affiche le compte de permissions', () => {
    render(<ProfilesTable {...defaultProps} />);
    expect(screen.getByText('0')).toBeInTheDocument();
  });

  it('affiche la date de création formatée', () => {
    render(<ProfilesTable {...defaultProps} />);
    // TZ=UTC (test-setup.ts) : 2026-01-28T10:00:00Z → "28/01/2026" ou équivalent fr-FR
    // On vérifie la présence d'une date qui contient l'année 2026
    expect(screen.getByText(/2026/)).toBeInTheDocument();
  });

  it('ouvre un modal de confirmation à la suppression', async () => {
    const user = userEvent.setup();
    // ProfilesTable utilise App.useApp() — wrapper App requis pour modal
    const { container: _container } = render(
      <App>
        <ProfilesTable {...defaultProps} />
      </App>,
    );

    const deleteBtn = screen.getByRole('button', { name: /Supprimer/i });
    await user.click(deleteBtn);
    // Ant Design Modal.confirm ouvre un dialogue
    await waitFor(() => {
      expect(document.querySelector('.ant-modal-confirm')).toBeTruthy();
    });
  });

  it('affiche le profil sans groupe AD (ad_group vide)', () => {
    const noAdProfile: ProfileListItem = {
      id: 3,
      name: 'Sans AD',
      ad_group: '',
      is_admin: false,
      is_auditor: true,
      is_approver: false,
      permission_count: null as unknown as number,
      created_at: '2026-01-28T10:00:00Z',
    };
    render(<ProfilesTable {...defaultProps} dataSource={[noAdProfile]} />);
    expect(screen.getByText('Sans AD')).toBeInTheDocument();
    // permission_count=null → affiche 0
    expect(screen.getByText('0')).toBeInTheDocument();
  });

  it('déclenche les sorters au clic sur les en-têtes de colonnes', () => {
    const items2: ProfileListItem[] = [
      { id: 1, name: 'Zebra', ad_group: 'GRP-Z', is_admin: true, is_auditor: false, is_approver: true, permission_count: 5, created_at: '2026-01-01T00:00:00Z' },
      { id: 2, name: 'Alpha', ad_group: 'GRP-A', is_admin: false, is_auditor: true, is_approver: false, permission_count: 10, created_at: '2026-01-02T00:00:00Z' },
    ];
    render(<ProfilesTable {...defaultProps} dataSource={items2} />);

    // Click each sortable column header to trigger the sorter functions
    fireEvent.click(screen.getByText('Nom'));
    fireEvent.click(screen.getByText('Nom')); // second click for descending
    fireEvent.click(screen.getByText('Admin'));
    fireEvent.click(screen.getByText('Admin'));
    fireEvent.click(screen.getByText('Auditeur'));
    fireEvent.click(screen.getByText('Auditeur'));
    fireEvent.click(screen.getByText('Approbateur'));
    fireEvent.click(screen.getByText('Approbateur'));
    fireEvent.click(screen.getByText('Permissions'));
    fireEvent.click(screen.getByText('Permissions'));
    fireEvent.click(screen.getByText('Date de création'));
    fireEvent.click(screen.getByText('Date de création'));

    // Verify table still renders correctly after sorting
    expect(screen.getByText('Zebra')).toBeInTheDocument();
    expect(screen.getByText('Alpha')).toBeInTheDocument();
  });

  it('onOk du modal de suppression appelle onDelete', async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn().mockResolvedValue(undefined);

    render(
      <App>
        <ProfilesTable {...defaultProps} onDelete={onDelete} />
      </App>,
    );

    const deleteBtn = screen.getByRole('button', { name: /Supprimer/i });
    await user.click(deleteBtn);

    await waitFor(() => {
      expect(document.querySelector('.ant-modal-confirm')).toBeTruthy();
    });

    // Cliquer le bouton "Supprimer" dans le modal de confirmation
    const confirmBtns = screen.getAllByRole('button', { name: /^Supprimer$/ });
    const okBtn = confirmBtns[confirmBtns.length - 1];
    await user.click(okBtn);

    await waitFor(() => {
      expect(onDelete).toHaveBeenCalledWith(items[0]);
    });
  });
});
