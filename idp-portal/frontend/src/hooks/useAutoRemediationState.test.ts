/**
 * Tests for useAutoRemediationState (Story 34.12 / Story 66-11 AC#2).
 *
 * Verifies:
 * - État initial (aucune suggestion active)
 * - Transition auto_remediation_started → state mis à jour
 * - Transition auto_remediation_failed → state mis à jour
 * - Cleanup / reset sur changement de executionId
 * - Ignorance des messages non reconnus
 * - lastMessage null → pas de changement d'état
 */

import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAutoRemediationState } from './useAutoRemediationState';

type LastMessage = { type: string; data?: unknown } | null | undefined;

describe('useAutoRemediationState', () => {
  it('état initial — aucune remédiation en cours', () => {
    const { result } = renderHook(() =>
      useAutoRemediationState(null, 42),
    );

    expect(result.current.inProgress).toBe(false);
    expect(result.current.failed).toBe(false);
    expect(result.current.childExecutionId).toBeNull();
    expect(result.current.correctiveActionName).toBeNull();
    expect(result.current.failureMessage).toBeNull();
  });

  it('auto_remediation_started → inProgress=true, données correctes', () => {
    const { result, rerender } = renderHook(
      ({ msg }: { msg: LastMessage }) => useAutoRemediationState(msg, 1),
      { initialProps: { msg: null as LastMessage } },
    );

    act(() => {
      rerender({
        msg: {
          type: 'auto_remediation_started',
          data: { child_execution_id: 99, corrective_action_name: 'Fix-Server' },
        },
      });
    });

    expect(result.current.inProgress).toBe(true);
    expect(result.current.failed).toBe(false);
    expect(result.current.childExecutionId).toBe(99);
    expect(result.current.correctiveActionName).toBe('Fix-Server');
    expect(result.current.failureMessage).toBeNull();
  });

  it('auto_remediation_started sans données → valeurs nulles par défaut', () => {
    const { result, rerender } = renderHook(
      ({ msg }: { msg: LastMessage }) => useAutoRemediationState(msg, 1),
      { initialProps: { msg: null as LastMessage } },
    );

    act(() => {
      rerender({ msg: { type: 'auto_remediation_started' } });
    });

    expect(result.current.inProgress).toBe(true);
    expect(result.current.childExecutionId).toBeNull();
    expect(result.current.correctiveActionName).toBeNull();
  });

  it('auto_remediation_failed → failed=true, inProgress=false', () => {
    const { result, rerender } = renderHook(
      ({ msg }: { msg: LastMessage }) => useAutoRemediationState(msg, 1),
      { initialProps: { msg: null as LastMessage } },
    );

    // D'abord démarrer
    act(() => {
      rerender({
        msg: {
          type: 'auto_remediation_started',
          data: { child_execution_id: 55, corrective_action_name: 'Rollback' },
        },
      });
    });

    expect(result.current.inProgress).toBe(true);

    // Puis échouer
    act(() => {
      rerender({
        msg: {
          type: 'auto_remediation_failed',
          data: { child_execution_id: 55, message: 'Rollback impossible' },
        },
      });
    });

    expect(result.current.inProgress).toBe(false);
    expect(result.current.failed).toBe(true);
    expect(result.current.childExecutionId).toBe(55);
    expect(result.current.failureMessage).toBe('Rollback impossible');
  });

  it('auto_remediation_failed — message par défaut si absent', () => {
    const { result, rerender } = renderHook(
      ({ msg }: { msg: LastMessage }) => useAutoRemediationState(msg, 1),
      { initialProps: { msg: null as LastMessage } },
    );

    act(() => {
      rerender({ msg: { type: 'auto_remediation_failed' } });
    });

    expect(result.current.failureMessage).toBe(
      'Tentative de correction automatique échouée',
    );
  });

  it('auto_remediation_failed préserve childExecutionId existant si absent du message', () => {
    const { result, rerender } = renderHook(
      ({ msg }: { msg: LastMessage }) => useAutoRemediationState(msg, 1),
      { initialProps: { msg: null as LastMessage } },
    );

    act(() => {
      rerender({
        msg: {
          type: 'auto_remediation_started',
          data: { child_execution_id: 77 },
        },
      });
    });

    act(() => {
      rerender({ msg: { type: 'auto_remediation_failed', data: {} } });
    });

    expect(result.current.childExecutionId).toBe(77);
  });

  it('message non reconnu → état inchangé', () => {
    const { result, rerender } = renderHook(
      ({ msg }: { msg: LastMessage }) => useAutoRemediationState(msg, 1),
      { initialProps: { msg: null as LastMessage } },
    );

    act(() => {
      rerender({ msg: { type: 'step_update', data: {} } });
    });

    expect(result.current.inProgress).toBe(false);
    expect(result.current.failed).toBe(false);
  });

  it('lastMessage null → état inchangé', () => {
    const { result, rerender } = renderHook(
      ({ msg }: { msg: LastMessage }) => useAutoRemediationState(msg, 1),
      { initialProps: { msg: null as LastMessage } },
    );

    act(() => {
      rerender({
        msg: {
          type: 'auto_remediation_started',
          data: { child_execution_id: 10 },
        },
      });
    });

    act(() => {
      rerender({ msg: null });
    });

    // lastMessage null ne déclenche pas de changement d'état — l'état reste tel quel
    expect(result.current.inProgress).toBe(true);
  });

  it('changement de executionId → reset de l\'état', () => {
    const { result, rerender } = renderHook(
      ({ msg, execId }: { msg: LastMessage; execId: number }) =>
        useAutoRemediationState(msg, execId),
      { initialProps: { msg: null as LastMessage, execId: 1 } },
    );

    // Déclencher une remédiation sur l'exécution 1
    act(() => {
      rerender({
        msg: {
          type: 'auto_remediation_started',
          data: { child_execution_id: 10 },
        },
        execId: 1,
      });
    });

    expect(result.current.inProgress).toBe(true);

    // Changer d'exécution → reset
    act(() => {
      rerender({ msg: null, execId: 2 });
    });

    expect(result.current.inProgress).toBe(false);
    expect(result.current.failed).toBe(false);
    expect(result.current.childExecutionId).toBeNull();
    expect(result.current.correctiveActionName).toBeNull();
    expect(result.current.failureMessage).toBeNull();
  });

  it('executionId undefined → pas de reset inattendu sur premier rendu', () => {
    const { result } = renderHook(() =>
      useAutoRemediationState(null, undefined),
    );

    expect(result.current.inProgress).toBe(false);
  });

  it('message malformé — data est une chaîne → valeurs nulles par défaut (robustesse)', () => {
    const { result, rerender } = renderHook(
      ({ msg }: { msg: LastMessage }) => useAutoRemediationState(msg, 1),
      { initialProps: { msg: null as LastMessage } },
    );

    act(() => {
      // data est une chaîne au lieu d'un objet — test de robustesse
      rerender({
        msg: { type: 'auto_remediation_started', data: 'unexpected-string' as unknown },
      });
    });

    // Le hook doit survivre sans planter et retourner des valeurs par défaut
    expect(result.current.inProgress).toBe(true);
    expect(result.current.childExecutionId).toBeNull();
    expect(result.current.correctiveActionName).toBeNull();
  });

  it('message malformé — data est un tableau → valeurs nulles par défaut (robustesse)', () => {
    const { result, rerender } = renderHook(
      ({ msg }: { msg: LastMessage }) => useAutoRemediationState(msg, 1),
      { initialProps: { msg: null as LastMessage } },
    );

    act(() => {
      rerender({
        msg: { type: 'auto_remediation_failed', data: [1, 2, 3] as unknown },
      });
    });

    expect(result.current.failed).toBe(true);
    expect(result.current.childExecutionId).toBeNull();
    expect(result.current.failureMessage).toBe('Tentative de correction automatique échouée');
  });
});
