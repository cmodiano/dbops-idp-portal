/**
 * Tests for ExportButton component (Story 8.5, Task 10).
 *
 * Tests:
 * - 10.1 Renders with dropdown menu
 * - 10.2 Click on "Exporter en CSV" calls exportDashboardCSV
 * - 10.3 Click on "Exporter en PDF" calls exportDashboardPDF
 * - 10.4 Disabled when loading=true
 * - 10.5 Shows spinner during export
 * - 10.6 Integration: visible in ReportingDashboard
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { ExportButton } from './ExportButton';
import * as dashboardService from '../../../services/dashboard_service';

// Create mock message object
const mockMessage = {
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
  loading: vi.fn(),
};

// Spy on App.useApp to provide mocked message
vi.spyOn(App, 'useApp').mockReturnValue({
  message: mockMessage,
  notification: {} as any,
  modal: {} as any,
});

// Mock the dashboard service
vi.mock('../../../services/dashboard_service', () => ({
  exportDashboardCSV: vi.fn(),
  exportDashboardPDF: vi.fn(),
}));

describe('ExportButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders export button with dropdown menu (AC1)', async () => {
    // Task 10.1
    render(<App><ExportButton filters={{}} /></App>);

    const button = screen.getByRole('button', { name: /exporter/i });
    expect(button).toBeInTheDocument();

    // Open dropdown
    await userEvent.click(button);

    // Check menu items
    expect(screen.getByText('Exporter en CSV')).toBeInTheDocument();
    expect(screen.getByText('Exporter en PDF')).toBeInTheDocument();
  });

  it('calls exportDashboardCSV when clicking CSV option (AC6)', async () => {
    // Task 10.2
    const mockFilters = { days: 14, engine: 'aap' };
    vi.mocked(dashboardService.exportDashboardCSV).mockResolvedValueOnce();

    render(<App><ExportButton filters={mockFilters} /></App>);

    // Open dropdown and click CSV
    await userEvent.click(screen.getByRole('button', { name: /exporter/i }));
    await userEvent.click(screen.getByText('Exporter en CSV'));

    await waitFor(() => {
      expect(dashboardService.exportDashboardCSV).toHaveBeenCalledWith(mockFilters);
    });
  });

  it('calls exportDashboardPDF when clicking PDF option (AC7)', async () => {
    // Task 10.3
    const mockFilters = { days: 30, environment: 'prod' };
    vi.mocked(dashboardService.exportDashboardPDF).mockResolvedValueOnce();

    render(<App><ExportButton filters={mockFilters} /></App>);

    // Open dropdown and click PDF
    await userEvent.click(screen.getByRole('button', { name: /exporter/i }));
    await userEvent.click(screen.getByText('Exporter en PDF'));

    await waitFor(() => {
      expect(dashboardService.exportDashboardPDF).toHaveBeenCalledWith(mockFilters);
    });
  });

  it('disables button when loading prop is true', () => {
    // Task 10.4
    render(<App><ExportButton filters={{}} loading={true} /></App>);

    const button = screen.getByRole('button', { name: /exporter/i });
    expect(button).toBeDisabled();
  });

  it('disables button when disabled prop is true', () => {
    render(<App><ExportButton filters={{}} disabled={true} /></App>);

    const button = screen.getByRole('button', { name: /exporter/i });
    expect(button).toBeDisabled();
  });

  it('shows loading spinner during export (Story 8.5, Task 10.5)', async () => {
    // Task 10.5
    // Create a promise that we can control
    let resolveExport: () => void;
    const exportPromise = new Promise<void>((resolve) => {
      resolveExport = resolve;
    });
    vi.mocked(dashboardService.exportDashboardCSV).mockReturnValueOnce(exportPromise);

    render(<App><ExportButton filters={{}} /></App>);

    // Open dropdown and click CSV
    await userEvent.click(screen.getByRole('button', { name: /exporter/i }));
    await userEvent.click(screen.getByText('Exporter en CSV'));

    // Button should show loading state
    await waitFor(() => {
      const button = screen.getByRole('button');
      // Ant Design adds a loading class or spin icon
      expect(button.querySelector('.ant-btn-loading-icon') || button.classList.contains('ant-btn-loading')).toBeTruthy();
    });

    // Resolve the export
    resolveExport!();
  });

  it('shows error message on export failure', async () => {
    vi.mocked(dashboardService.exportDashboardCSV).mockRejectedValueOnce(new Error('Network error'));

    render(<App><ExportButton filters={{}} /></App>);

    // Open dropdown and click CSV
    await userEvent.click(screen.getByRole('button', { name: /exporter/i }));
    await userEvent.click(screen.getByText('Exporter en CSV'));

    // Error message should be called via mocked message
    await waitFor(() => {
      expect(mockMessage.error).toHaveBeenCalledWith("Erreur lors de l'export CSV");
    });
  });

  it('shows success message on successful export', async () => {
    vi.mocked(dashboardService.exportDashboardPDF).mockResolvedValueOnce();

    render(<App><ExportButton filters={{}} /></App>);

    // Open dropdown and click PDF
    await userEvent.click(screen.getByRole('button', { name: /exporter/i }));
    await userEvent.click(screen.getByText('Exporter en PDF'));

    // Success message should be called via mocked message
    await waitFor(() => {
      expect(mockMessage.success).toHaveBeenCalledWith('Export PDF téléchargé');
    });
  });

  it('passes all filter types to export function', async () => {
    const fullFilters = {
      days: 30,
      engine: 'aap',
      environment: 'prod',
      tags: ['oracle', 'patch'],
      status: 'COMPLETED',
      fromDate: '2026-01-01',
      toDate: '2026-01-31',
    };
    vi.mocked(dashboardService.exportDashboardCSV).mockResolvedValueOnce();

    render(<App><ExportButton filters={fullFilters} /></App>);

    await userEvent.click(screen.getByRole('button', { name: /exporter/i }));
    await userEvent.click(screen.getByText('Exporter en CSV'));

    await waitFor(() => {
      expect(dashboardService.exportDashboardCSV).toHaveBeenCalledWith(fullFilters);
    });
  });
});
