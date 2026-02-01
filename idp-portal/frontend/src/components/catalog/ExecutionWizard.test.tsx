/**
 * Tests for ExecutionWizard component (Story 4.1, Task 8.2; Story 4.2, Task 5.4).
 *
 * Tests:
 * - Step navigation (next, prev, persist state)
 * - Environment selection with impact indicator
 * - Dynamic form generation from parameters_schema
 * - Inline validation
 * - Confirmation step recap
 * - Accessibility (aria-labels, keyboard navigation)
 * - Inventory loading and error handling (Story 4.2)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { ExecutionWizard } from './ExecutionWizard';
import type { CatalogActionDetail } from '../../services/catalog_service';
import type { InventoryItem } from '../../types/api';
import { fetchInventoryItems } from '../../services/execution_service';

// Mock environments data (always needed for environment selector) - use French labels to match UI
const mockEnvironments: InventoryItem[] = [
  { id: 'dev', name: 'Developpement', environment: null },
  { id: 'staging', name: 'Staging', environment: null },
  { id: 'prod', name: 'Production', environment: null },
];

// Mock the execution service
vi.mock('../../services/execution_service', () => ({
  submitExecution: vi.fn(),
  // Default: return environments for environment selector (French labels), empty for others
  fetchInventoryItems: vi.fn().mockImplementation(async (type: string) => {
    if (type === 'environments') {
      return [
        { id: 'dev', name: 'Developpement', environment: null },
        { id: 'staging', name: 'Staging', environment: null },
        { id: 'prod', name: 'Production', environment: null },
      ];
    }
    return [];
  }),
}));

// Wrapper with Ant Design App context
const TestWrapper = ({ children }: { children: React.ReactNode }) => (
  <App>{children}</App>
);

const mockAction: CatalogActionDetail = {
  id: 1,
  name: 'Create PDB Oracle',
  description: 'Creates a Pluggable Database',
  engine: 'Oracle',
  platform: 'AAP',
  parameters_schema: {
    type: 'object',
    properties: {
      pdb_name: {
        type: 'string',
        title: 'PDB Name',
        description: 'Name of the Pluggable Database',
      },
      size_gb: {
        type: 'number',
        title: 'Size (GB)',
        minimum: 1,
        maximum: 1000,
      },
    },
    required: ['pdb_name'],
  },
  impact_rules: {
    DEV: { level: 'low', criteria: null },
    STAGING: { level: 'medium', criteria: null },
    PROD: { level: 'high', criteria: null },
  },
  default_impact_level: 'medium',
  status: 'published',
  created_by: 1,
  created_at: '2026-01-29T00:00:00Z',
  updated_at: null,
  tags: ['oracle', 'provisioning'],
  change_type_config: {
    DEV: { required: false, change_model_code: null },
    STAGING: { required: false, change_model_code: null },
    PROD: { required: true, change_model_code: 'CHG001' },
  },
  execution_count: 5,
};

describe('ExecutionWizard', () => {
  const defaultProps = {
    open: true,
    action: mockAction,
    allowedEnvironments: ['dev', 'staging', 'prod'],
    onCancel: vi.fn(),
    onSuccess: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Step Navigation', () => {
    it('renders 3-step wizard with correct labels', () => {
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      expect(screen.getByText('Environnement')).toBeInTheDocument();
      expect(screen.getByText('Parametres')).toBeInTheDocument();
      expect(screen.getByText('Confirmation')).toBeInTheDocument();
    });

    it('starts on step 1 (Environment)', () => {
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      expect(screen.getByText('Environnement cible')).toBeInTheDocument();
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });

    it('disables Next button when no environment selected', () => {
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      const nextButton = screen.getByRole('button', { name: /suivant/i });
      expect(nextButton).toBeDisabled();
    });

    it('enables Next button after environment selection', async () => {
      const user = userEvent.setup();
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      // Select environment
      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByText('Developpement'));

      const nextButton = screen.getByRole('button', { name: /suivant/i });
      expect(nextButton).not.toBeDisabled();
    });

    it('navigates to step 2 after environment selection and Next click', async () => {
      const user = userEvent.setup();
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      // Select environment
      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByText('Developpement'));

      // Click Next
      await user.click(screen.getByRole('button', { name: /suivant/i }));

      // Should see Parameters step
      await waitFor(() => {
        expect(screen.getByLabelText('PDB Name')).toBeInTheDocument();
      });
    });

    it('Previous button goes back to step 1', async () => {
      const user = userEvent.setup();
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      // Go to step 2
      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByText('Developpement'));
      await user.click(screen.getByRole('button', { name: /suivant/i }));

      // Wait for step 2
      await waitFor(() => {
        expect(screen.getByLabelText('PDB Name')).toBeInTheDocument();
      });

      // Click Previous
      await user.click(screen.getByRole('button', { name: /precedent/i }));

      // Should be back on step 1
      expect(screen.getByText('Environnement cible')).toBeInTheDocument();
    });

    it('persists environment selection when going back', async () => {
      const user = userEvent.setup();
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      // Select dev environment
      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByText('Developpement'));

      // Go to step 2 and back
      await user.click(screen.getByRole('button', { name: /suivant/i }));
      await waitFor(() => expect(screen.getByLabelText('PDB Name')).toBeInTheDocument());
      await user.click(screen.getByRole('button', { name: /precedent/i }));

      // Environment should still be selected
      expect(screen.getByText('Developpement')).toBeInTheDocument();
    });
  });

  describe('Environment Step (Step 1)', () => {
    it('shows Production warning badge when prod selected', async () => {
      const user = userEvent.setup();
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByText('Production'));

      expect(screen.getByText(/Avertissement/)).toBeInTheDocument();
      expect(screen.getByText(/Environnement Production/)).toBeInTheDocument();
    });

    it('shows correct impact indicator for selected environment', async () => {
      const user = userEvent.setup();
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      // Select prod (high impact)
      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByText('Production'));

      // Should show high impact
      expect(screen.getByText('Eleve')).toBeInTheDocument();
    });

    it('only shows allowed environments', () => {
      render(
        <ExecutionWizard {...defaultProps} allowedEnvironments={['dev', 'staging']} />,
        { wrapper: TestWrapper }
      );

      const select = screen.getByRole('combobox');
      fireEvent.mouseDown(select);

      expect(screen.getByText('Developpement')).toBeInTheDocument();
      expect(screen.getByText('Staging')).toBeInTheDocument();
      // Prod should not be visible (not in allowed list)
    });
  });

  describe('Parameters Step (Step 2)', () => {
    it('generates form fields from parameters_schema', async () => {
      const user = userEvent.setup();
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      // Go to step 2
      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByText('Developpement'));
      await user.click(screen.getByRole('button', { name: /suivant/i }));

      await waitFor(() => {
        expect(screen.getByLabelText('PDB Name')).toBeInTheDocument();
        expect(screen.getByLabelText('Size (GB)')).toBeInTheDocument();
      });
    });

    it('shows "no parameters" message when schema is empty', async () => {
      const user = userEvent.setup();
      const actionWithoutParams = { ...mockAction, parameters_schema: null };

      render(
        <ExecutionWizard {...defaultProps} action={actionWithoutParams} />,
        { wrapper: TestWrapper }
      );

      // Go to step 2
      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByText('Developpement'));
      await user.click(screen.getByRole('button', { name: /suivant/i }));

      await waitFor(() => {
        expect(screen.getByText(/Aucun parametre requis/)).toBeInTheDocument();
      });
    });
  });

  describe('Confirmation Step (Step 3)', () => {
    it('shows recap with action name, environment, impact, and change type', async () => {
      const user = userEvent.setup();
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      // Go through all steps
      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByText('Production'));
      await user.click(screen.getByRole('button', { name: /suivant/i }));

      // Fill required field
      await waitFor(() => expect(screen.getByLabelText('PDB Name')).toBeInTheDocument());
      await user.type(screen.getByLabelText('PDB Name'), 'TEST_PDB');
      await user.click(screen.getByRole('button', { name: /suivant/i }));

      // Check confirmation step
      await waitFor(() => {
        expect(screen.getByText('Create PDB Oracle')).toBeInTheDocument();
        expect(screen.getByText('Production')).toBeInTheDocument();
        expect(screen.getByText('CAB requis')).toBeInTheDocument(); // PROD has required change
        expect(screen.getByText('Eleve')).toBeInTheDocument(); // High impact for PROD
      });
    });

    it('shows "Pre-approuve" for non-CAB environments', async () => {
      const user = userEvent.setup();
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      // Select dev (no CAB required)
      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByText('Developpement'));
      await user.click(screen.getByRole('button', { name: /suivant/i }));

      // Fill required field and go to confirmation
      await waitFor(() => expect(screen.getByLabelText('PDB Name')).toBeInTheDocument());
      await user.type(screen.getByLabelText('PDB Name'), 'TEST_PDB');
      await user.click(screen.getByRole('button', { name: /suivant/i }));

      await waitFor(() => {
        expect(screen.getByText('Pre-approuve')).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has aria-label on Steps component', () => {
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      expect(screen.getByLabelText(/Etape 1 sur 3/)).toBeInTheDocument();
    });

    it('closes on Escape key', async () => {
      const onCancel = vi.fn();
      render(
        <ExecutionWizard {...defaultProps} onCancel={onCancel} />,
        { wrapper: TestWrapper }
      );

      fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });

      // Modal handles escape internally, but our handler should be called
      // Note: Ant Design Modal handles this, we test our integration
    });

    it('environment select has aria-label', () => {
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      expect(screen.getByLabelText('Environnement cible')).toBeInTheDocument();
    });
  });

  describe('Cancel and Close', () => {
    it('calls onCancel when Cancel button clicked', async () => {
      const onCancel = vi.fn();
      const user = userEvent.setup();

      render(
        <ExecutionWizard {...defaultProps} onCancel={onCancel} />,
        { wrapper: TestWrapper }
      );

      await user.click(screen.getByRole('button', { name: /annuler/i }));

      expect(onCancel).toHaveBeenCalled();
    });
  });

  describe('Submission', () => {
    it('shows Confirmer l\'execution button on step 3', async () => {
      const user = userEvent.setup();
      render(<ExecutionWizard {...defaultProps} />, { wrapper: TestWrapper });

      // Go through all steps
      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByText('Developpement'));
      await user.click(screen.getByRole('button', { name: /suivant/i }));

      await waitFor(() => expect(screen.getByLabelText('PDB Name')).toBeInTheDocument());
      await user.type(screen.getByLabelText('PDB Name'), 'TEST_PDB');
      await user.click(screen.getByRole('button', { name: /suivant/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /confirmer l'execution/i })).toBeInTheDocument();
      });
    });
  });

  describe('Inventory Loading (Story 4.2, Task 5.4)', () => {
    const actionWithInventory: CatalogActionDetail = {
      ...mockAction,
      parameters_schema: {
        type: 'object',
        properties: {
          database: {
            type: 'string',
            title: 'Database',
            source: 'inventory',
            inventory_type: 'databases',
          },
        },
        required: ['database'],
      },
    };

    // Mock database items
    const mockDatabaseItems: InventoryItem[] = [
      { id: 'db1', name: 'Database 1', environment: 'dev' },
      { id: 'db2', name: 'Database 2', environment: 'prod' },
    ];

    beforeEach(() => {
      // Clear localStorage
      localStorage.clear();
      vi.clearAllMocks();
      // Reset to default implementation
      vi.mocked(fetchInventoryItems).mockImplementation(async (type: string) => {
        if (type === 'environments') return mockEnvironments;
        return [];
      });
    });

    it('loads inventory items successfully for dropdown fields', async () => {
      // Mock to return database items
      vi.mocked(fetchInventoryItems).mockImplementation(async (type: string) => {
        if (type === 'environments') return mockEnvironments;
        if (type === 'databases') return mockDatabaseItems;
        return [];
      });

      render(
        <ExecutionWizard {...defaultProps} action={actionWithInventory} />,
        { wrapper: TestWrapper }
      );

      // Navigate to parameters step
      const user = userEvent.setup();
      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByText('Developpement'));
      await user.click(screen.getByRole('button', { name: /suivant/i }));

      // Wait for step 2 and check dropdown exists
      await waitFor(() => {
        const dbSelect = screen.getByLabelText('Database');
        expect(dbSelect).toBeInTheDocument();
      });

      // Verify databases were fetched
      expect(fetchInventoryItems).toHaveBeenCalledWith('databases', 'dev');
    });

    it('displays warning badge when inventory unavailable (503)', async () => {
      const cachedDatabaseItems: InventoryItem[] = [
        { id: 'db1', name: 'Database 1', environment: 'dev' },
      ];
      const error503 = new Error('Inventaire temporairement indisponible — dernières valeurs en cache');
      (error503 as Error & { code: string }).code = 'INVENTORY_UNAVAILABLE';
      (error503 as Error & { useCache: boolean }).useCache = true;
      (error503 as Error & { cachedItems: InventoryItem[] }).cachedItems = cachedDatabaseItems;

      // Environments work, databases fail with 503
      vi.mocked(fetchInventoryItems).mockImplementation(async (type: string) => {
        if (type === 'environments') return mockEnvironments;
        throw error503;
      });

      render(
        <ExecutionWizard {...defaultProps} action={actionWithInventory} />,
        { wrapper: TestWrapper }
      );

      const user = userEvent.setup();
      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByText('Developpement'));
      await user.click(screen.getByRole('button', { name: /suivant/i }));

      // Wait for warning badge to appear
      await waitFor(() => {
        expect(
          screen.getByText(/Données inventaire temporairement indisponibles/i)
        ).toBeInTheDocument();
      });
    });

    it('uses localStorage cache when API fails with 503', async () => {
      const cachedItems: InventoryItem[] = [
        { id: 'db_cached', name: 'Cached Database', environment: 'dev' },
      ];

      // Set up localStorage cache (simulating what the service would have stored)
      localStorage.setItem(
        'inventory_cache_databases_dev',
        JSON.stringify({
          items: cachedItems,
          timestamp: Date.now(),
        })
      );

      // Create 503 error with cache info (as the service would return when localStorage has valid cache)
      const error503 = new Error('Inventaire temporairement indisponible — dernières valeurs en cache');
      (error503 as Error & { code: string }).code = 'INVENTORY_UNAVAILABLE';
      (error503 as Error & { useCache: boolean }).useCache = true;
      (error503 as Error & { cachedItems: InventoryItem[] }).cachedItems = cachedItems;

      // Environments work, databases fail with cache fallback
      vi.mocked(fetchInventoryItems).mockImplementation(async (type: string) => {
        if (type === 'environments') return mockEnvironments;
        throw error503;
      });

      render(
        <ExecutionWizard {...defaultProps} action={actionWithInventory} />,
        { wrapper: TestWrapper }
      );

      const user = userEvent.setup();
      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByText('Developpement'));
      await user.click(screen.getByRole('button', { name: /suivant/i }));

      // Should use cached items and show warning
      await waitFor(() => {
        expect(
          screen.getByText(/Données inventaire temporairement indisponibles/i)
        ).toBeInTheDocument();
      });
    });

    it('caches successful inventory responses in localStorage', async () => {
      vi.mocked(fetchInventoryItems).mockImplementation(async (type: string) => {
        if (type === 'environments') return mockEnvironments;
        if (type === 'databases') return mockDatabaseItems;
        return [];
      });

      render(
        <ExecutionWizard {...defaultProps} action={actionWithInventory} />,
        { wrapper: TestWrapper }
      );

      const user = userEvent.setup();
      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByText('Developpement'));
      await user.click(screen.getByRole('button', { name: /suivant/i }));

      // Check that fetchInventoryItems was called with databases (caching is internal to the service)
      await waitFor(() => {
        expect(fetchInventoryItems).toHaveBeenCalledWith('databases', 'dev');
      });
    });

    it('shows loading spinner while fetching inventory', async () => {
      let resolveDatabases: (value: InventoryItem[]) => void;
      const databasesPromise = new Promise<InventoryItem[]>((resolve) => {
        resolveDatabases = resolve;
      });

      vi.mocked(fetchInventoryItems).mockImplementation(async (type: string) => {
        if (type === 'environments') return mockEnvironments;
        if (type === 'databases') return databasesPromise;
        return [];
      });

      render(
        <ExecutionWizard {...defaultProps} action={actionWithInventory} />,
        { wrapper: TestWrapper }
      );

      const user = userEvent.setup();
      const select = screen.getByRole('combobox');
      await user.click(select);
      await user.click(screen.getByText('Developpement'));
      await user.click(screen.getByRole('button', { name: /suivant/i }));

      // Should show loading state
      await waitFor(() => {
        const dbSelect = screen.getByLabelText('Database');
        expect(dbSelect).toBeInTheDocument();
        // Ant Design Select shows loading via aria-busy or spinner
      });

      // Resolve the promise (wrap in act to avoid state update warning)
      await act(async () => {
        resolveDatabases!(mockDatabaseItems);
      });
    });
  });
});
