/**
 * Tests for ConfigSyncPanel component (Story 64.14, AC #3, #9).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import * as configSyncService from '../../../services/config_sync_service';
import { ConfigSyncPanel } from '../ConfigSyncPanel';
import type { ConfigSyncStatusResponse } from '../../../types/api/config_sync';

const mockNavigate = vi.fn();

vi.mock('react-router', () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock('../../../services/config_sync_service', () => ({
  getConfigSyncStatus: vi.fn(),
}));

const mockMessage = { error: vi.fn(), success: vi.fn() };

vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd');
  return {
    ...actual,
    App: {
      ...actual.App,
      useApp: () => ({ message: mockMessage, notification: {}, modal: {} }),
    },
  };
});

const mockData: ConfigSyncStatusResponse = {
  data: {
    global: {
      total: 10,
      synced: 8,
      diverged: 1,
      never_synced: 1,
      last_sync_date: '2026-03-01T10:00:00Z',
    },
    entity_types: [
      {
        entity_type: 'actions',
        total: 5,
        synced: 4,
        diverged: 1,
        never_synced: 0,
        last_sync_date: '2026-03-01T10:00:00Z',
      },
      {
        entity_type: 'integrations',
        total: 3,
        synced: 3,
        diverged: 0,
        never_synced: 0,
        last_sync_date: '2026-03-01T09:00:00Z',
      },
      {
        entity_type: 'profiles',
        total: 2,
        synced: 1,
        diverged: 0,
        never_synced: 1,
        last_sync_date: null,
      },
      { entity_type: 'policies', total: 0, synced: 0, diverged: 0, never_synced: 0, last_sync_date: null },
      { entity_type: 'engines', total: 0, synced: 0, diverged: 0, never_synced: 0, last_sync_date: null },
      { entity_type: 'categories', total: 0, synced: 0, diverged: 0, never_synced: 0, last_sync_date: null },
      { entity_type: 'integration-types', total: 0, synced: 0, diverged: 0, never_synced: 0, last_sync_date: null },
      { entity_type: 'feature-flags', total: 0, synced: 0, diverged: 0, never_synced: 0, last_sync_date: null },
    ],
  },
};

describe('ConfigSyncPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('affiche le tableau avec les données après chargement', async () => {
    vi.mocked(configSyncService.getConfigSyncStatus).mockResolvedValue(mockData);
    render(<ConfigSyncPanel />);
    await waitFor(() => expect(screen.getByText('Actions')).toBeInTheDocument());
    expect(screen.getByText('Intégrations')).toBeInTheDocument();
    expect(screen.getByText('Profils')).toBeInTheDocument();
  });

  it('affiche un indicateur de chargement (Spin) pendant le fetch', () => {
    vi.mocked(configSyncService.getConfigSyncStatus).mockReturnValue(new Promise(() => {}));
    render(<ConfigSyncPanel />);
    // Ant Design Spin renders an .ant-spin-spinning element when loading
    const spinContainer = document.querySelector('.ant-spin-spinning');
    expect(spinContainer).toBeInTheDocument();
  });

  it('affiche les statistiques globales après chargement', async () => {
    vi.mocked(configSyncService.getConfigSyncStatus).mockResolvedValue(mockData);
    render(<ConfigSyncPanel />);
    await waitFor(() => expect(screen.getByText('Total entités')).toBeInTheDocument());
    expect(screen.getByText('Synchronisées')).toBeInTheDocument();
    expect(screen.getByText('Divergées')).toBeInTheDocument();
  });

  it('affiche le bouton Voir l\'audit des syncs', async () => {
    vi.mocked(configSyncService.getConfigSyncStatus).mockResolvedValue(mockData);
    render(<ConfigSyncPanel />);
    await waitFor(() =>
      expect(screen.getByText("Voir l'audit des syncs")).toBeInTheDocument()
    );
  });

  it('appelle message.error si le service échoue', async () => {
    vi.mocked(configSyncService.getConfigSyncStatus).mockRejectedValue(new Error('Network error'));
    render(<ConfigSyncPanel />);
    await waitFor(() => expect(mockMessage.error).toHaveBeenCalledWith(
      'Erreur lors du chargement du statut de sync'
    ));
  });
});
