/**
 * Tests for EnginesAdminTable (Story 31.10, AC1/AC2/AC3/AC5).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { EnginesAdminTable } from './EnginesAdminTable';

// Mock services
vi.mock('../../services/engines_service', () => ({
  fetchEnginesForAdmin: vi.fn(),
  updateEngine: vi.fn(),
}));

vi.mock('../../utils/engineIconCache', () => ({
  invalidateEngineIconCache: vi.fn(),
}));

vi.mock('../../hooks/useEngines', () => ({
  invalidateEnginesCache: vi.fn(),
}));

import { fetchEnginesForAdmin, updateEngine } from '../../services/engines_service';
import { invalidateEngineIconCache } from '../../utils/engineIconCache';
import { invalidateEnginesCache } from '../../hooks/useEngines';
import type { RefEngine } from '../../services/reference_service';

const mockFetchEnginesForAdmin = vi.mocked(fetchEnginesForAdmin);
const mockUpdateEngine = vi.mocked(updateEngine);
const mockInvalidateEngineIconCache = vi.mocked(invalidateEngineIconCache);
const mockInvalidateEnginesCache = vi.mocked(invalidateEnginesCache);

const mockNotification = {
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
  open: vi.fn(),
};
const mockModalConfirm = vi.fn();

function renderWithApp(ui: React.ReactElement) {
  vi.spyOn(App, 'useApp').mockReturnValue({
    message: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn(), loading: vi.fn() },
    notification: mockNotification,
    modal: { confirm: mockModalConfirm },
  } as ReturnType<typeof App.useApp>);
  return render(<App>{ui}</App>);
}

const engines: RefEngine[] = [
  { id: 1, code: 'ORACLE', label: 'Oracle', display_order: 1, is_active: 1, icon_url: '/icons/oracle.svg' },
  { id: 2, code: 'SQLSERVER', label: 'SQL Server', display_order: 2, is_active: 1, icon_url: null },
  { id: 3, code: 'DB2', label: 'DB2', display_order: 3, is_active: 0, icon_url: null },
];

describe('EnginesAdminTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchEnginesForAdmin.mockResolvedValue(engines);
  });

  it('renders engine list with all columns, active+inactive, and icon preview (AC1)', async () => {
    renderWithApp(<EnginesAdminTable />);
    await waitFor(() => {
      expect(screen.getByText('Oracle')).toBeInTheDocument();
    });
    // All engines including inactive
    expect(screen.getByText('SQL Server')).toBeInTheDocument();
    expect(screen.getAllByText('DB2').length).toBeGreaterThanOrEqual(1);
    // Column headers
    expect(screen.getByText('Code')).toBeInTheDocument();
    expect(screen.getByText('Libellé')).toBeInTheDocument();
    expect(screen.getByText('Icône')).toBeInTheDocument();
    expect(screen.getByText('Ordre')).toBeInTheDocument();
    expect(screen.getByText('Actif')).toBeInTheDocument();
    // API called with activeOnly=false
    expect(mockFetchEnginesForAdmin).toHaveBeenCalledWith(false);
    // Icon preview
    const avatarImg = screen.getByAltText('Icône moteur');
    expect(avatarImg).toHaveAttribute('src', '/icons/oracle.svg');
  });

  it('shows count in header', async () => {
    renderWithApp(<EnginesAdminTable />);
    await waitFor(() => {
      expect(screen.getByText('Moteurs (3)')).toBeInTheDocument();
    });
  });

  it('opens edit modal when Modifier clicked (AC2)', async () => {
    const user = userEvent.setup();
    renderWithApp(<EnginesAdminTable />);
    await waitFor(() => {
      expect(screen.getByText('Oracle')).toBeInTheDocument();
    });
    const editButtons = screen.getAllByRole('button', { name: /Modifier/i });
    await user.click(editButtons[0]);
    await waitFor(() => {
      expect(screen.getByText('Modifier le moteur')).toBeInTheDocument();
    });
  });

  it('shows Désactiver button only for active engines', async () => {
    renderWithApp(<EnginesAdminTable />);
    await waitFor(() => {
      expect(screen.getByText('Oracle')).toBeInTheDocument();
    });
    const deactivateButtons = screen.getAllByRole('button', { name: /Désactiver/i });
    // Only 2 active engines (ORACLE, SQLSERVER) should have Désactiver
    expect(deactivateButtons).toHaveLength(2);
  });

  it('calls confirm modal and deactivates engine with is_active: 0 (AC2)', async () => {
    const user = userEvent.setup();
    mockUpdateEngine.mockResolvedValue({ ...engines[0], is_active: 0 });
    mockModalConfirm.mockImplementation(({ onOk }: { onOk: () => Promise<void> }) => {
      onOk();
    });

    renderWithApp(<EnginesAdminTable />);
    await waitFor(() => {
      expect(screen.getByText('Oracle')).toBeInTheDocument();
    });
    const deactivateButtons = screen.getAllByRole('button', { name: /Désactiver/i });
    await user.click(deactivateButtons[0]);

    expect(mockModalConfirm).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Désactiver le moteur' })
    );
    await waitFor(() => {
      expect(mockUpdateEngine).toHaveBeenCalledWith(1, { is_active: 0 });
    });
  });

  it('invalidates caches after successful deactivation (AC3)', async () => {
    mockUpdateEngine.mockResolvedValue({ ...engines[0], is_active: 0 });
    mockModalConfirm.mockImplementation(({ onOk }: { onOk: () => Promise<void> }) => {
      onOk();
    });

    renderWithApp(<EnginesAdminTable />);
    await waitFor(() => {
      expect(screen.getByText('Oracle')).toBeInTheDocument();
    });

    const deactivateButtons = screen.getAllByRole('button', { name: /Désactiver/i });
    await userEvent.setup().click(deactivateButtons[0]);

    await waitFor(() => {
      expect(mockInvalidateEngineIconCache).toHaveBeenCalled();
      expect(mockInvalidateEnginesCache).toHaveBeenCalled();
    });
  });

  it('refreshes list when Actualiser clicked', async () => {
    const user = userEvent.setup();
    renderWithApp(<EnginesAdminTable />);
    await waitFor(() => {
      expect(screen.getByText('Oracle')).toBeInTheDocument();
    });

    mockFetchEnginesForAdmin.mockClear();
    await user.click(screen.getByRole('button', { name: /Actualiser/i }));
    expect(mockFetchEnginesForAdmin).toHaveBeenCalledWith(false);
  });

  it('invalidates caches and refetches after form edit success (AC3)', async () => {
    const user = userEvent.setup();
    mockUpdateEngine.mockResolvedValue({ ...engines[0], icon_url: '/icons/new.svg' });

    renderWithApp(<EnginesAdminTable />);
    await waitFor(() => {
      expect(screen.getByText('Oracle')).toBeInTheDocument();
    });

    // Open edit modal
    const editButtons = screen.getAllByRole('button', { name: /Modifier/i });
    await user.click(editButtons[0]);
    await waitFor(() => {
      expect(screen.getByText('Modifier le moteur')).toBeInTheDocument();
    });

    // Submit the form (click Enregistrer)
    mockFetchEnginesForAdmin.mockClear();
    mockInvalidateEngineIconCache.mockClear();
    mockInvalidateEnginesCache.mockClear();

    const saveBtn = screen.getByRole('button', { name: /Enregistrer/i });
    await user.click(saveBtn);

    await waitFor(() => {
      expect(mockUpdateEngine).toHaveBeenCalled();
      expect(mockInvalidateEngineIconCache).toHaveBeenCalled();
      expect(mockInvalidateEnginesCache).toHaveBeenCalled();
      expect(mockFetchEnginesForAdmin).toHaveBeenCalledWith(false);
    });
  });

  it('shows error notification on fetch failure', async () => {
    mockFetchEnginesForAdmin.mockRejectedValueOnce(new Error('Network error'));
    renderWithApp(<EnginesAdminTable />);
    await waitFor(() => {
      expect(mockNotification.error).toHaveBeenCalledWith(
        expect.objectContaining({ description: 'Network error' })
      );
    });
  });
});
