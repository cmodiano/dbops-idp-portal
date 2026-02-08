/**
 * Story 19.4 Integration Tests - ExecutionWizard → ExecutionView flow.
 *
 * Covers:
 * - AC1: Wizard closes, ExecutionView opens automatically after execution creation
 * - AC3: ExecutionView closes, stays on catalog
 * - AC5: Wizard stays open on POST failure
 * - AC8: Wizard state resets after success
 * - Task 2.3: CatalogPage → ExecutionWizard → ExecutionView integration
 * - Task 7.1: E2E flow ActionCard → Wizard → ExecutionView → Close
 */

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import CatalogPage from './CatalogPage';
import * as catalogService from '../services/catalog_service';
import * as executionService from '../services/execution_service';
import * as authContext from '../contexts/AuthContext';
import type { CatalogAction, CatalogActionDetail, FavoriteEntry } from '../services/catalog_service';
import type { ExecutionResponse } from '../types/api';

vi.mock('../services/catalog_service', () => ({
  fetchCatalogActions: vi.fn(),
  fetchCatalogActionById: vi.fn(),
  fetchCatalogTags: vi.fn(),
  fetchFavorites: vi.fn(),
  addFavorite: vi.fn(),
  removeFavorite: vi.fn(),
  fetchActionStats: vi.fn(),
}));

vi.mock('../services/execution_service', () => ({
  submitExecution: vi.fn(),
  getExecution: vi.fn(),
  getExecutionSteps: vi.fn(() => Promise.resolve([])),
  fetchInventoryItems: vi.fn(() => Promise.resolve([])),
  fetchInventoryTargets: vi.fn(() => Promise.resolve([])),
}));

