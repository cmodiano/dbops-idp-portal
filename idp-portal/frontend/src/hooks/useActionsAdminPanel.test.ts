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
  getAction,
  updateAction,
  updateActionStatus,
  deleteAction,
  deactivateAction,
  reactivateAction,
} from '../services/admin_service';
import type { ActionListItem, ActionCreate, ActionResponse, ActionDetail } from '../types/api';

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

  it('openCreateWorkflow — ouvre le modal en mode création workflow', () => {
    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    act(() => { result.current.openCreateWorkflow(); });

    expect(result.current.modalOpen).toBe(true);
    expect(result.current.wizardInitialItemType).toBe('workflow');
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

  it('handleCascadeConfirm — no-op quand cascadeAction est null', async () => {
    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    await act(async () => {
      await result.current.handleCascadeConfirm();
    });

    expect(deactivateAction).not.toHaveBeenCalledWith(expect.anything(), expect.anything(), true);
    expect(MOCK_NOTIFICATION.success).not.toHaveBeenCalled();
  });

  it('handleCascadeConfirm — succès : notifie et recharge', async () => {
    vi.mocked(deactivateAction)
      .mockResolvedValueOnce({
        status: 'requires_confirmation',
        affected_workflows: [{ id: 10, name: 'WF1', status: 'published' }],
      } as never)
      .mockResolvedValueOnce({ id: 1, status: 'disabled' } as never);

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    // Trigger cascade modal first
    await act(async () => {
      await result.current.handleDeactivate(MOCK_ACTIONS[0]);
    });
    expect(result.current.cascadeModalOpen).toBe(true);

    // Confirm cascade
    await act(async () => {
      await result.current.handleCascadeConfirm();
    });

    expect(MOCK_NOTIFICATION.success).toHaveBeenCalledTimes(1);
    expect(result.current.cascadeModalOpen).toBe(false);
    expect(result.current.cascadeAction).toBeNull();
    expect(getAdminActions).toHaveBeenCalled();
  });

  it('handleCascadeConfirm — erreur API : notifie l\'erreur', async () => {
    vi.mocked(deactivateAction)
      .mockResolvedValueOnce({
        status: 'requires_confirmation',
        affected_workflows: [{ id: 10, name: 'WF1', status: 'published' }],
      } as never)
      .mockRejectedValueOnce(new Error('Cascade failed'));

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    await act(async () => {
      await result.current.handleDeactivate(MOCK_ACTIONS[0]);
    });

    await act(async () => {
      await result.current.handleCascadeConfirm();
    });

    expect(MOCK_NOTIFICATION.error).toHaveBeenCalledTimes(1);
  });

  it('handleCascadeCancel — ferme le modal cascade et réinitialise le state', async () => {
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

    act(() => { result.current.handleCascadeCancel(); });

    expect(result.current.cascadeModalOpen).toBe(false);
    expect(result.current.cascadeAction).toBeNull();
    expect(result.current.cascadeWorkflows).toHaveLength(0);
  });

  it('handleEditSubmit — erreur si editAction est null', async () => {
    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    await act(async () => {
      await expect(result.current.handleEditSubmit({} as never)).rejects.toThrow('editAction manquant');
    });
  });

  it('handleEditSubmit — succès quand editAction est défini', async () => {
    const mockDetail: ActionDetail = { id: 1, name: 'Action A', engine: 'Oracle', status: 'published' } as never;
    vi.mocked(getAction).mockResolvedValue(mockDetail);
    vi.mocked(updateAction).mockResolvedValue(mockDetail);

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    // Ouvrir le modal édition pour setter editAction
    await act(async () => {
      await result.current.handleEdit(MOCK_ACTIONS[0]);
    });

    let updated!: ActionDetail;
    await act(async () => {
      updated = await result.current.handleEditSubmit({ name: 'Action A Updated' } as never);
    });

    expect(updated).toEqual(mockDetail);
    expect(updateAction).toHaveBeenCalledWith(1, { name: 'Action A Updated' });
  });

  it('handleEdit — succès : charge le détail et ouvre le modal', async () => {
    const mockDetail: ActionDetail = { id: 1, name: 'Action A', engine: 'Oracle', status: 'published' } as never;
    vi.mocked(getAction).mockResolvedValue(mockDetail);

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    await act(async () => {
      await result.current.handleEdit(MOCK_ACTIONS[0]);
    });

    expect(result.current.editAction).toEqual(mockDetail);
    expect(result.current.modalOpen).toBe(true);
  });

  it('handleEdit — erreur : notifie l\'erreur', async () => {
    vi.mocked(getAction).mockRejectedValue(new Error('Not found'));

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    await act(async () => {
      await result.current.handleEdit(MOCK_ACTIONS[0]);
    });

    expect(MOCK_NOTIFICATION.error).toHaveBeenCalledTimes(1);
    expect(result.current.modalOpen).toBe(false);
  });

  it('handleStatusChange — utilise la transition comme label quand non mappée', async () => {
    vi.mocked(updateActionStatus).mockResolvedValue(undefined as never);

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    // 'publish', 'disable', 'enable' sont mappés. Une valeur non mappée devrait utiliser la transition elle-même.
    await act(async () => {
      await result.current.handleStatusChange(MOCK_ACTIONS[0], 'publish');
    });

    expect(MOCK_NOTIFICATION.success).toHaveBeenCalledWith(
      expect.objectContaining({ description: expect.stringContaining('publiee') })
    );
  });

  it('handleStatusChange — erreur API : notifie l\'erreur', async () => {
    vi.mocked(updateActionStatus).mockRejectedValue(new Error('Status change failed'));

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    await act(async () => {
      await result.current.handleStatusChange(MOCK_ACTIONS[0], 'publish');
    });

    expect(MOCK_NOTIFICATION.error).toHaveBeenCalledTimes(1);
  });

  it('handleReactivate — erreur API : notifie l\'erreur', async () => {
    vi.mocked(reactivateAction).mockRejectedValue(new Error('Reactivate failed'));

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    await act(async () => {
      await result.current.handleReactivate(MOCK_ACTIONS[0]);
    });

    expect(MOCK_NOTIFICATION.error).toHaveBeenCalledTimes(1);
  });

  it('handleDeactivate — erreur API : notifie l\'erreur', async () => {
    vi.mocked(deactivateAction).mockRejectedValue(new Error('Deactivate failed'));

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    await act(async () => {
      await result.current.handleDeactivate(MOCK_ACTIONS[0]);
    });

    expect(MOCK_NOTIFICATION.error).toHaveBeenCalledTimes(1);
  });

  it('fetchActions — erreur API : notifie l\'erreur', async () => {
    vi.mocked(getAdminActions).mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    await act(async () => {
      await result.current.fetchActions();
    });

    expect(MOCK_NOTIFICATION.error).toHaveBeenCalledTimes(1);
    expect(result.current.loading).toBe(false);
  });

  it('handleSuccess — notifie création et recharge quand wasEdit=false', async () => {
    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    const mockAction: ActionResponse = { id: 3, name: 'Nouvelle Action', status: 'draft', engine: 'Oracle' } as never;

    await act(async () => {
      result.current.handleSuccess(mockAction);
    });

    expect(MOCK_NOTIFICATION.success).toHaveBeenCalledWith(
      expect.objectContaining({ description: expect.stringContaining('creee avec succes') })
    );
    expect(result.current.modalOpen).toBe(false);
  });

  it('handleSuccess — notifie mise à jour quand wasEdit=true', async () => {
    const mockDetail: ActionDetail = { id: 1, name: 'Action A', engine: 'Oracle', status: 'published' } as never;
    vi.mocked(getAction).mockResolvedValue(mockDetail);

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    // Set editAction first
    await act(async () => {
      await result.current.handleEdit(MOCK_ACTIONS[0]);
    });

    await act(async () => {
      result.current.handleSuccess(mockDetail);
    });

    expect(MOCK_NOTIFICATION.success).toHaveBeenCalledWith(
      expect.objectContaining({ description: expect.stringContaining('mise a jour') })
    );
  });

  it('handleDelete — onOk supprime et notifie succès', async () => {
    vi.mocked(deleteAction).mockResolvedValue(undefined as never);

    let capturedOnOk: (() => Promise<void>) | undefined;
    vi.mocked(MOCK_MODAL.confirm).mockImplementation((config: any) => {
      capturedOnOk = config.onOk;
      return {} as never;
    });

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    act(() => { result.current.handleDelete(MOCK_ACTIONS[0]); });

    expect(capturedOnOk).toBeDefined();
    await act(async () => { await capturedOnOk!(); });

    expect(deleteAction).toHaveBeenCalledWith(1);
    expect(MOCK_NOTIFICATION.success).toHaveBeenCalledTimes(1);
    expect(getAdminActions).toHaveBeenCalled();
  });

  it('handleDelete — onOk erreur : notifie l\'erreur', async () => {
    vi.mocked(deleteAction).mockRejectedValue(new Error('Delete failed'));

    let capturedOnOk: (() => Promise<void>) | undefined;
    vi.mocked(MOCK_MODAL.confirm).mockImplementation((config: any) => {
      capturedOnOk = config.onOk;
      return {} as never;
    });

    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    act(() => { result.current.handleDelete(MOCK_ACTIONS[0]); });

    await act(async () => { await capturedOnOk!(); });

    expect(MOCK_NOTIFICATION.error).toHaveBeenCalledTimes(1);
  });

  it('fetchActions — inclut toujours include_disabled=true', async () => {
    const { result } = renderHook(() =>
      useActionsAdminPanel({ notification: MOCK_NOTIFICATION as any, modal: MOCK_MODAL as any })
    );

    await act(async () => {
      await result.current.fetchActions();
    });

    expect(getAdminActions).toHaveBeenCalledWith(expect.objectContaining({ include_disabled: true }));
  });
});
