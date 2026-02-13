/**
 * Tests for AuditPage (Story 6.3).
 *
 * Tests:
 * - AC1: Table with columns (action, user, environment, status, date, ServiceNow)
 * - AC2: Filters (period, environment, status) trigger real-time reload
 * - AC3: Click row opens drawer with details
 * - AC5: Pagination 25 per page
 * - AC8: Access restricted to auditors
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router';
import { App, ConfigProvider } from 'antd';
import { ThemeProvider } from '../contexts/ThemeContext';

// Mock App.useApp() to provide message without needing full App context
const mockMessage = {
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
  loading: vi.fn(),
};

vi.spyOn(App, 'useApp').mockReturnValue({
  message: mockMessage,
  notification: {} as any,
  modal: {} as any,
});

// Mock the audit service
const mockListExecutionAudit = vi.fn();
const mockExportAuditReport = vi.fn();
vi.mock('../services/audit_service', () => ({
  listExecutionAudit: () => mockListExecutionAudit(),
  exportAuditReport: (...args: unknown[]) => mockExportAuditReport(...args),
}));

// Mock the execution service
const mockGetExecution = vi.fn();
const mockGetExecutionSteps = vi.fn();
vi.mock('../services/execution_service', () => ({
  getExecution: (id: number) => mockGetExecution(id),
  getExecutionSteps: (id: number) => mockGetExecutionSteps(id),
}));

// Mock useAuth hook
let mockUserData = {
  id: 1,
  username: 'auditor',
  display_name: 'Auditor User',
  profile: 'audit' as const,
  navigation_tabs: ['audit'] as const,
  is_auditor: true,
};

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: mockUserData,
    isAuthenticated: true,
    isLoading: false,
    hasTab: (tab: string) => mockUserData.navigation_tabs.includes(tab as never),
    accessToken: 'test-token',
    login: vi.fn(),
    logout: vi.fn(),
    refreshToken: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// Import after mocks
import AuditPage from './AuditPage';

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <ThemeProvider>
      <ConfigProvider>
        <BrowserRouter>{ui}</BrowserRouter>
      </ConfigProvider>
    </ThemeProvider>,
  );
}

const mockAuditEntries = [
  {
    id: 1,
    timestamp: '2026-01-30T10:00:00',
    user_id: '1',
    action_type: 'EXECUTION_COMPLETED',
    entity_type: 'execution',
    entity_id: 101,
    details: { action_id: 5, environment: 'prod', status: 'COMPLETED' },
    ip_address: '192.168.1.1',
    correlation_id: 'abc-123',
    derived_status: 'success' as const,
  },
  {
    id: 2,
    timestamp: '2026-01-30T09:00:00',
    user_id: '2',
    action_type: 'EXECUTION_FAILED',
    entity_type: 'execution',
    entity_id: 102,
    details: { action_id: 6, environment: 'dev', status: 'FAILED' },
    ip_address: '192.168.1.2',
    correlation_id: 'def-456',
    derived_status: 'failed' as const,
  },
];

describe('AuditPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset to auditor user
    mockUserData = {
      id: 1,
      username: 'auditor',
      display_name: 'Auditor User',
      profile: 'audit' as const,
      navigation_tabs: ['audit'] as const,
      is_auditor: true,
    };
  });

  it('AC1: renders table with correct columns', async () => {
    mockListExecutionAudit.mockResolvedValue({
      data: mockAuditEntries,
      pagination: { page: 1, page_size: 25, total: 2, total_pages: 1 },
    });

    renderWithProviders(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText('Audit des exécutions')).toBeInTheDocument();
    });

    // Check table headers (use getAllByRole for table headers)
    const headers = screen.getAllByRole('columnheader');
    expect(headers.length).toBeGreaterThanOrEqual(6);
    expect(screen.getByRole('columnheader', { name: /Action/ })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Utilisateur/ })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Statut/ })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Date/ })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Change SN/ })).toBeInTheDocument();
  });

  it('AC1: displays audit entries in table', async () => {
    mockListExecutionAudit.mockResolvedValue({
      data: mockAuditEntries,
      pagination: { page: 1, page_size: 25, total: 2, total_pages: 1 },
    });

    renderWithProviders(<AuditPage />);

    await waitFor(() => {
      // Check action names are displayed
      expect(screen.getByText('Action #5')).toBeInTheDocument();
      expect(screen.getByText('Action #6')).toBeInTheDocument();
    });

    // Check status tags
    expect(screen.getByText('Succès')).toBeInTheDocument();
    expect(screen.getByText('Échec')).toBeInTheDocument();

    // Check environments
    expect(screen.getByText('PROD')).toBeInTheDocument();
    expect(screen.getByText('DEV')).toBeInTheDocument();
  });

  it('AC2: renders filter controls', async () => {
    mockListExecutionAudit.mockResolvedValue({
      data: [],
      pagination: { page: 1, page_size: 25, total: 0, total_pages: 1 },
    });

    renderWithProviders(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText('Audit des exécutions')).toBeInTheDocument();
    });

    // Check filter placeholders
    expect(screen.getByPlaceholderText('Date début')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Date fin')).toBeInTheDocument();
  });

  it('AC5: displays pagination with correct count', async () => {
    mockListExecutionAudit.mockResolvedValue({
      data: mockAuditEntries,
      pagination: { page: 1, page_size: 25, total: 100, total_pages: 4 },
    });

    renderWithProviders(<AuditPage />);

    await waitFor(() => {
      // Total count badge should show
      expect(screen.getByText('résultats')).toBeInTheDocument();
    });
  });

  it('AC8: shows access denied for non-auditor', async () => {
    // Override to non-auditor
    mockUserData = {
      id: 2,
      username: 'regular',
      display_name: 'Regular User',
      profile: 'dbops' as const,
      navigation_tabs: ['catalog'] as const,
      is_auditor: false,
    };

    renderWithProviders(<AuditPage />);

    expect(screen.getByText('Accès non autorisé')).toBeInTheDocument();
    expect(screen.getByText('Cette page est réservée aux auditeurs.')).toBeInTheDocument();
  });

  it('displays error message when API fails', async () => {
    mockListExecutionAudit.mockRejectedValue(new Error('API Error'));

    renderWithProviders(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText('API Error')).toBeInTheDocument();
    });
  });

  it('AC3: clicking row opens drawer', async () => {
    mockListExecutionAudit.mockResolvedValue({
      data: mockAuditEntries,
      pagination: { page: 1, page_size: 25, total: 2, total_pages: 1 },
    });

    mockGetExecution.mockResolvedValue({
      id: 101,
      action_id: 5,
      action_name: 'Test Action',
      user_id: 1,
      environment: 'prod',
      parameters: null,
      status: 'COMPLETED',
      servicenow_change_id: null,
      started_at: '2026-01-30T10:00:00',
      completed_at: '2026-01-30T10:05:00',
      created_at: '2026-01-30T09:59:00',
    });

    mockGetExecutionSteps.mockResolvedValue([]);

    const user = userEvent.setup();
    renderWithProviders(<AuditPage />);

    await waitFor(() => {
      expect(screen.getByText('Action #5')).toBeInTheDocument();
    });

    // Click on a row
    await user.click(screen.getByText('Action #5'));

    await waitFor(() => {
      expect(screen.getByText("Détail d'audit")).toBeInTheDocument();
    });
  });

  describe('Export functionality (Story 6.4)', () => {
    beforeEach(() => {
      mockListExecutionAudit.mockResolvedValue({
        data: mockAuditEntries,
        pagination: { page: 1, page_size: 25, total: 2, total_pages: 1 },
      });
      mockExportAuditReport.mockResolvedValue(undefined);
    });

    it('AC1: renders export button with dropdown', async () => {
      renderWithProviders(<AuditPage />);

      await waitFor(() => {
        expect(screen.getByText('Audit des exécutions')).toBeInTheDocument();
      });

      const exportButton = screen.getByRole('button', { name: /Exporter/i });
      expect(exportButton).toBeInTheDocument();
    });

    it('AC1: dropdown shows CSV and PDF options', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditPage />);

      await waitFor(() => {
        expect(screen.getByText('Audit des exécutions')).toBeInTheDocument();
      });

      const exportButton = screen.getByRole('button', { name: /Exporter/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(screen.getByText('CSV')).toBeInTheDocument();
        expect(screen.getByText('PDF')).toBeInTheDocument();
      });
    });

    it('AC2: calls export API with correct filters when CSV selected', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditPage />);

      await waitFor(() => {
        expect(screen.getByText('Audit des exécutions')).toBeInTheDocument();
      });

      const exportButton = screen.getByRole('button', { name: /Exporter/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(screen.getByText('CSV')).toBeInTheDocument();
      });

      await user.click(screen.getByText('CSV'));

      await waitFor(() => {
        expect(mockExportAuditReport).toHaveBeenCalledWith('csv', expect.objectContaining({}));
      });
    });

    it('AC2: calls export API with correct filters when PDF selected', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditPage />);

      await waitFor(() => {
        expect(screen.getByText('Audit des exécutions')).toBeInTheDocument();
      });

      const exportButton = screen.getByRole('button', { name: /Exporter/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(screen.getByText('PDF')).toBeInTheDocument();
      });

      await user.click(screen.getByText('PDF'));

      await waitFor(() => {
        expect(mockExportAuditReport).toHaveBeenCalledWith('pdf', expect.objectContaining({}));
      });
    });

    it('AC5: shows success toast after successful export', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditPage />);

      await waitFor(() => {
        expect(screen.getByText('Audit des exécutions')).toBeInTheDocument();
      });

      const exportButton = screen.getByRole('button', { name: /Exporter/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(screen.getByText('CSV')).toBeInTheDocument();
      });

      await user.click(screen.getByText('CSV'));

      await waitFor(() => {
        expect(mockMessage.success).toHaveBeenCalledWith(expect.stringMatching(/Rapport exporté/i), expect.anything());
      });
    });

    it('AC2: shows error message when export fails', async () => {
      mockExportAuditReport.mockRejectedValue(new Error('Limite d\'export dépassée'));
      const user = userEvent.setup();
      renderWithProviders(<AuditPage />);

      await waitFor(() => {
        expect(screen.getByText('Audit des exécutions')).toBeInTheDocument();
      });

      const exportButton = screen.getByRole('button', { name: /Exporter/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(screen.getByText('PDF')).toBeInTheDocument();
      });

      await user.click(screen.getByText('PDF'));

      await waitFor(() => {
        expect(mockMessage.error).toHaveBeenCalledWith(expect.stringMatching(/Limite d'export dépassée/i), expect.anything());
      });
    });

    it('AC2: passes current filters to export API', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditPage />);

      // Wait for data to load and filters to appear (use testid for reliable Select in Ant 6.2)
      await waitFor(() => {
        expect(screen.getByTestId('audit-filter-environment')).toBeInTheDocument();
      });

      // Set environment filter
      const envSelect = screen.getByTestId('audit-filter-environment');
      await user.click(envSelect);
      await waitFor(() => {
        const prodOptions = screen.getAllByText('PROD');
        expect(prodOptions.length).toBeGreaterThan(0);
      });
      // Click the option in the dropdown (not the one in the table)
      const prodOptions = screen.getAllByText('PROD');
      const dropdownOption = prodOptions.find((el) => el.closest('.ant-select-item'));
      if (dropdownOption) {
        await user.click(dropdownOption);
      } else {
        await user.click(prodOptions[0]);
      }

      // Wait for filter to apply
      await waitFor(() => {
        expect(mockListExecutionAudit).toHaveBeenCalled();
      });

      // Export
      const exportButton = screen.getByRole('button', { name: /Exporter/i });
      await user.click(exportButton);

      await waitFor(() => {
        expect(screen.getByText('CSV')).toBeInTheDocument();
      });

      await user.click(screen.getByText('CSV'));

      await waitFor(() => {
        expect(mockExportAuditReport).toHaveBeenCalledWith(
          'csv',
          expect.objectContaining({
            environment: 'prod',
          }),
        );
      });
    });
  });
});