vi.mock('../services/logger', () => ({
  default: { info: vi.fn(), error: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: vi.fn(() => ({
    isAuthenticated: true,
    isBusinessProfile: false,
    user: { id: 1, email: 'test@example.com', display_name: 'Test User' },
  })),
}));

vi.mock('../contexts/ThemeContext', () => ({
  useTheme: vi.fn(() => ({
    theme: 'light',
    setTheme: vi.fn(),
  })),
  ThemeProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: vi.fn(() => ({
    steps: [],
    execution: null,
    loading: false,
    error: null,
    lastMessage: null,
  })),
}));

vi.mock('../hooks/useExecutionPolling', () => ({
  useExecutionPolling: vi.fn(() => ({
    execution: null,
    steps: [],
    isPolling: false,
    error: null,
  })),
}));

vi.mock('../hooks/useRemediationSuggestions', () => ({
  useRemediationSuggestions: vi.fn(() => ({
    suggestions: null,
    loading: false,
  })),
}));

vi.mock('../hooks/useRemediationContext', () => ({
  useRemediationContext: vi.fn(() => ({
    context: null,
    loading: false,
  })),
}));

const Wrapper = ({ children }: { children: React.ReactNode }) => <App>{children}</App>;

const mockAction: CatalogAction = {
  id: 10,
  name: 'Deploy Application',
  description: 'Deploy app to environment',
  engine: 'AAP',
  platform: 'Linux',
  impact_level: 'MEDIUM',
  parameters_schema: {
    type: 'object',
    properties: {
      version: { type: 'string', title: 'Version' },
    },
    required: [],
  },
  tags: ['deployment'],
  execution_count: 5,
  item_type: 'action',
};

const mockActionDetail: CatalogActionDetail = {
  ...mockAction,
  engine_details: {},
  parameters_schema: {
    type: 'object',
    properties: {
      version: { type: 'string', title: 'Version', default: '1.0.0' },
    },
    required: [],
  },
};

const mockExecution: ExecutionResponse = {
  id: 42,
  action_id: 10,
  action_name: 'Deploy Application',
  user_id: 1,
  user_display_name: 'Test User',
  environment: 'dev',
  parameters: { version: '1.0.0' },
  status: 'RUNNING',
  servicenow_change_id: null,
  started_at: new Date().toISOString(),
  completed_at: null,
  created_at: new Date().toISOString(),
};

describe('Story 19.4 Integration - ExecutionWizard → ExecutionView flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(catalogService.fetchCatalogActions).mockResolvedValue([mockAction]);
    vi.mocked(catalogService.fetchCatalogActionById).mockResolvedValue({
      data: mockActionDetail,
      can_execute: true,
      allowed_environments: ['dev', 'staging'],
    });
    vi.mocked(catalogService.fetchCatalogTags).mockResolvedValue([]);
    vi.mocked(catalogService.fetchFavorites).mockResolvedValue([]);
    vi.mocked(catalogService.fetchActionStats).mockResolvedValue(null);
    vi.mocked(executionService.getExecution).mockResolvedValue(mockExecution);
  });

  // Task 2.3, Subtask 2.3: AC1-2 integration test
  it('AC1-2: opens ExecutionView automatically after wizard success', async () => {
    vi.mocked(executionService.submitExecution).mockResolvedValue({ execution_id: 42 } as any);

    render(<CatalogPage />, { wrapper: Wrapper });

    // Wait for catalog to load
    await waitFor(() => screen.getByText('Catalogue'));

    // 1. Click action card to open drawer
    const actionCard = await screen.findByText('Deploy Application');
    await userEvent.click(actionCard);

    // Wait for drawer to open
    await waitFor(() => screen.getByRole('dialog'));

    // 2. Click "Exécuter" button in drawer to open ExecutionWizard
    const executeButton = await screen.findByRole('button', { name: /exécuter/i });
    await userEvent.click(executeButton);

    // Wait for ExecutionWizard modal
    await waitFor(() => screen.getByRole('dialog', { name: /exécution/i }), { timeout: 3000 });

    // 3. Fill wizard step 1 (skip target selection if not required)
    // Assuming action doesn't require targets, click "Suivant"
    const nextButton = screen.getByRole('button', { name: /suivant/i });
    await userEvent.click(nextButton);

    // 4. Fill wizard step 2 (parameters) - version already has default
    const nextButton2 = screen.getByRole('button', { name: /suivant/i });
    await userEvent.click(nextButton2);

    // 5. Confirm execution (step 3)
    const confirmButton = screen.getByRole('button', { name: /exécuter/i });
    await userEvent.click(confirmButton);

    // AC1: Vérifier wizard fermé
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: /exécution/i })).not.toBeInTheDocument();
    }, { timeout: 5000 });

    // AC2: Vérifier ExecutionView ouvert
    await waitFor(() => {
      expect(screen.getByTestId('execution-view-drawer')).toBeVisible();
    }, { timeout: 5000 });

    // Vérifier executionId passé à ExecutionView
    expect(screen.getByText(/Deploy Application/)).toBeInTheDocument();
    expect(executionService.getExecution).toHaveBeenCalledWith(42);
  });

  // Task 2.3, Subtask 2.3: AC3 test
  it('AC3: closes ExecutionView and stays on catalog on close button', async () => {
    vi.mocked(executionService.submitExecution).mockResolvedValue({ execution_id: 42 } as any);

    render(<CatalogPage />, { wrapper: Wrapper });

    await waitFor(() => screen.getByText('Catalogue'));

    // Open wizard and submit execution (simplified flow)
    const actionCard = await screen.findByText('Deploy Application');
    await userEvent.click(actionCard);
    await waitFor(() => screen.getByRole('dialog'));

    const executeButton = await screen.findByRole('button', { name: /exécuter/i });
    await userEvent.click(executeButton);

    await waitFor(() => screen.getByRole('dialog', { name: /exécution/i }));

    // Skip to confirmation (assume no validation errors)
    const nextButton = screen.getByRole('button', { name: /suivant/i });
    await userEvent.click(nextButton);
    const nextButton2 = screen.getByRole('button', { name: /suivant/i });
    await userEvent.click(nextButton2);

    const confirmButton = screen.getByRole('button', { name: /exécuter/i });
    await userEvent.click(confirmButton);

    // Wait for ExecutionView to open
    await waitFor(() => screen.getByTestId('execution-view-drawer'), { timeout: 5000 });

    // Click close button in ExecutionView
    const closeButton = screen.getByTestId('close-execution-view');
    await userEvent.click(closeButton);

    // AC3: Vérifier ExecutionView fermé
    await waitFor(() => {
      expect(screen.queryByTestId('execution-view-drawer')).not.toBeInTheDocument();
    });

    // AC3: Vérifier toujours sur CatalogPage
    expect(screen.getByText('Catalogue')).toBeInTheDocument();
  });

  // Task 2.3, AC5: Wizard stays open on error
  it('AC5: displays error in wizard without closing on POST failure', async () => {
    vi.mocked(executionService.submitExecution).mockRejectedValue(new Error('Invalid parameters'));

    render(<CatalogPage />, { wrapper: Wrapper });

    await waitFor(() => screen.getByText('Catalogue'));

    // Open wizard
    const actionCard = await screen.findByText('Deploy Application');
    await userEvent.click(actionCard);
    await waitFor(() => screen.getByRole('dialog'));

    const executeButton = await screen.findByRole('button', { name: /exécuter/i });
    await userEvent.click(executeButton);

    await waitFor(() => screen.getByRole('dialog', { name: /exécution/i }));

    // Fill wizard and submit
    const nextButton = screen.getByRole('button', { name: /suivant/i });
    await userEvent.click(nextButton);
    const nextButton2 = screen.getByRole('button', { name: /suivant/i });
    await userEvent.click(nextButton2);

    const confirmButton = screen.getByRole('button', { name: /exécuter/i });
    await userEvent.click(confirmButton);

    // AC5: Vérifier erreur affichée dans wizard
    await waitFor(() => {
      expect(screen.getByText(/erreur lors de la soumission/i)).toBeInTheDocument();
    });

    // AC5: Vérifier wizard toujours ouvert
    expect(screen.getByRole('dialog', { name: /exécution/i })).toBeVisible();

    // AC5: Vérifier ExecutionView ne s'ouvre PAS
    expect(screen.queryByTestId('execution-view-drawer')).not.toBeInTheDocument();
  });

  // Task 2.3, AC8: Wizard state resets after success
  it('AC8: resets wizard state after execution success', async () => {
    vi.mocked(executionService.submitExecution).mockResolvedValue({ execution_id: 42 } as any);

    render(<CatalogPage />, { wrapper: Wrapper });

    await waitFor(() => screen.getByText('Catalogue'));

    // Open wizard and submit execution
    const actionCard = await screen.findByText('Deploy Application');
    await userEvent.click(actionCard);
    await waitFor(() => screen.getByRole('dialog'));

    const executeButton = await screen.findByRole('button', { name: /exécuter/i });
    await userEvent.click(executeButton);

    await waitFor(() => screen.getByRole('dialog', { name: /exécution/i }));

    // Fill and submit
    const nextButton = screen.getByRole('button', { name: /suivant/i });
    await userEvent.click(nextButton);
    const nextButton2 = screen.getByRole('button', { name: /suivant/i });
    await userEvent.click(nextButton2);

    const confirmButton = screen.getByRole('button', { name: /exécuter/i });
    await userEvent.click(confirmButton);

    // Wait for wizard to close
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: /exécution/i })).not.toBeInTheDocument();
    }, { timeout: 5000 });

    // AC8: Vérifier ExecutionView ouvert (confirme wizard fermé)
    await waitFor(() => {
      expect(screen.getByTestId('execution-view-drawer')).toBeVisible();
    });

    // Close ExecutionView
    const closeButton = screen.getByTestId('close-execution-view');
    await userEvent.click(closeButton);

    // AC8: Re-open wizard from same action - should be reset (step 0, empty form)
    const actionCard2 = await screen.findByText('Deploy Application');
    await userEvent.click(actionCard2);
    await waitFor(() => screen.getByRole('dialog'));

    const executeButton2 = await screen.findByRole('button', { name: /exécuter/i });
    await userEvent.click(executeButton2);

    // Wizard should open at step 1 (targets), not step 3
    await waitFor(() => {
      const wizard = screen.getByRole('dialog', { name: /exécution/i });
      expect(within(wizard).getByText(/cible/i)).toBeInTheDocument();
    });
  });
});
