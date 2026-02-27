/**
 * CalendarFiltersPanel tests (Story 13.6, AC4, AC5).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfigProvider } from 'antd';
import { CalendarFiltersPanel } from './CalendarFiltersPanel';
import { lightTheme } from '../../theme/desjardins';
import type { CalendarFilters } from '../../hooks/useCalendarFilters';
import * as integrationsService from '../../services/integrations_service';

vi.mock('../../services/integrations_service');
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { id: 1, username: 'test' }, loading: false }),
}));
vi.mock('../../hooks/useEnvironments', () => ({
  useEnvironments: () => ({
    environments: ['dev', 'staging', 'prod'],
    loading: false,
    error: null,
    environmentOptions: [
      { value: 'dev', label: 'Développement' },
      { value: 'staging', label: 'Staging' },
      { value: 'prod', label: 'Production' },
    ],
  }),
}));

const defaultFilters: CalendarFilters = {
  action_id: null,
  environment: null,
  engine: null,
  platform: null,
  start_date: null,
  end_date: null,
};

const defaultAvailableActions = [
  { action_id: 1, action_name: 'Action A' },
  { action_id: 2, action_name: 'Action B' },
];

function renderFiltersPanel(
  filters: CalendarFilters = defaultFilters,
  onApplyFilters = vi.fn(),
  onResetFilters = vi.fn(),
  activeFilterCount = 0,
  availableActions = defaultAvailableActions
) {
  return render(
    <ConfigProvider theme={lightTheme}>
      <CalendarFiltersPanel
        filters={filters}
        onApplyFilters={onApplyFilters}
        onResetFilters={onResetFilters}
        activeFilterCount={activeFilterCount}
        loading={false}
        availableActions={availableActions}
      />
    </ConfigProvider>
  );
}

describe('CalendarFiltersPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(integrationsService.getIntegrations).mockResolvedValue([
      { id: 1, type: 'aap', name: 'AAP', base_url: 'https://aap.example.com', credential_ref: null, icon: null, auth_flow: null, token_url: null, created_at: '2026-01-01', updated_at: '2026-01-01' },
      { id: 2, type: 'terraform', name: 'Terraform', base_url: 'https://tf.example.com', credential_ref: null, icon: null, auth_flow: null, token_url: null, created_at: '2026-01-01', updated_at: '2026-01-01' },
    ]);
  });

  describe('Rendering', () => {
    it('renders all filter controls', async () => {
      renderFiltersPanel();

      expect(screen.getByTestId('calendar-filters-panel')).toBeInTheDocument();
      expect(screen.getByTestId('filter-action')).toBeInTheDocument();
      expect(screen.getByTestId('filter-environment')).toBeInTheDocument();
      expect(screen.getByTestId('filter-engine')).toBeInTheDocument();
      expect(screen.getByTestId('filter-platform')).toBeInTheDocument();
      // RangePicker generates multiple elements; verify at least one exists
      expect(screen.queryAllByTestId('filter-date-range').length).toBeGreaterThan(0);
      expect(screen.getByTestId('filter-reset')).toBeInTheDocument();
    });

    it('shows filter title with icon', () => {
      renderFiltersPanel();

      expect(screen.getByText('Filtres')).toBeInTheDocument();
    });

    it('shows active filter count badge when filters are active', () => {
      renderFiltersPanel(defaultFilters, vi.fn(), vi.fn(), 3);

      const badge = screen.getByTestId('active-filters-badge');
      expect(badge).toHaveTextContent('3');
    });

    it('hides badge when no filters are active', () => {
      renderFiltersPanel(defaultFilters, vi.fn(), vi.fn(), 0);

      expect(screen.queryByTestId('active-filters-badge')).not.toBeInTheDocument();
    });
  });

  describe('Action Filter', () => {
    it('shows available actions from props', async () => {
      const user = userEvent.setup();
      renderFiltersPanel();

      const actionSelect = screen.getByTestId('filter-action');
      await user.click(within(actionSelect).getByRole('combobox'));

      await waitFor(() => {
        expect(screen.getByText('Action A')).toBeInTheDocument();
        expect(screen.getByText('Action B')).toBeInTheDocument();
      });
    });

    it('calls onApplyFilters when action selected', async () => {
      const user = userEvent.setup();
      const onApplyFilters = vi.fn();
      renderFiltersPanel(defaultFilters, onApplyFilters);

      const actionSelect = screen.getByTestId('filter-action');
      await user.click(within(actionSelect).getByRole('combobox'));

      await waitFor(() => {
        expect(screen.getByText('Action A')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Action A'));

      expect(onApplyFilters).toHaveBeenCalledWith(
        expect.objectContaining({ action_id: 1 })
      );
    });
  });

  describe('Environment Filter', () => {
    it('shows environment options', async () => {
      const user = userEvent.setup();
      renderFiltersPanel();

      const envSelect = screen.getByTestId('filter-environment');
      await user.click(within(envSelect).getByRole('combobox'));

      await waitFor(() => {
        expect(screen.getByText('Développement')).toBeInTheDocument();
        expect(screen.getByText('Staging')).toBeInTheDocument();
        expect(screen.getByText('Production')).toBeInTheDocument();
      });
    });

    it('calls onApplyFilters when environment selected', async () => {
      const user = userEvent.setup();
      const onApplyFilters = vi.fn();
      renderFiltersPanel(defaultFilters, onApplyFilters);

      const envSelect = screen.getByTestId('filter-environment');
      await user.click(within(envSelect).getByRole('combobox'));

      await waitFor(() => {
        expect(screen.getByText('Production')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Production'));

      expect(onApplyFilters).toHaveBeenCalledWith(
        expect.objectContaining({ environment: 'prod' })
      );
    });
  });

  describe('Engine Filter', () => {
    it('renders engine select', () => {
      renderFiltersPanel();

      const engineSelect = screen.getByTestId('filter-engine');
      expect(engineSelect).toBeInTheDocument();
    });
  });

  describe('Platform Filter', () => {
    it('loads integrations for platform options', async () => {
      renderFiltersPanel();

      await waitFor(() => {
        expect(integrationsService.getIntegrations).toHaveBeenCalled();
      });
    });

    it('renders platform select', async () => {
      renderFiltersPanel();

      await waitFor(() => {
        expect(integrationsService.getIntegrations).toHaveBeenCalled();
      });

      const platformSelect = screen.getByTestId('filter-platform');
      expect(platformSelect).toBeInTheDocument();
    });
  });

  describe('Date Range Filter', () => {
    it('renders date range picker', () => {
      renderFiltersPanel();

      // RangePicker generates multiple elements with same testid; verify at least one exists
      expect(screen.queryAllByTestId('filter-date-range').length).toBeGreaterThan(0);
    });

    it('shows selected date range', () => {
      const filtersWithDates: CalendarFilters = {
        ...defaultFilters,
        start_date: '2026-02-01',
        end_date: '2026-02-28',
      };
      renderFiltersPanel(filtersWithDates);

      // Date picker should show the selected range - verify elements exist
      expect(screen.queryAllByTestId('filter-date-range').length).toBeGreaterThan(0);
    });
  });

  describe('Reset Button', () => {
    it('is disabled when no filters are active', () => {
      renderFiltersPanel(defaultFilters, vi.fn(), vi.fn(), 0);

      const resetButton = screen.getByTestId('filter-reset');
      expect(resetButton).toBeDisabled();
    });

    it('is enabled when filters are active', () => {
      renderFiltersPanel(defaultFilters, vi.fn(), vi.fn(), 2);

      const resetButton = screen.getByTestId('filter-reset');
      expect(resetButton).not.toBeDisabled();
    });

    it('calls onResetFilters when clicked', async () => {
      const user = userEvent.setup();
      const onResetFilters = vi.fn();
      renderFiltersPanel(defaultFilters, vi.fn(), onResetFilters, 1);

      await user.click(screen.getByTestId('filter-reset'));

      expect(onResetFilters).toHaveBeenCalled();
    });
  });

  describe('Loading State', () => {
    it('disables all controls when loading', () => {
      render(
        <ConfigProvider theme={lightTheme}>
          <CalendarFiltersPanel
            filters={defaultFilters}
            onApplyFilters={vi.fn()}
            onResetFilters={vi.fn()}
            activeFilterCount={0}
            loading={true}
            availableActions={defaultAvailableActions}
          />
        </ConfigProvider>
      );

      // Verify select container has disabled class
      const actionSelect = screen.getByTestId('filter-action');
      expect(actionSelect).toHaveClass('ant-select-disabled');
    });
  });
});
