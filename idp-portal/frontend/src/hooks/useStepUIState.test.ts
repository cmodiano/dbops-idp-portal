/**
 * Tests for useStepUIState hook (Story 71.11, AC #3).
 */

import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useStepUIState } from './useStepUIState';
import type { ExecutionStepResponse } from '../types/api';

const mockSteps: ExecutionStepResponse[] = [
  { id: 1, step_id: 'step-a', name: 'Step A', status: 'SUCCESS', order: 1 } as any,
  { id: 2, step_id: 'step-b', name: 'Step B', status: 'RUNNING', order: 2 } as any,
];

describe('useStepUIState', () => {
  it('état initial : expandedId=null, logsDrawerStepId=null, logsDrawerStep=null', () => {
    const { result } = renderHook(() => useStepUIState(mockSteps));

    expect(result.current.expandedId).toBeNull();
    expect(result.current.logsDrawerStepId).toBeNull();
    expect(result.current.logsDrawerStep).toBeNull();
  });

  it('setExpandedId(id) met à jour expandedId', () => {
    const { result } = renderHook(() => useStepUIState(mockSteps));

    act(() => {
      result.current.setExpandedId(1);
    });

    expect(result.current.expandedId).toBe(1);
  });

  it('setLogsDrawerStepId(id) met à jour logsDrawerStepId', () => {
    const { result } = renderHook(() => useStepUIState(mockSteps));

    act(() => {
      result.current.setLogsDrawerStepId(2);
    });

    expect(result.current.logsDrawerStepId).toBe(2);
  });

  it('logsDrawerStep est dérivé des steps par logsDrawerStepId', () => {
    const { result } = renderHook(() => useStepUIState(mockSteps));

    act(() => {
      result.current.setLogsDrawerStepId(1);
    });

    expect(result.current.logsDrawerStep).toEqual(mockSteps[0]);
  });

  it('logsDrawerStep est null si id ne correspond à aucun step', () => {
    const { result } = renderHook(() => useStepUIState(mockSteps));

    act(() => {
      result.current.setLogsDrawerStepId(999);
    });

    expect(result.current.logsDrawerStep).toBeNull();
  });

  it('logsDrawerContentRef est un objet ref', () => {
    const { result } = renderHook(() => useStepUIState(mockSteps));

    expect(result.current.logsDrawerContentRef).toBeDefined();
    expect(typeof result.current.logsDrawerContentRef).toBe('object');
    expect('current' in result.current.logsDrawerContentRef).toBe(true);
  });
});
