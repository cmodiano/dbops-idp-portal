/**
 * Tests unitaires pour useIntegrationValidation (Story 54.15, AC8).
 */

import { renderHook, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { useIntegrationValidation } from './useIntegrationValidation';
import { validateIntegration, validateAllIntegrations } from '../services/integrations_service';
import type { IntegrationValidationResponse } from '../types/api';

vi.mock('../services/integrations_service');

const mockValidationResponse = {
  integration_id: 1,
  integration_name: 'Test Integration',
  integration_type: 'oracle',
  current_status: 'valid' as const,
  validation_details: {
    status: 'valid' as const,
    type_exists: true,
    type_is_active: true,
    catalogue_version: null,
    validation_message: 'OK',
  },
};
const mockValidateAllResponse = { valid: 5, invalid: 1, deprecated: 0, updated: 2 };

describe('useIntegrationValidation', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('état initial — pas de validation en cours', () => {
    const { result } = renderHook(() => useIntegrationValidation());
    expect(result.current.validatingId).toBeNull();
    expect(result.current.validatingAll).toBe(false);
  });

  it('validateOne — succès : retourne le résultat et remet validatingId à null', async () => {
    vi.mocked(validateIntegration).mockResolvedValue(mockValidationResponse);

    const { result } = renderHook(() => useIntegrationValidation());

    let returned: IntegrationValidationResponse | undefined;
    await act(async () => {
      returned = await result.current.validateOne(1);
    });

    expect(validateIntegration).toHaveBeenCalledWith(1);
    expect(returned).toEqual(mockValidationResponse);
    expect(result.current.validatingId).toBeNull();
  });

  it('validateOne — état validatingId pendant la requête', async () => {
    let resolveValidate!: (v: typeof mockValidationResponse) => void;
    vi.mocked(validateIntegration).mockImplementation(
      () => new Promise((resolve) => { resolveValidate = resolve; })
    );

    const { result } = renderHook(() => useIntegrationValidation());

    act(() => { void result.current.validateOne(42); });
    expect(result.current.validatingId).toBe(42);

    await act(async () => { resolveValidate(mockValidationResponse); });
    expect(result.current.validatingId).toBeNull();
  });

  it('validateOne — erreur : remet validatingId à null et propage', async () => {
    vi.mocked(validateIntegration).mockRejectedValue(new Error('Validation échouée'));

    const { result } = renderHook(() => useIntegrationValidation());

    await expect(
      act(async () => { await result.current.validateOne(1); })
    ).rejects.toThrow('Validation échouée');

    expect(result.current.validatingId).toBeNull();
  });

  it('validateAll — succès : retourne le rapport et remet validatingAll à false', async () => {
    vi.mocked(validateAllIntegrations).mockResolvedValue(mockValidateAllResponse);

    const { result } = renderHook(() => useIntegrationValidation());

    let returned: typeof mockValidateAllResponse | undefined;
    await act(async () => {
      returned = await result.current.validateAll();
    });

    expect(validateAllIntegrations).toHaveBeenCalled();
    expect(returned).toEqual(mockValidateAllResponse);
    expect(result.current.validatingAll).toBe(false);
  });

  it('validateAll — état validatingAll pendant la requête', async () => {
    let resolveAll!: (v: typeof mockValidateAllResponse) => void;
    vi.mocked(validateAllIntegrations).mockImplementation(
      () => new Promise((resolve) => { resolveAll = resolve; })
    );

    const { result } = renderHook(() => useIntegrationValidation());

    act(() => { void result.current.validateAll(); });
    expect(result.current.validatingAll).toBe(true);

    await act(async () => { resolveAll(mockValidateAllResponse); });
    expect(result.current.validatingAll).toBe(false);
  });

  it('validateAll — erreur : remet validatingAll à false et propage', async () => {
    vi.mocked(validateAllIntegrations).mockRejectedValue(new Error('Batch échoué'));

    const { result } = renderHook(() => useIntegrationValidation());

    await expect(
      act(async () => { await result.current.validateAll(); })
    ).rejects.toThrow('Batch échoué');

    expect(result.current.validatingAll).toBe(false);
  });
});
