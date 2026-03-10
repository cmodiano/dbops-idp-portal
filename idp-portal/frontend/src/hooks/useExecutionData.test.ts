/**
 * Tests for useExecutionData (Story 34.12 / Story 66-11 AC#3).
 *
 * Verifies:
 * - mode='historical' → données issues de executionProp/stepsProp
 * - mode='realtime' + executionId → useRealtime=true, WS actif
 * - WS indisponible (erreur) → fallback polling activé
 * - mode='historical' → WS non activé, pas de polling
 * - cleanup (WS + polling arrêtés) délégué aux sous-hooks
 * - Agrégation des données : WS prioritaire, polling en fallback
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useExecutionData } from './useExecutionData';
import type { ExecutionResponse, ExecutionStepResponse } from '../types/api';

// Mocks des sous-hooks
vi.mock('./useWebSocket', () => ({
  useWebSocket: vi.fn(),
}));

vi.mock('./useExecutionPolling', () => ({
  useExecutionPolling: vi.fn(),
}));

import { useWebSocket } from './useWebSocket';
import { useExecutionPolling } from './useExecutionPolling';

const mockUseWebSocket = vi.mocked(useWebSocket);
const mockUseExecutionPolling = vi.mocked(useExecutionPolling);

// ── Données de test ───────────────────────────────────────────────────────────

const mockExecution: ExecutionResponse = {
  id: 1,
  action_id: 10,
  action_name: 'Deploy',
  user_id: 5,
  environment: 'prod',
  parameters: null,
  status: 'RUNNING',
  servicenow_change_id: null,
  started_at: '2025-01-01T10:00:00Z',
  completed_at: null,
  created_at: '2025-01-01T09:59:00Z',
  item_type: 'action',
};

const mockStep: ExecutionStepResponse = {
  id: 1,
  execution_id: 1,
  step_order: 1,
  step_name: 'Step 1',
  step_type: 'platform',
  status: 'RUNNING',
  started_at: '2025-01-01T10:00:00Z',
  completed_at: null,
  output: null,
  platform_job_id: null,
  error_message: null,
};

// Résultat WS par défaut (pas d'erreur, chargement terminé)
const defaultWsResult = {
  steps: [mockStep],
  execution: mockExecution,
  loading: false,
  error: null,
  lastMessage: null,
  isAuthenticated: true,
};

// Résultat polling par défaut (pas actif)
const defaultPollingResult = {
  execution: null,
  steps: [],
  isPolling: false,
  error: null,
};

describe('useExecutionData', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseWebSocket.mockReturnValue(defaultWsResult);
    mockUseExecutionPolling.mockReturnValue(defaultPollingResult);
  });

  // ── Mode historique ──────────────────────────────────────────────────────────

  it('mode historique — retourne executionProp et stepsProp directement', () => {
    const { result } = renderHook(() =>
      useExecutionData({
        executionId: 1,
        executionProp: mockExecution,
        stepsProp: [mockStep],
        mode: 'historical',
      }),
    );

    expect(result.current.execution).toBe(mockExecution);
    expect(result.current.steps).toEqual([mockStep]);
    expect(result.current.useRealtime).toBe(false);
    expect(result.current.isPolling).toBe(false);
  });

  it('mode historique — useWebSocket appelé avec null (pas de connexion)', () => {
    renderHook(() =>
      useExecutionData({
        executionId: 1,
        executionProp: mockExecution,
        stepsProp: [mockStep],
        mode: 'historical',
      }),
    );

    expect(mockUseWebSocket).toHaveBeenCalledWith(null);
  });

  it('mode historique — useExecutionPolling appelé avec enabled=false', () => {
    renderHook(() =>
      useExecutionData({
        executionId: 1,
        executionProp: mockExecution,
        stepsProp: [mockStep],
        mode: 'historical',
      }),
    );

    expect(mockUseExecutionPolling).toHaveBeenCalledWith(
      expect.objectContaining({ enabled: false }),
    );
  });

  it('pas de stepsProp → retourne tableau vide en mode historique', () => {
    const { result } = renderHook(() =>
      useExecutionData({
        executionId: 1,
        executionProp: mockExecution,
        mode: 'historical',
      }),
    );

    expect(result.current.steps).toEqual([]);
  });

  // ── Mode temps réel — WS actif ───────────────────────────────────────────────

  it('mode realtime + executionId → useRealtime=true, données WS utilisées', () => {
    const { result } = renderHook(() =>
      useExecutionData({ executionId: 1, mode: 'realtime' }),
    );

    expect(result.current.useRealtime).toBe(true);
    expect(result.current.steps).toEqual([mockStep]);
    expect(result.current.execution).toBe(mockExecution);
    expect(result.current.isPolling).toBe(false);
  });

  it('mode realtime + executionId → useWebSocket appelé avec executionId', () => {
    renderHook(() =>
      useExecutionData({ executionId: 42, mode: 'realtime' }),
    );

    expect(mockUseWebSocket).toHaveBeenCalledWith(42);
  });

  it('mode realtime + executionId → lastMessage WS transmis', () => {
    const lastMessage = { type: 'step_update', data: {} };
    mockUseWebSocket.mockReturnValue({ ...defaultWsResult, lastMessage });

    const { result } = renderHook(() =>
      useExecutionData({ executionId: 1, mode: 'realtime' }),
    );

    expect(result.current.lastMessage).toBe(lastMessage);
  });

  it('mode realtime sans executionId → useRealtime=false', () => {
    const { result } = renderHook(() =>
      useExecutionData({ executionId: null, mode: 'realtime' }),
    );

    expect(result.current.useRealtime).toBe(false);
    expect(mockUseWebSocket).toHaveBeenCalledWith(null);
  });

  // ── Fallback polling sur erreur WS ──────────────────────────────────────────

  it('WS en erreur → polling activé (enabled=true)', () => {
    mockUseWebSocket.mockReturnValue({
      ...defaultWsResult,
      error: 'Connexion WebSocket échouée',
    });

    renderHook(() =>
      useExecutionData({ executionId: 1, mode: 'realtime' }),
    );

    expect(mockUseExecutionPolling).toHaveBeenCalledWith(
      expect.objectContaining({ enabled: true, executionId: 1 }),
    );
  });

  it('WS en erreur → données issues du polling', () => {
    const pollStep: ExecutionStepResponse = { ...mockStep, status: 'COMPLETED' };
    const pollExecution: ExecutionResponse = { ...mockExecution, status: 'COMPLETED' };

    mockUseWebSocket.mockReturnValue({
      ...defaultWsResult,
      steps: [],
      execution: null,
      error: 'Erreur WS',
    });
    mockUseExecutionPolling.mockReturnValue({
      execution: pollExecution,
      steps: [pollStep],
      isPolling: true,
      error: null,
    });

    const { result } = renderHook(() =>
      useExecutionData({ executionId: 1, mode: 'realtime' }),
    );

    expect(result.current.steps).toEqual([pollStep]);
    expect(result.current.execution).toBe(pollExecution);
    expect(result.current.isPolling).toBe(true);
  });

  it('WS OK (pas d\'erreur) → polling désactivé', () => {
    renderHook(() =>
      useExecutionData({ executionId: 1, mode: 'realtime' }),
    );

    expect(mockUseExecutionPolling).toHaveBeenCalledWith(
      expect.objectContaining({ enabled: false }),
    );
  });

  // ── Agrégation et priorité des sources ──────────────────────────────────────

  it('WS actif sans erreur → steps WS prioritaires sur stepsProp', () => {
    const wsStep: ExecutionStepResponse = { ...mockStep, step_name: 'WS Step' };
    const propStep: ExecutionStepResponse = { ...mockStep, step_name: 'Prop Step' };

    mockUseWebSocket.mockReturnValue({ ...defaultWsResult, steps: [wsStep] });

    const { result } = renderHook(() =>
      useExecutionData({
        executionId: 1,
        stepsProp: [propStep],
        mode: 'realtime',
      }),
    );

    expect(result.current.steps).toEqual([wsStep]);
  });

  it('loading=true pendant que WS charge', () => {
    mockUseWebSocket.mockReturnValue({ ...defaultWsResult, loading: true });

    const { result } = renderHook(() =>
      useExecutionData({ executionId: 1, mode: 'realtime' }),
    );

    expect(result.current.loading).toBe(true);
  });

  it('loading=false en mode historique (pas de WS)', () => {
    const { result } = renderHook(() =>
      useExecutionData({
        executionId: 1,
        executionProp: mockExecution,
        mode: 'historical',
      }),
    );

    expect(result.current.loading).toBe(false);
  });

  // ── Cleanup (délégation aux sous-hooks) ─────────────────────────────────────

  it('unmount — pas d\'erreur (cleanup délégué aux sous-hooks mockés)', () => {
    const { unmount } = renderHook(() =>
      useExecutionData({ executionId: 1, mode: 'realtime' }),
    );

    // Le hook délègue le cleanup à useWebSocket et useExecutionPolling
    // Les sous-hooks gèrent leur propre cycle de vie (testé séparément)
    expect(() => unmount()).not.toThrow();
  });
});
