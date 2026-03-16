/**
 * Tests for useWorkflowStepCapabilities — Story 83-12.
 * Résilience technique uniquement : pas de fallback métier local.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useWorkflowStepCapabilities } from './useWorkflowStepCapabilities';
import * as useCapabilitiesModule from './useCapabilities';

vi.mock('./useCapabilities');

const mockUseCapabilities = vi.mocked(useCapabilitiesModule.useCapabilities);

const mockCapabilities = {
  platforms: [],
  services: [],
  stepTypes: [
    { code: 'platform', label: 'Exécuter', category: 'execution', config_schema: {}, constraints: {} },
    {
      code: 'gate',
      label: 'Attendre',
      category: 'control',
      config_schema: {},
      constraints: {},
      variants: [
        { code: 'maintenance_window', label: 'Fenêtre de maintenance', config_schema: {} },
        { code: 'approval', label: 'Approbation manuelle', config_schema: {} },
      ],
    },
  ],
};

describe('useWorkflowStepCapabilities', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('extrait les variants gate depuis les capacités', () => {
    mockUseCapabilities.mockReturnValue({
      capabilities: mockCapabilities,
      loading: false,
      error: null,
    });

    const { result } = renderHook(() => useWorkflowStepCapabilities());

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.gateVariants).toHaveLength(2);
    expect(result.current.gateVariants[0].code).toBe('maintenance_window');
    expect(result.current.gateVariants[1].code).toBe('approval');
  });

  it('retourne gateVariants vide si API en erreur (résilience technique)', () => {
    mockUseCapabilities.mockReturnValue({
      capabilities: null,
      loading: false,
      error: 'API down',
    });

    const { result } = renderHook(() => useWorkflowStepCapabilities());

    expect(result.current.error).toBe('API down');
    expect(result.current.loading).toBe(false);
    // Résilience technique : pas de fallback métier, liste vide
    expect(result.current.gateVariants).toHaveLength(0);
  });

  it('retourne gateVariants=[] pendant le chargement', () => {
    mockUseCapabilities.mockReturnValue({
      capabilities: null,
      loading: true,
      error: null,
    });

    const { result } = renderHook(() => useWorkflowStepCapabilities());

    expect(result.current.loading).toBe(true);
    expect(result.current.gateVariants).toHaveLength(0);
  });

  it('retourne gateVariants vide si stepTypes est vide', () => {
    mockUseCapabilities.mockReturnValue({
      capabilities: {
        platforms: [],
        services: [],
        stepTypes: [], // API retourne une liste vide sans erreur
      },
      loading: false,
      error: null,
    });

    const { result } = renderHook(() => useWorkflowStepCapabilities());

    // Résilience technique : pas de fallback métier, liste vide
    expect(result.current.gateVariants).toHaveLength(0);
  });

  it("l'erreur prend priorité sur les données obsolètes (error + capabilities non-null)", () => {
    mockUseCapabilities.mockReturnValue({
      capabilities: mockCapabilities, // données périmées encore présentes
      loading: false,
      error: 'API error', // erreur simultanée (ex: refetch échoué avec stale data)
    });

    const { result } = renderHook(() => useWorkflowStepCapabilities());

    expect(result.current.error).toBe('API error');
    // error doit gagner sur les données obsolètes — pas de fallback métier
    expect(result.current.gateVariants).toHaveLength(0);
  });

  it("retourne gateVariants vide si le step gate n'a pas de variants", () => {
    mockUseCapabilities.mockReturnValue({
      capabilities: {
        platforms: [],
        services: [],
        stepTypes: [
          { code: 'gate', label: 'Attendre', category: 'control', config_schema: {}, constraints: {} },
          // pas de variants
        ],
      },
      loading: false,
      error: null,
    });

    const { result } = renderHook(() => useWorkflowStepCapabilities());

    // Résilience technique : pas de fallback métier, liste vide
    expect(result.current.gateVariants).toHaveLength(0);
  });
});
