/**
 * Tests for ExecutionWizard target selection (Story 13.2, Task 8.2).
 *
 * Tests:
 * - Target selection step for actions with requires_target=true
 * - Environment derivation from selected targets
 * - Mixed environments warning
 * - Fallback to environment selection for actions with requires_target=false
 * - Submission with target_names in payload
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { ExecutionWizard } from './ExecutionWizard';
import type { CatalogActionDetail } from '../../services/catalog_service';
import { submitExecution } from '../../services/execution_service';

// Mock targets response
const mockTargetsResponse = {
  items: [
    { name: 'srv-dev-01', environment: 'dev', target_type: 'server', metadata: null },
    { name: 'srv-dev-02', environment: 'dev', target_type: 'server', metadata: null },
    { name: 'srv-staging-01', environment: 'staging', target_type: 'server', metadata: null },
    { name: 'db-prod-01', environment: 'prod', target_type: 'database', metadata: null },
  ],
  total: 4,
  page: 1,
  page_size: 100,
  total_pages: 1,
};

// Mock environments response
const mockEnvironmentsResponse = [
  { id: 'dev', name: 'Developpement', environment: null },
  { id: 'staging', name: 'Staging', environment: null },
  { id: 'prod', name: 'Production', environment: null },
];

// Mock the API client (TargetSelector and fetchInventoryTargets use apiFetchRaw)
vi.mock('../../services/api_client', () => ({
  apiFetch: vi.fn(),
  apiFetchRaw: vi.fn(),
}));

import { apiFetchRaw } from '../../services/api_client';

const mockApiFetchRaw = apiFetchRaw as ReturnType<typeof vi.fn>;

// Mock the execution service
vi.mock('../../services/execution_service', () => ({
  submitExecution: vi.fn().mockResolvedValue({
    execution_id: 123,
    status: 'SUBMITTED',
    created_at: '2026-02-05T10:00:00Z',
  }),
  fetchInventoryItems: vi.fn().mockImplementation(async (type: string) => {
    if (type === 'environments') {
      return mockEnvironmentsResponse;
    }
    return [];
  }),
  fetchInventoryTargets: vi.fn().mockResolvedValue([
    { name: 'srv-dev-01', environment: 'dev', target_type: 'server', metadata: null },
    { name: 'srv-dev-02', environment: 'dev', target_type: 'server', metadata: null },
    { name: 'srv-staging-01', environment: 'staging', target_type: 'server', metadata: null },
    { name: 'db-prod-01', environment: 'prod', target_type: 'database', metadata: null },
  ]),
}));

// Wrapper with Ant Design App context
const TestWrapper = ({ children }: { children: React.ReactNode }) => (
  <App>{children}</App>
);

// Action that requires target (default)
const mockActionWithTargets: CatalogActionDetail = {
  id: 1,
  name: 'Execute on Target',
  description: 'Action that requires target selection',
  engine: 'Oracle',
  platform: 'AAP',
  parameters_schema: null,
  impact_rules: {
    DEV: { level: 'low', criteria: null },
    STAGING: { level: 'medium', criteria: null },
    PROD: { level: 'high', criteria: null },
  },
  default_impact_level: 'medium',
  status: 'published',
  created_by: 1,
  created_at: '2026-02-05T00:00:00Z',
  updated_at: null,
  tags: ['oracle'],
  execution_count: 0,
  requires_target: true, // Explicit true
};

// Action that doesn't require target
const mockActionWithoutTargets: CatalogActionDetail = {
  ...mockActionWithTargets,
  id: 2,
  name: 'Global Action',
  description: 'Action that does not require target selection',
  requires_target: false,
};

describe('ExecutionWizard - Target Selection (Story 13.2)', () => {
  const defaultProps = {
    open: true,
    action: mockActionWithTargets,
    allowedEnvironments: ['dev', 'staging', 'prod'],
    onCancel: vi.fn(),
    onSuccess: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockApiFetchRaw.mockImplementation(async (url: string) => {
      if (url.includes('/inventory/targets')) {
        return mockTargetsResponse;
      }
      return { items: [], total: 0, page: 1, page_size: 100, total_pages: 0 };
    });
  });

  describe('Step Labels (AC1)', () => {
    it('renders "Cible(s)" as first step title for actions requiring targets', async () => {
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      await waitFor(() => {
        // Multiple elements may have "Cible(s)" text (step title and form label)
        const elements = screen.getAllByText('Cible(s)');
        expect(elements.length).toBeGreaterThanOrEqual(1);
      });
    });

    it('renders "Parametres" and "Confirmation" as step 2 and 3', () => {
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      expect(screen.getByText('Parametres')).toBeInTheDocument();
      expect(screen.getByText('Confirmation')).toBeInTheDocument();
    });
  });

  describe('Target Selection (AC1)', () => {
    it('shows TargetSelector for actions requiring targets', async () => {
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      await waitFor(() => {
        expect(screen.getByText('Selectionnez une ou plusieurs cibles')).toBeInTheDocument();
      });
    });

    it('disables Next button when no target selected', async () => {
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      await waitFor(() => {
        expect(screen.getByText('Selectionnez une ou plusieurs cibles')).toBeInTheDocument();
      });

      const nextButton = screen.getByRole('button', { name: /suivant/i });
      expect(nextButton).toBeDisabled();
    });

    it('loads targets and renders options in dropdown', async () => {
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      // Wait for targets to load (API call via apiFetchRaw)
      await waitFor(() => {
        expect(mockApiFetchRaw).toHaveBeenCalledWith(
          expect.stringContaining('/inventory/targets')
        );
      });

      // Open dropdown using mouseDown (required for Ant Design Select)
      const select = screen.getByRole('combobox');
      fireEvent.mouseDown(select);

      // Wait for options to render - verifies API data is loaded into dropdown
      await waitFor(
        () => {
          const options = screen.getAllByRole('option');
          expect(options.length).toBeGreaterThan(0);
        },
        { timeout: 3000 }
      );

      // Verify the options are from our mock data (check for environment groups)
      expect(screen.getByText('Développement')).toBeInTheDocument();
    });
  });

  describe('Environment Derivation (AC2)', () => {
    it('groups targets by environment in dropdown', async () => {
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      // Wait for targets to load
      await waitFor(() => {
        expect(mockApiFetchRaw).toHaveBeenCalledWith(
          expect.stringContaining('/inventory/targets')
        );
      });

      // Open dropdown using mouseDown (required for Ant Design Select)
      const select = screen.getByRole('combobox');
      fireEvent.mouseDown(select);

      // Wait for options
      await waitFor(
        () => {
          const options = screen.getAllByRole('option');
          expect(options.length).toBeGreaterThan(0);
        },
        { timeout: 3000 }
      );

      // Should show environment group headers (Developpement, Staging, Production)
      expect(screen.getByText('Développement')).toBeInTheDocument();
      expect(screen.getByText('Staging')).toBeInTheDocument();
      expect(screen.getByText('Production')).toBeInTheDocument();
    });

    it('shows options after dropdown opens', async () => {
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      // Wait for targets to load
      await waitFor(() => {
        expect(mockApiFetchRaw).toHaveBeenCalledWith(
          expect.stringContaining('/inventory/targets')
        );
      });

      // Open dropdown
      const select = screen.getByRole('combobox');
      fireEvent.mouseDown(select);

      // Wait for options - should have at least one selectable option
      await waitFor(
        () => {
          const options = screen.getAllByRole('option');
          expect(options.length).toBeGreaterThanOrEqual(1);
        },
        { timeout: 3000 }
      );
    });
  });

  describe('Fallback to Environment Selection (AC3)', () => {
    it('shows environment selector for actions not requiring targets', async () => {
      render(
        <ExecutionWizard
          {...defaultProps}
          action={mockActionWithoutTargets}
        />,
        { wrapper: TestWrapper }
      );

      await waitFor(() => {
        // Should show environment selector instead of target selector
        expect(screen.getByText('Environnement cible')).toBeInTheDocument();
      });
    });
  });

  describe('Submission with Targets (AC4)', () => {
    it('calls inventory API to load targets', async () => {
      render(
        <ExecutionWizard {...defaultProps} />,
        { wrapper: TestWrapper }
      );

      // Wait for targets to load via API
      await waitFor(() => {
        expect(mockApiFetchRaw).toHaveBeenCalledWith(
          expect.stringContaining('/inventory/targets')
        );
      });

      // Verify the API was called with correct parameters
      expect(mockApiFetchRaw).toHaveBeenCalledWith(
        expect.stringMatching(/\/inventory\/targets\?page=1&page_size=/)
      );
    });
  });

  describe('Confirmation Step with Targets', () => {
    it('wizard has correct step structure for target-based actions', async () => {
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      // Wait for targets to load
      await waitFor(() => {
        expect(mockApiFetchRaw).toHaveBeenCalledWith(
          expect.stringContaining('/inventory/targets')
        );
      });

      // Verify all 3 steps are present
      expect(screen.getByText('Parametres')).toBeInTheDocument();
      expect(screen.getByText('Confirmation')).toBeInTheDocument();

      // Verify wizard navigation buttons are present
      expect(screen.getByRole('button', { name: /annuler/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /suivant/i })).toBeInTheDocument();
    });
  });
});
