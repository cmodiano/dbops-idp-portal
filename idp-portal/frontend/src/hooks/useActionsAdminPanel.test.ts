/**
 * Tests pour useActionsAdminPanel (Story 48.8, AC5, AC6).
 * Vérifie que le hook encapsule correctement les opérations CRUD de ActionsAdminPanel.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useActionsAdminPanel } from './useActionsAdminPanel';

vi.mock('../services/admin_service', () => ({
  getAdminActions: vi.fn(),
  createAction: vi.fn(),
  getAction: vi.fn(),
  updateAction: vi.fn(),
  updateActionStatus: vi.fn(),
  deleteAction: vi.fn(),
  deactivateAction: vi.fn(),
  reactivateAction: vi.fn(),
}));

import {
  getAdminActions,
  createAction,
  deactivateAction,
  reactivateAction,
} from '../services/admin_service';
import type { ActionListItem, ActionCreate, ActionResponse } from '../types/api';

const MOCK_ACTIONS: ActionListItem[] = [
  { id: 1, name: 'Action A', engine: 'Oracle', status: 'published', created_at: '', execution_count: 0 },
  { id: 2, name: 'Action B', engine: 'PostgreSQL', status: 'draft', created_at: '', execution_count: 0 },
];

// Mocks for useActionsAdminPanel — use 'as any' when passing to satisfy Ant Design types
const MOCK_NOTIFICATION = {
  error: vi.fn(),
  success: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
  open: vi.fn(),
  destroy: vi.fn(),
};

const MOCK_MODAL = {
  confirm: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
  error: vi.fn(),
  success: vi.fn(),
  update: vi.fn(),
  destroy: vi.fn(),
};

describe('useActionsAdminPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getAdminActions).mockResolvedValue({ data: MOCK_ACTIONS } as never);
  });

  it('expose les actions après fetchActions', async () => {
    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    await act(async () => {
      await result.current.fetchActions();
    });

    expect(result.current.actions).toHaveLength(2);
    expect(result.current.actions[0].name).toBe('Action A');
    expect(result.current.loading).toBe(false);
  });

  it('handleCreate succès — appelle createAction et retourne la réponse', async () => {
    const mockResponse: ActionResponse = { id: 3, name: 'Nouvelle', status: 'draft', engine: 'Oracle' } as never;
    vi.mocked(createAction).mockResolvedValue(mockResponse);

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    const payload: ActionCreate = { name: 'Nouvelle', engine: 'Oracle' } as never;
    let created!: ActionResponse;
    await act(async () => {
      created = await result.current.handleCreate(payload);
    });

    expect(created).toEqual(mockResponse);
    expect(createAction).toHaveBeenCalledWith(payload);
  });

  it('handleCreate erreur — expose submitError et re-throw', async () => {
    vi.mocked(createAction).mockRejectedValue(new Error('Validation failed'));

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    await act(async () => {
      await expect(result.current.handleCreate({} as never)).rejects.toThrow('Validation failed');
    });

    expect(result.current.submitError).toBe('Validation failed');
  });

  it('handleDelete — appelle modal.confirm', () => {
    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    act(() => {
      result.current.handleDelete(MOCK_ACTIONS[0]);
    });

    expect(MOCK_MODAL.confirm).toHaveBeenCalledOnce();
    const confirmCall = vi.mocked(MOCK_MODAL.confirm).mock.calls[0][0] as { title: string };
    expect(confirmCall.title).toContain("Supprimer");
  });

  it('handleDeactivate simple — notifie succès et recharge les actions', async () => {
    vi.mocked(deactivateAction).mockResolvedValue({ id: 1, status: 'disabled' } as never);

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    await act(async () => {
      await result.current.handleDeactivate(MOCK_ACTIONS[0]);
    });

    expect(MOCK_NOTIFICATION.success).toHaveBeenCalledOnce();
    expect(getAdminActions).toHaveBeenCalled();
  });

  it('handleDeactivate cascade — ouvre le modal de confirmation cascade', async () => {
    vi.mocked(deactivateAction).mockResolvedValue({
      status: 'requires_confirmation',
      affected_workflows: [{ id: 10, name: 'WF1', status: 'published' }],
    } as never);

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    await act(async () => {
      await result.current.handleDeactivate(MOCK_ACTIONS[0]);
    });

    expect(result.current.cascadeModalOpen).toBe(true);
    expect(result.current.cascadeWorkflows).toHaveLength(1);
    expect(result.current.cascadeAction).toEqual(MOCK_ACTIONS[0]);
  });

  it('handleReactivate succès — notifie succès et recharge les actions', async () => {
    vi.mocked(reactivateAction).mockResolvedValue({ id: 1, status: 'published' } as never);

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    await act(async () => {
      await result.current.handleReactivate(MOCK_ACTIONS[0]);
    });

    expect(MOCK_NOTIFICATION.success).toHaveBeenCalledOnce();
    expect(getAdminActions).toHaveBeenCalled();
  });

  it('openCreateAction — ouvre le modal en mode création action', () => {
    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    act(() => { result.current.openCreateAction(); });

    expect(result.current.modalOpen).toBe(true);
    expect(result.current.wizardInitialItemType).toBe('action');
    expect(result.current.editAction).toBeNull();
  });

  it('handleModalClose — ferme le modal et réinitialise le state', () => {
    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    act(() => { result.current.openCreateAction(); });
    expect(result.current.modalOpen).toBe(true);

    act(() => { result.current.handleModalClose(); });
    expect(result.current.modalOpen).toBe(false);
    expect(result.current.editAction).toBeNull();
    expect(result.current.submitError).toBeNull();
  });
});
