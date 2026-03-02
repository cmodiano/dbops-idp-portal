/**
 * Tests for useAuditFilters hook — coverage.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import React from 'react';
import { App } from 'antd';

vi.mock('../services/audit_service', () => ({
  listExecutionAudit: vi.fn(),
  exportAuditReport: vi.fn(),
}));
vi.mock('../services/catalog_service', () => ({
  fetchCatalogActions: vi.fn(),
}));
vi.mock('../services/execution_service', () => ({
  getExecution: vi.fn(),
  getExecutionSteps: vi.fn(),
}));
vi.mock('./useEngines', () => ({
  useEngines: () => ({ engineOptions: [], loading: false }),
}));

import { listExecutionAudit, exportAuditReport } from '../services/audit_service';
import { fetchCatalogActions } from '../services/catalog_service';
import { getExecution, getExecutionSteps } from '../services/execution_service';
import { useAuditFilters } from './useAuditFilters';

const mockListAudit = vi.mocked(listExecutionAudit);
const mockExport = vi.mocked(exportAuditReport);
const mockFetchActions = vi.mocked(fetchCatalogActions);
const mockGetExecution = vi.mocked(getExecution);
const mockGetSteps = vi.mocked(getExecutionSteps);

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(App, null, children);

const defaultAuditResponse = {
  data: [],
  pagination: { total: 0, page: 1, page_size: 50, total_pages: 1 },
};

describe('useAuditFilters — coverage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListAudit.mockResolvedValue(defaultAuditResponse);
    mockFetchActions.mockResolvedValue([]);
    mockExport.mockResolvedValue(undefined as never);
    mockGetExecution.mockResolvedValue({} as never);
    mockGetSteps.mockResolvedValue([]);
  });

  it('initial state: entries empty, loading=true initially', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.entries).toEqual([]);
    expect(result.current.error).toBeNull();
    expect(result.current.drawerOpen).toBe(false);
  });

  it('listExecutionAudit called on mount', async () => {
    renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(mockListAudit).toHaveBeenCalled());
  });

  it('error from listExecutionAudit sets error state', async () => {
    mockListAudit.mockRejectedValue(new Error('Network error'));
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe('Network error');
  });

  it('setDateRange updates filter', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => { result.current.setEnvironment('prod'); });
    expect(result.current.environment).toBe('prod');
  });

  it('setEngineType updates filter', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => { result.current.setEngineType('AAP'); });
    expect(result.current.engineType).toBe('AAP');
  });

  it('setActionId updates filter', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => { result.current.setActionId(42); });
    expect(result.current.actionId).toBe(42);
  });

  it('setStatus updates filter', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => { result.current.setStatus('COMPLETED' as never); });
    expect(result.current.status).toBe('COMPLETED');
  });

  it('setCorrelationId updates filter', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => { result.current.setCorrelationId('abc-123'); });
    expect(result.current.correlationId).toBe('abc-123');
  });

  it('setEntityType updates filter', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => { result.current.setEntityType('execution'); });
    expect(result.current.entityType).toBe('execution');
  });

  it('setActionType updates filter', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => { result.current.setActionType('deploy'); });
    expect(result.current.actionType).toBe('deploy');
  });

  it('setUserSearchInput updates userSearchInput', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => { result.current.setUserSearchInput('alice'); });
    expect(result.current.userSearchInput).toBe('alice');
  });

  it('handleRowClick with entity_type=execution loads execution + steps', async () => {
    mockGetExecution.mockResolvedValue({ id: 1, status: 'COMPLETED' } as never);
    mockGetSteps.mockResolvedValue([{ id: 10 }] as never);
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.handleRowClick({
        id: 1,
        entity_type: 'execution',
        entity_id: 1,
        timestamp: '',
        action_name: '',
        user: '',
        status: 'COMPLETED',
        parent_execution_id: null,
      } as never);
    });

    expect(result.current.drawerOpen).toBe(true);
    expect(mockGetExecution).toHaveBeenCalledWith(1);
    expect(mockGetSteps).toHaveBeenCalledWith(1);
  });

  it('handleRowClick with entity_type!=execution does not call getExecution', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.handleRowClick({
        id: 2,
        entity_type: 'schedule',
        entity_id: 5,
        timestamp: '',
        action_name: '',
        user: '',
        status: 'COMPLETED',
        parent_execution_id: null,
      } as never);
    });

    expect(result.current.drawerOpen).toBe(true);
    expect(mockGetExecution).not.toHaveBeenCalled();
  });

  it('handleRowClick error handling sets drawerError', async () => {
    mockGetExecution.mockRejectedValue(new Error('Not found'));
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.handleRowClick({
        id: 3,
        entity_type: 'execution',
        entity_id: 99,
        timestamp: '',
        action_name: '',
        user: '',
        status: 'FAILED',
        parent_execution_id: null,
      } as never);
    });

    expect(result.current.drawerError).toBe('Not found');
  });

  it('handleDrawerClose sets drawerOpen=false', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.handleRowClick({
        id: 1, entity_type: 'schedule', entity_id: 1,
        timestamp: '', action_name: '', user: '', status: 'COMPLETED', parent_execution_id: null,
      } as never);
    });
    act(() => { result.current.handleDrawerClose(); });
    expect(result.current.drawerOpen).toBe(false);
  });

  it('handleTableChange with page change updates currentPage', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      result.current.handleTableChange(
        { current: 2, pageSize: 50 },
        {},
        {},
        {} as never,
      );
    });
    expect(result.current.currentPage).toBe(2);
  });

  it('handleTableChange with sort change updates sortField and sortOrder', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      result.current.handleTableChange(
        { current: 1, pageSize: 50 },
        {},
        { field: 'entity', order: 'ascend' } as never,
        {} as never,
      );
    });
    expect(result.current.sortField).toBe('entity');
    expect(result.current.sortOrder).toBe('ascend');
  });

  it('handleTableChange without sort order resets to default', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      result.current.handleTableChange(
        { current: 1, pageSize: 50 },
        {},
        { field: 'entity', order: undefined } as never,
        {} as never,
      );
    });
    expect(result.current.sortField).toBe('timestamp');
    expect(result.current.sortOrder).toBe('descend');
  });

  it('handleExport csv calls exportAuditReport', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.handleExport('csv');
    });
    expect(mockExport).toHaveBeenCalledWith('csv', expect.any(Object));
  });

  it('handleExport pdf calls exportAuditReport', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.handleExport('pdf');
    });
    expect(mockExport).toHaveBeenCalledWith('pdf', expect.any(Object));
  });

  it('handleExport error sets exporting=false', async () => {
    mockExport.mockRejectedValue(new Error('Export failed'));
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.handleExport('csv');
    });
    expect(result.current.exporting).toBe(false);
  });

  it('getApiSortField: entity -> entity_type in sort param', async () => {
    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      result.current.handleTableChange(
        { current: 1, pageSize: 50 },
        {},
        { field: 'entity', order: 'ascend' } as never,
        {} as never,
      );
    });
    await waitFor(() => expect(mockListAudit).toHaveBeenCalled());
    const lastCall = mockListAudit.mock.calls[mockListAudit.mock.calls.length - 1]?.[0];
    expect(lastCall?.sort).toBe('entity_type');
  });

  it('topLevelEntries and childrenByParentId grouping', async () => {
    const parent = { id: 1, entity_type: 'execution', entity_id: 1, timestamp: '', action_name: '', user: '', status: 'COMPLETED', parent_execution_id: null };
    const child = { id: 2, entity_type: 'execution', entity_id: 2, timestamp: '', action_name: '', user: '', status: 'COMPLETED', parent_execution_id: 1 };
    mockListAudit.mockResolvedValue({ data: [parent, child] as never, pagination: { total: 2, page: 1, page_size: 50, total_pages: 1 } });

    const { result } = renderHook(() => useAuditFilters(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.topLevelEntries).toHaveLength(1);
    expect(result.current.topLevelEntries[0].id).toBe(1);
    expect(result.current.childrenByParentId.get(1)).toHaveLength(1);
  });
});
