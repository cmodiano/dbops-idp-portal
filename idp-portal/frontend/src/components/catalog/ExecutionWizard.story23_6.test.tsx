/**
 * Integration tests for ExecutionWizard - Story 23.6.
 *
 * Tests validate:
 * - No inventory fetch for actions without inventory params (requires_target=false)
 * - selectedServerNames=[] propagated with server_names:[] for instances
 * - Alert displayed when no servers selected for instance fields
 * - Retrocompatibility: manual fields unaffected
 *
 * Note: Full target selection integration (picking servers then verifying
 * instance filtering) is covered by unit tests on useTargetInventory and
 * renderFieldInput (37 tests total).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { App } from 'antd';
import { ExecutionWizard } from './ExecutionWizard';
import type { CatalogActionDetail } from '../../services/catalog_service';
import { fetchInventoryItems } from '../../services/execution_service';

// Mock API client
vi.mock('../../services/api_client', () => ({
  apiFetch: vi.fn(),
  apiFetchRaw: vi.fn().mockResolvedValue({
    items: [],
    total: 0,
    page: 1,
    page_size: 5000,
    total_pages: 0,
  }),
}));

// Mock execution service
vi.mock('../../services/execution_service', () => ({
  submitExecution: vi.fn().mockResolvedValue({
    execution_id: 123,
    status: 'SUBMITTED',
    created_at: '2026-02-09T10:00:00Z',
  }),
  fetchInventoryItems: vi.fn().mockImplementation(async (type: string) => {
    if (type === 'environments') {
      return [
        { id: 'dev', name: 'Developpement', environment: null },
      ];
    }
    return [{ id: 'inst01', name: 'ORCL01', environment: 'dev' }];
  }),
  fetchInventoryTargets: vi.fn().mockResolvedValue([]),
}));

// Mock catalog service
vi.mock('../../services/catalog_service', () => ({
  fetchCatalogActionById: vi.fn(),
}));

const TestWrapper = ({ children }: { children: React.ReactNode }) => (
  <App>{children}</App>
);

const mkAction = (
  id: number,
  name: string,
  schema: Record<string, unknown> | null,
): CatalogActionDetail => ({
  id,
  name,
  description: `Test action ${name}`,
  engine: 'Oracle',
  platform: 'AAP',
  parameters_schema: schema,
  impact_level: null,
  impact_rules: null,
  default_impact_level: 'low',
  status: 'published',
  created_at: '2026-02-09T00:00:00Z',
  tags: ['oracle'],
  execution_count: 0,
  requires_target: false, // All tests use requires_target=false for simpler navigation
});

const instanceSchema = {
  type: 'object',
  properties: {
    instance_name: {
      type: 'string',
      title: 'Nom de l\'instance',
      source: 'inventory',
      inventory_type: 'instances',
    },
  },
  required: ['instance_name'],
};

const manualSchema = {
  type: 'object',
  properties: {
    patch_version: { type: 'string', title: 'Version du patch' },
  },
  required: [],
};

describe('ExecutionWizard - Story 23.6 (selectedServerNames)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchInventoryItems).mockImplementation(async (type: string) => {
      if (type === 'environments') {
        return [{ id: 'dev', name: 'Developpement', environment: null }];
      }
      return [{ id: 'inst01', name: 'ORCL01', environment: 'dev' }];
    });
  });

  it('passe server_names vide quand aucun serveur sélectionné (requires_target=false)', async () => {
    // requires_target=false + single env → auto-selected, so Suivant is clickable
    const action = mkAction(10, 'Instance Action', instanceSchema);

    render(
      <TestWrapper>
        <ExecutionWizard
          open={true}
          action={action}
          allowedEnvironments={['dev']}
          onCancel={vi.fn()}
          initialParams={{ environment: 'dev' }}
        />
      </TestWrapper>
    );

    // Click Suivant to go to step 2
    await waitFor(() => {
      expect(screen.getByText('Suivant')).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Suivant'));
    });

    // Wait for inventory loading
    await waitFor(() => {
      const instanceCalls = vi.mocked(fetchInventoryItems).mock.calls.filter(
        (call) => call[0] === 'instances'
      );
      expect(instanceCalls.length).toBeGreaterThanOrEqual(1);
    }, { timeout: 5000 });

    // Verify server_names is empty array (no targets selected)
    // Story 37.3: engine_type is also passed since action.engine = 'Oracle'
    const instanceCalls = vi.mocked(fetchInventoryItems).mock.calls.filter(
      (call) => call[0] === 'instances'
    );
    const lastCall = instanceCalls[instanceCalls.length - 1];
    expect(lastCall[2]).toEqual(expect.objectContaining({ server_names: [] }));
  });

  it('action sans paramètre inventaire ne déclenche pas fetchInventoryItems pour instances', async () => {
    const action = mkAction(11, 'Manual Action', manualSchema);

    render(
      <TestWrapper>
        <ExecutionWizard
          open={true}
          action={action}
          allowedEnvironments={['dev']}
          onCancel={vi.fn()}
          initialParams={{ environment: 'dev' }}
        />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Suivant')).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Suivant'));
    });

    // Wait a bit
    await new Promise((r) => setTimeout(r, 500));

    // No instances fetch
    const instanceCalls = vi.mocked(fetchInventoryItems).mock.calls.filter(
      (call) => call[0] === 'instances'
    );
    expect(instanceCalls.length).toBe(0);
  });

  it('affiche Alert info pour champ instances quand selectedServerNames vide', async () => {
    const action = mkAction(12, 'Instance Alert Action', instanceSchema);

    render(
      <TestWrapper>
        <ExecutionWizard
          open={true}
          action={action}
          allowedEnvironments={['dev']}
          onCancel={vi.fn()}
          initialParams={{ environment: 'dev' }}
        />
      </TestWrapper>
    );

    // Navigate to step 2
    await waitFor(() => {
      expect(screen.getByText('Suivant')).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Suivant'));
    });

    // Verify Alert is shown for instance field (no server selected)
    await waitFor(() => {
      expect(
        screen.getByText(/Veuillez d'abord sélectionner un serveur/i)
      ).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('champ manual non impacté par selectedServerNames', async () => {
    const mixedSchema = {
      type: 'object',
      properties: {
        instance_name: {
          type: 'string',
          title: 'Nom de l\'instance',
          source: 'inventory',
          inventory_type: 'instances',
        },
        patch_version: {
          type: 'string',
          title: 'Version du patch',
        },
      },
      required: [],
    };

    const action = mkAction(13, 'Mixed Action', mixedSchema);

    render(
      <TestWrapper>
        <ExecutionWizard
          open={true}
          action={action}
          allowedEnvironments={['dev']}
          onCancel={vi.fn()}
          initialParams={{ environment: 'dev' }}
        />
      </TestWrapper>
    );

    // Navigate to step 2
    await waitFor(() => {
      expect(screen.getByText('Suivant')).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Suivant'));
    });

    // Verify: Alert for instance field + text input for manual field
    await waitFor(() => {
      // Instance field shows Alert
      expect(
        screen.getByText(/Veuillez d'abord sélectionner un serveur/i)
      ).toBeInTheDocument();
      // Manual field renders (text input exists)
      expect(screen.getByLabelText('Version du patch')).toBeInTheDocument();
    }, { timeout: 5000 });
  });
});
