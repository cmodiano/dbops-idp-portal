/**
 * ExecutionView tests (Story 19.1).
 * Covers AC1 (drawer opens), AC7 (close), AC8 (metadata), AC9 (error/refresh), AC10 (action badge).
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { ExecutionView } from './ExecutionView';
import * as executionService from '../../services/execution_service';
import type { ExecutionResponse } from '../../types/api';

vi.mock('../../services/execution_service', () => ({
  getExecution: vi.fn(),
  getExecutionSteps: vi.fn(() => Promise.resolve([])),
}));

vi.mock('../../services/admin_service', () => ({
  getAction: vi.fn(() => Promise.resolve({ workflow_steps: [] })),
}));

vi.mock('../../services/logger', () => ({
  default: { warn: vi.fn(), error: vi.fn(), info: vi.fn(), debug: vi.fn() },
}));

vi.mock('../../hooks/useWebSocket', () => ({
  useWebSocket: vi.fn(() => ({
    steps: [],
    execution: null,
    loading: false,
    error: null,
    lastMessage: null,
  })),
}));

vi.mock('../../hooks/useExecutionPolling', () => ({
  useExecutionPolling: vi.fn(() => ({
    execution: null,
    steps: [],
    isPolling: false,
    error: null,
  })),
}));

vi.mock('../../hooks/useRemediationSuggestions', () => ({
  useRemediationSuggestions: vi.fn(() => ({
    suggestions: null,
    loading: false,
  })),
}));

vi.mock('../../hooks/useRemediationContext', () => ({
  useRemediationContext: vi.fn(() => ({
    context: null,
    loading: false,
  })),
}));

const Wrapper = ({ children }: { children: React.ReactNode }) => <App>{children}</App>;

const mockExecution: ExecutionResponse = {
  id: 1,
  action_id: 10,
  action_name: 'Deploy App',
  user_id: 5,
  user_display_name: 'John Doe',
  environment: 'dev',
  parameters: null,
  status: 'RUNNING',
  servicenow_change_id: null,
  started_at: new Date().toISOString(),
  completed_at: null,
  created_at: new Date().toISOString(),
};

describe('ExecutionView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(executionService.getExecution).mockResolvedValue(mockExecution);
  });

  it('AC1: opens drawer when executionId is provided', async () => {
    render(<ExecutionView executionId={1} onClose={vi.fn()} />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText('Deploy App')).toBeInTheDocument();
    });
    expect(screen.getByTestId('execution-view-drawer')).toBeInTheDocument();
  });

  it('AC1: does not open drawer when executionId is null', () => {
    render(<ExecutionView executionId={null} onClose={vi.fn()} />, { wrapper: Wrapper });

    // Drawer should have open=false, no header rendered
    expect(screen.queryByTestId('execution-view-header')).not.toBeInTheDocument();
  });

  it('AC8: displays execution metadata header', async () => {
    render(<ExecutionView executionId={1} onClose={vi.fn()} />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
      expect(screen.getByText('Développement')).toBeInTheDocument();
      expect(screen.getByText('En cours')).toBeInTheDocument();
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });
  });

  it('AC10: shows "Action" badge when workflow_id is null/undefined', async () => {
    render(<ExecutionView executionId={1} onClose={vi.fn()} />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText('Action')).toBeInTheDocument();
    });
  });

  it('AC10: shows "Workflow" badge when item_type is workflow', async () => {
    const workflowExecution = { ...mockExecution, item_type: 'workflow' as const };
    vi.mocked(executionService.getExecution).mockResolvedValue(workflowExecution);

    render(<ExecutionView executionId={1} onClose={vi.fn()} />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText('Workflow')).toBeInTheDocument();
    });
  });

  it('AC7: calls onClose when close button is clicked', async () => {
    const onClose = vi.fn();
    render(<ExecutionView executionId={1} onClose={onClose} />, { wrapper: Wrapper });

    await waitFor(() => screen.getByText('Deploy App'));

    const closeButton = screen.getByTestId('close-execution-view');
    await userEvent.click(closeButton);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('AC7: calls redirectOnClose after onClose', async () => {
    const onClose = vi.fn();
    const redirectOnClose = vi.fn();
    render(<ExecutionView executionId={1} onClose={onClose} redirectOnClose={redirectOnClose} />, { wrapper: Wrapper });

    await waitFor(() => screen.getByText('Deploy App'));

    const closeButton = screen.getByTestId('close-execution-view');
    await userEvent.click(closeButton);

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(redirectOnClose).toHaveBeenCalledTimes(1);
  });

  it('AC6: displays warning alert with reconnection message on network error', async () => {
    vi.mocked(executionService.getExecution).mockRejectedValue(new Error('Network error'));

    render(<ExecutionView executionId={1} onClose={vi.fn()} />, { wrapper: Wrapper });

    await waitFor(() => {
      // Story 19.4 AC6: Warning alert with reconnection message
      expect(screen.getByText('Connexion perdue. Tentative de reconnexion...')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
    expect(screen.getByTestId('execution-view-error')).toBeInTheDocument();
  });

  it('AC9: refresh button retries API call and recovers', async () => {
    vi.mocked(executionService.getExecution)
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce(mockExecution);

    render(<ExecutionView executionId={1} onClose={vi.fn()} />, { wrapper: Wrapper });

    await waitFor(() => screen.getByText('Network error'));

    const refreshButton = screen.getByText('Rafraîchir');
    await userEvent.click(refreshButton);

    await waitFor(() => {
      expect(screen.getByText('Deploy App')).toBeInTheDocument();
    });
  });

  it('AC8: displays environment badge for production', async () => {
    const prodExecution = { ...mockExecution, environment: 'prod' as const };
    vi.mocked(executionService.getExecution).mockResolvedValue(prodExecution);

    render(<ExecutionView executionId={1} onClose={vi.fn()} />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText('Production')).toBeInTheDocument();
    });
  });

  it('AC8: displays completed status and duration for finished execution', async () => {
    const completedExecution = {
      ...mockExecution,
      status: 'COMPLETED' as const,
      started_at: '2026-02-08T10:00:00Z',
      completed_at: '2026-02-08T10:02:30Z',
    };
    vi.mocked(executionService.getExecution).mockResolvedValue(completedExecution);

    render(<ExecutionView executionId={1} onClose={vi.fn()} />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText('Terminé')).toBeInTheDocument();
      expect(screen.getByText('2m 30s')).toBeInTheDocument();
      expect(screen.getByText('Durée:')).toBeInTheDocument();
    });
  });

  it('AC8: shows elapsed time label for running execution', async () => {
    render(<ExecutionView executionId={1} onClose={vi.fn()} />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText('Temps écoulé:')).toBeInTheDocument();
    });
  });

  // Story 19.4 AC10: Accessibility tests
  it('AC10: has aria-live region announcing execution status', async () => {
    render(<ExecutionView executionId={1} onClose={vi.fn()} />, { wrapper: Wrapper });

    await waitFor(() => {
      const liveRegion = screen.getByTestId('execution-view-live-region');
      expect(liveRegion).toHaveAttribute('aria-live', 'polite');
      expect(liveRegion).toHaveTextContent(/Exécution #1/);
      expect(liveRegion).toHaveTextContent(/En cours/);
    });
  });

  it('AC10: shows initial announcement before execution loads', () => {
    vi.mocked(executionService.getExecution).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    render(<ExecutionView executionId={1} onClose={vi.fn()} />, { wrapper: Wrapper });

    const liveRegion = screen.getByTestId('execution-view-live-region');
    expect(liveRegion).toHaveTextContent('Exécution créée, suivi en cours');
  });

  it('AC10: close button has aria-label', async () => {
    render(<ExecutionView executionId={1} onClose={vi.fn()} />, { wrapper: Wrapper });

    await waitFor(() => {
      const closeButton = screen.getByTestId('close-execution-view');
      expect(closeButton).toHaveAttribute('aria-label', "Fermer la vue d'exécution");
    });
  });

  it('AC10: moves focus to close button after drawer opens', async () => {
    render(<ExecutionView executionId={1} onClose={vi.fn()} />, { wrapper: Wrapper });

    await waitFor(() => screen.getByText('Deploy App'));

    // Wait for focus to move after Drawer animation (350ms delay)
    await waitFor(() => {
      const closeButton = screen.getByTestId('close-execution-view');
      expect(closeButton).toHaveFocus();
    }, { timeout: 500 });
  });

  it('AC10: drawer has aria-label for screen readers', () => {
    render(<ExecutionView executionId={1} onClose={vi.fn()} />, { wrapper: Wrapper });

    const drawer = screen.getByTestId('execution-view-drawer');
    expect(drawer).toBeInTheDocument();
  });

  // Story 19.4 AC9: Remediation badge
  it('AC9: shows remediation badge when parent_execution_id is present', async () => {
    const remediationExecution = { ...mockExecution, parent_execution_id: 42 };
    vi.mocked(executionService.getExecution).mockResolvedValue(remediationExecution);

    render(<ExecutionView executionId={1} onClose={vi.fn()} />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText('Remédiation de #42')).toBeInTheDocument();
    });
  });

  it('AC9: does not show remediation badge when parent_execution_id is null', async () => {
    render(<ExecutionView executionId={1} onClose={vi.fn()} />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByText('Deploy App')).toBeInTheDocument();
    });
    expect(screen.queryByText(/Remédiation de/)).not.toBeInTheDocument();
  });
});
