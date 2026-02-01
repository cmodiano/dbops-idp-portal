/**
 * Tests for AdminAnalyticsDashboard component (Story 8.2, AC1, AC3, Task 12.5).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { App } from 'antd';
import { AdminAnalyticsDashboard } from './AdminAnalyticsDashboard';
import * as adminService from '../../../services/admin_service';
import type { AdminAnalytics } from '../../../types/api';

// Mock the admin service
vi.mock('../../../services/admin_service', () => ({
  fetchAdminAnalytics: vi.fn(),
}));

const mockAnalytics: AdminAnalytics = {
  total_published_actions: 15,
  executions_by_engine: [
    { engine: 'Oracle', count: 100 },
    { engine: 'SQL Server', count: 50 },
  ],
  executions_by_profile: [
    { profile: 'dba_app', count: 80 },
    { profile: 'dbops', count: 70 },
  ],
  adoption_trend: [
    { week_start: '2026-01-01', engine: 'Oracle', count: 10 },
    { week_start: '2026-01-08', engine: 'Oracle', count: 15 },
  ],
};

function renderWithApp(ui: React.ReactElement) {
  return render(<App>{ui}</App>);
}

describe('AdminAnalyticsDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (adminService.fetchAdminAnalytics as ReturnType<typeof vi.fn>).mockResolvedValue(mockAnalytics);
  });

  it('loads and displays analytics data', async () => {
    await act(async () => {
      renderWithApp(<AdminAnalyticsDashboard />);
    });

    await waitFor(() => {
      expect(screen.getByText('Actions publiees')).toBeInTheDocument();
    });

    expect(screen.getByText('15')).toBeInTheDocument();
    expect(adminService.fetchAdminAnalytics).toHaveBeenCalledWith(90); // Default period
  });

  it('changes period when selector is clicked', async () => {
    await act(async () => {
      renderWithApp(<AdminAnalyticsDashboard />);
    });

    await waitFor(() => {
      expect(screen.getByText('15')).toBeInTheDocument();
    });

    // Click on "30 jours" option
    await act(async () => {
      const option30 = screen.getByText('30 jours');
      fireEvent.click(option30);
    });

    await waitFor(() => {
      expect(adminService.fetchAdminAnalytics).toHaveBeenCalledWith(30);
    });
  });

  it('displays error alert when fetch fails', async () => {
    (adminService.fetchAdminAnalytics as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('Network error')
    );

    await act(async () => {
      renderWithApp(<AdminAnalyticsDashboard />);
    });

    await waitFor(() => {
      // Alert component shows error with class ant-alert-error
      expect(document.querySelector('.ant-alert-error')).toBeTruthy();
    });
  });

  it('renders all chart sections', async () => {
    await act(async () => {
      renderWithApp(<AdminAnalyticsDashboard />);
    });

    await waitFor(() => {
      expect(screen.getByText('Executions par moteur')).toBeInTheDocument();
    });

    expect(screen.getByText('Executions par profil')).toBeInTheDocument();
    expect(screen.getByText("Tendance d'adoption (par semaine)")).toBeInTheDocument();
  });
});
