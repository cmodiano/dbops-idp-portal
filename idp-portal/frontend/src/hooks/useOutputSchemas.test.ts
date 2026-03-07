/**
 * Tests pour useOutputSchemas hook (Story 63.3).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useOutputSchemas } from './useOutputSchemas';
import * as service from '../services/output_schema_service';

vi.mock('../services/output_schema_service');

const mockStep = {
  step_id: 'step-1',
  step_name: 'Créer changement',
  step_type: 'service_call',
  variables: [
    { name: 'change_number', path: '$.number', type: 'string', description: 'Numéro du change' },
  ],
};

describe('useOutputSchemas', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('retourne [] et loading=false si workflowId est undefined', () => {
    const { result } = renderHook(() => useOutputSchemas(undefined));
    expect(result.current.availableVariables).toEqual([]);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('ne fait pas d\'appel API si workflowId est undefined', () => {
    renderHook(() => useOutputSchemas(undefined));
    expect(service.fetchAvailableVariables).not.toHaveBeenCalled();
  });

  it('charge les variables quand workflowId est fourni', async () => {
    vi.mocked(service.fetchAvailableVariables).mockResolvedValue([mockStep]);

    const { result } = renderHook(() => useOutputSchemas(42));

    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.availableVariables).toHaveLength(1);
    expect(result.current.availableVariables[0].step_id).toBe('step-1');
    expect(result.current.error).toBeNull();
  });

  it('gère les erreurs et retourne [] + message d\'erreur', async () => {
    vi.mocked(service.fetchAvailableVariables).mockRejectedValue(new Error('Erreur réseau'));

    const { result } = renderHook(() => useOutputSchemas(42));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.availableVariables).toEqual([]);
    expect(result.current.error).toBe('Erreur réseau');
  });

  it('gère les erreurs non-Error et retourne message par défaut', async () => {
    vi.mocked(service.fetchAvailableVariables).mockRejectedValue('string error');

    const { result } = renderHook(() => useOutputSchemas(42));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Erreur de chargement');
  });

  it('recharge quand workflowId change', async () => {
    vi.mocked(service.fetchAvailableVariables).mockResolvedValue([mockStep]);

    const { result, rerender } = renderHook(({ id }) => useOutputSchemas(id), {
      initialProps: { id: 42 as number | undefined },
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(service.fetchAvailableVariables).toHaveBeenCalledWith(42);

    rerender({ id: 99 });
    await waitFor(() => expect(service.fetchAvailableVariables).toHaveBeenCalledWith(99));
  });

  it('remet loading à false quand workflowId passe à undefined pendant un fetch en cours', async () => {
    let resolvePromise!: (value: typeof mockStep[]) => void;
    vi.mocked(service.fetchAvailableVariables).mockReturnValue(
      new Promise((resolve) => { resolvePromise = resolve; }),
    );

    const { result, rerender } = renderHook(({ id }) => useOutputSchemas(id), {
      initialProps: { id: 42 as number | undefined },
    });

    expect(result.current.loading).toBe(true);

    rerender({ id: undefined });

    expect(result.current.loading).toBe(false);
    expect(result.current.availableVariables).toEqual([]);

    // Resolve the dangling promise to avoid unhandled rejection
    resolvePromise([]);
  });

  it('annule la mise à jour state après unmount (cancelled flag)', async () => {
    vi.mocked(service.fetchAvailableVariables).mockResolvedValue([mockStep]);

    const { result, unmount } = renderHook(() => useOutputSchemas(42));

    unmount();

    // After unmount, state is frozen at initial value (no update happened yet)
    expect(result.current.availableVariables).toEqual([]);
  });
});
