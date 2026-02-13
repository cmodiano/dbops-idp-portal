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
import type { CatalogAction, CatalogActionDetail } from '../services/catalog_service';
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
    effectiveMode: 'light',
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
  impact_level: 'medium',
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
  requires_target: false,
  status: 'published',
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

/** Helper: open catalog, click action card, open drawer, click Execute to open wizard */
async function openWizard() {
  // Wait for catalog to load
  await waitFor(() => screen.getByText('Catalogue'));

  // 1. Click action card to open drawer
  const actionCard = await screen.findByText('Deploy Application');
  await userEvent.click(actionCard);

  // Wait for drawer to open and detail to load
  await waitFor(() => screen.getByRole('dialog'));

  // 2. Click "Executer" button in drawer to open ExecutionWizard
  const executeButton = await screen.findByRole('button', { name: /executer/i });
  await userEvent.click(executeButton);

  // Wait for ExecutionWizard modal (title = "Executer: Deploy Application")
  await waitFor(() => screen.getByText(/Executer.*Deploy Application/i), { timeout: 3000 });
}

/** Helper: navigate wizard steps and submit (step 0 → 1 → 2 → submit) */
async function fillAndSubmitWizard() {
  // Step 0 → Step 1: click "Suivant" (target step skipped since requires_target=false)
  const nextButton = await screen.findByRole('button', { name: /suivant/i }, { timeout: 3000 });
  await userEvent.click(nextButton);

  // Step 1 → Step 2: click "Suivant" (parameters — version has default)
  const nextButton2 = await screen.findByRole('button', { name: /suivant/i }, { timeout: 3000 });
  await userEvent.click(nextButton2);

  // Step 2: click submit button ("Exécuter maintenant")
  const confirmButton = await screen.findByRole('button', { name: /maintenant/i }, { timeout: 3000 });
  await userEvent.click(confirmButton);
}

describe('Story 19.4 Integration - ExecutionWizard → ExecutionView flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(catalogService.fetchCatalogActions).mockResolvedValue([mockAction]);
    vi.mocked(catalogService.fetchCatalogActionById).mockResolvedValue({
      data: mockActionDetail,
      can_execute: true,
      allowed_environments: ['dev'],
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

    await openWizard();
    await fillAndSubmitWizard();

    // AC1: Vérifier wizard fermé
    await waitFor(() => {
      expect(screen.queryByText(/Executer.*Deploy Application/i)).not.toBeInTheDocument();
    }, { timeout: 5000 });

    // AC2: Vérifier ExecutionView ouvert
    await waitFor(() => {
      expect(screen.getByTestId('execution-view-drawer')).toBeVisible();
    }, { timeout: 5000 });

    // Vérifier executionId passé à ExecutionView (plusieurs "Deploy Application" peuvent exister, au moins un dans le drawer)
    expect(screen.getByTestId('execution-view-drawer')).toBeInTheDocument();
    expect(within(screen.getByTestId('execution-view-drawer')).getByText(/Deploy Application/)).toBeInTheDocument();
    expect(executionService.getExecution).toHaveBeenCalledWith(42);
  });

  // Task 2.3, Subtask 2.3: AC3 test
  it('AC3: closes ExecutionView and stays on catalog on close button', async () => {
    vi.mocked(executionService.submitExecution).mockResolvedValue({ execution_id: 42 } as any);

    render(<CatalogPage />, { wrapper: Wrapper });

    await openWizard();
    await fillAndSubmitWizard();

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

    await openWizard();
    await fillAndSubmitWizard();

    // AC5: Vérifier erreur affichée dans wizard (error message or fallback)
    await waitFor(() => {
      expect(screen.getByText(/Invalid parameters/i)).toBeInTheDocument();
    });

    // AC5: Vérifier wizard toujours ouvert (title still visible)
    expect(screen.getByText(/Executer.*Deploy Application/i)).toBeVisible();

    // AC5: Vérifier ExecutionView ne s'ouvre PAS
    expect(screen.queryByTestId('execution-view-drawer')).not.toBeInTheDocument();
  });

  // Task 2.3, AC8: Wizard state resets after success
  it('AC8: resets wizard state after execution success', { timeout: 20000 }, async () => {
    vi.mocked(executionService.submitExecution).mockResolvedValue({ execution_id: 42 } as any);

    render(<CatalogPage />, { wrapper: Wrapper });

    await openWizard();
    await fillAndSubmitWizard();

    // Wait for wizard to close
    await waitFor(() => {
      expect(screen.queryByText(/Executer.*Deploy Application/i)).not.toBeInTheDocument();
    }, { timeout: 5000 });

    // AC8: Vérifier ExecutionView ouvert (confirme wizard fermé)
    await waitFor(() => {
      expect(screen.getByTestId('execution-view-drawer')).toBeVisible();
    });

    // Close ExecutionView
    const closeButton = screen.getByTestId('close-execution-view');
    await userEvent.click(closeButton);

    // AC8: Re-open wizard from same action - should be reset (initial step, not step 3)
    const actionCard2 = await screen.findByText('Deploy Application');
    await userEvent.click(actionCard2);
    await waitFor(() => screen.getByRole('dialog'));

    const executeButton2 = await screen.findByRole('button', { name: /executer/i });
    await userEvent.click(executeButton2);

    // Wizard should open again at initial step (not at final submit step)
    await waitFor(() => {
      expect(screen.getByText(/Executer.*Deploy Application/i)).toBeVisible();
      expect(screen.queryByRole('button', { name: /Exécuter maintenant/i })).not.toBeInTheDocument();
    }, { timeout: 5000 });
  });
});
