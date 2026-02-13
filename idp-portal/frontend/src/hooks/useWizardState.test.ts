import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useWizardState } from './useWizardState';

describe('useWizardState', () => {
  it('starts at step 0 with initial data', () => {
    const { result } = renderHook(() => useWizardState());
    expect(result.current.currentStep).toBe(0);
    expect(result.current.stepData.selectedTargets).toEqual([]);
    expect(result.current.stepData.targetInputMode).toBe('list');
    expect(result.current.stepData.selectedEnvironment).toBeNull();
    expect(result.current.stepData.parameters).toEqual({});
    expect(result.current.canProceed).toBe(false);
  });

  it('navigates forward with next()', () => {
    const { result } = renderHook(() => useWizardState());
    act(() => result.current.next());
    expect(result.current.currentStep).toBe(1);
    act(() => result.current.next());
    expect(result.current.currentStep).toBe(2);
  });

  it('does not exceed total steps', () => {
    const { result } = renderHook(() => useWizardState({ totalSteps: 3 }));
    act(() => result.current.next());
    act(() => result.current.next());
    act(() => result.current.next());
    expect(result.current.currentStep).toBe(2);
  });

  it('navigates backward with prev()', () => {
    const { result } = renderHook(() => useWizardState());
    act(() => result.current.next());
    act(() => result.current.next());
    act(() => result.current.prev());
    expect(result.current.currentStep).toBe(1);
  });

  it('does not go below step 0', () => {
    const { result } = renderHook(() => useWizardState());
    act(() => result.current.prev());
    expect(result.current.currentStep).toBe(0);
  });

  it('goToStep jumps to valid step', () => {
    const { result } = renderHook(() => useWizardState());
    act(() => result.current.goToStep(2));
    expect(result.current.currentStep).toBe(2);
  });

  it('goToStep ignores invalid step numbers', () => {
    const { result } = renderHook(() => useWizardState());
    act(() => result.current.goToStep(-1));
    expect(result.current.currentStep).toBe(0);
    act(() => result.current.goToStep(5));
    expect(result.current.currentStep).toBe(0);
  });

  it('updates step data partially', () => {
    const { result } = renderHook(() => useWizardState());
    act(() => result.current.updateStepData({ selectedEnvironment: 'dev' }));
    expect(result.current.stepData.selectedEnvironment).toBe('dev');
    expect(result.current.stepData.targetInputMode).toBe('list');
  });

  it('preserves existing data on partial updates', () => {
    const { result } = renderHook(() => useWizardState());
    act(() => result.current.updateStepData({ parameters: { foo: 'bar' } }));
    act(() => result.current.updateStepData({ selectedEnvironment: 'prod' }));
    expect(result.current.stepData.parameters).toEqual({ foo: 'bar' });
    expect(result.current.stepData.selectedEnvironment).toBe('prod');
  });

  it('reset() returns to initial state', () => {
    const { result } = renderHook(() => useWizardState());
    act(() => {
      result.current.next();
      result.current.updateStepData({ selectedEnvironment: 'prod', parameters: { x: 1 } });
      result.current.setCanProceed(true);
    });
    act(() => result.current.reset());
    expect(result.current.currentStep).toBe(0);
    expect(result.current.stepData.selectedEnvironment).toBeNull();
    expect(result.current.stepData.parameters).toEqual({});
    expect(result.current.canProceed).toBe(false);
  });

  it('setCanProceed toggles canProceed flag', () => {
    const { result } = renderHook(() => useWizardState());
    act(() => result.current.setCanProceed(true));
    expect(result.current.canProceed).toBe(true);
    act(() => result.current.setCanProceed(false));
    expect(result.current.canProceed).toBe(false);
  });

  it('respects custom totalSteps', () => {
    const { result } = renderHook(() => useWizardState({ totalSteps: 5 }));
    act(() => {
      result.current.next();
      result.current.next();
      result.current.next();
      result.current.next();
    });
    expect(result.current.currentStep).toBe(4);
    act(() => result.current.next());
    expect(result.current.currentStep).toBe(4); // capped at totalSteps - 1
  });
});
