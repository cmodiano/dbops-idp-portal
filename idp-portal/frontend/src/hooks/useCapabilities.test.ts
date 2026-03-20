/**
 * Tests for useCapabilities — Story 82.6, AC7 (T7.3).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useCapabilities, _resetCapabilitiesCache } from './useCapabilities';
import * as capabilitiesService from '../services/capabilities_service';

vi.mock('../services/capabilities_service');

const mockGetIntegrations = vi.mocked(capabilitiesService.getIntegrationsCapabilities);
const mockGetWorkflowSteps = vi.mocked(capabilitiesService.getWorkflowStepsCapabilities);

const mockIntegrationsData = {
  platforms: [
    {
      code: 'aap',
      display_name: 'Ansible Automation Platform',
      aliases: ['tower'],
      icon: 'aap',
      connector_type: 'aap',
      action_platform_code: 'AAP',
      supports_health_check: true,
      action_config_schema: {},
    },
  ],
  services: [
    {
      code: 'servicenow',
      display_name: 'ServiceNow',
      credential_mode: 'integration' as const,
      operations: [{ code: 'create_change', label: 'Créer un changement', input_schema: {}, output_schema: {}, ui_hints: {} }],
      supports_health_check: false,
      supports_service_call: true,
    },
  ],
};

const mockWorkflowStepsData = {
  step_types: [
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

describe('useCapabilities', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    _resetCapabilitiesCache();
  });

  // Garantit la restauration des vrais timers après chaque test utilisant vi.useFakeTimers()
  afterEach(() => {
    vi.useRealTimers();
  });

  it('retourne loading=true initialement puis les données après fetch', async () => {
    mockGetIntegrations.mockResolvedValue(mockIntegrationsData);
    mockGetWorkflowSteps.mockResolvedValue(mockWorkflowStepsData);

    const { result } = renderHook(() => useCapabilities());

    expect(result.current.loading).toBe(true);
    expect(result.current.capabilities).toBeNull();

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.capabilities).not.toBeNull();
    expect(result.current.capabilities?.platforms).toHaveLength(1);
    expect(result.current.capabilities?.services).toHaveLength(1);
    expect(result.current.capabilities?.stepTypes).toHaveLength(1);
    expect(result.current.error).toBeNull();
    expect(result.current.retryCount).toBe(0);
  });

  it('charge les deux endpoints en parallèle (Promise.all)', async () => {
    mockGetIntegrations.mockResolvedValue(mockIntegrationsData);
    mockGetWorkflowSteps.mockResolvedValue(mockWorkflowStepsData);

    const { result } = renderHook(() => useCapabilities());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(mockGetIntegrations).toHaveBeenCalledTimes(1);
    expect(mockGetWorkflowSteps).toHaveBeenCalledTimes(1);
  });

  it('expose error et capabilities=null si le fetch échoue', async () => {
    // Story 88-2: fake timers pour éviter les délais réels de backoff (1s + 2s)
    vi.useFakeTimers();
    mockGetIntegrations.mockRejectedValue(new Error('API down'));
    mockGetWorkflowSteps.mockResolvedValue(mockWorkflowStepsData);

    const { result } = renderHook(() => useCapabilities());

    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(result.current.capabilities).toBeNull();
    // Story 88-2 Task 2.3: message enrichi indique le nombre de tentatives
    expect(result.current.error).toContain('API down');
    expect(result.current.retryCount).toBeGreaterThan(0);
  });

  it('partage le même fetch en cas de montage concurrent (pas de double requête)', async () => {
    mockGetIntegrations.mockResolvedValue(mockIntegrationsData);
    mockGetWorkflowSteps.mockResolvedValue(mockWorkflowStepsData);

    // Monter deux hooks simultanément AVANT la résolution
    const { result: resultA } = renderHook(() => useCapabilities());
    const { result: resultB } = renderHook(() => useCapabilities());

    // Les deux démarrent en loading
    expect(resultA.current.loading).toBe(true);
    expect(resultB.current.loading).toBe(true);

    // Attendre que les deux soient résolus
    await waitFor(() => expect(resultA.current.loading).toBe(false));
    await waitFor(() => expect(resultB.current.loading).toBe(false));

    // Un seul fetch effectué grâce au partage de la promise _pending
    expect(mockGetIntegrations).toHaveBeenCalledTimes(1);
    expect(resultA.current.capabilities?.platforms).toHaveLength(1);
    expect(resultB.current.capabilities?.platforms).toHaveLength(1);
  });

  it("utilise le cache si déjà chargé (cache hit — pas de second fetch)", async () => {
    mockGetIntegrations.mockResolvedValue(mockIntegrationsData);
    mockGetWorkflowSteps.mockResolvedValue(mockWorkflowStepsData);

    // Premier hook : charge les données
    const { result: result1 } = renderHook(() => useCapabilities());
    await waitFor(() => expect(result1.current.loading).toBe(false));
    expect(mockGetIntegrations).toHaveBeenCalledTimes(1);

    // Deuxième hook : doit utiliser le cache, pas refetch
    const { result: result2 } = renderHook(() => useCapabilities());
    await waitFor(() => expect(result2.current.loading).toBe(false));

    // Cache hit : toujours 1 seul appel API
    expect(mockGetIntegrations).toHaveBeenCalledTimes(1);
    expect(result2.current.capabilities?.platforms).toHaveLength(1);
  });

  // Story 88-2 ERR-FE-01: Retry tests — fake timers pour éviter les délais réels (1s/2s)
  it('2.4 — retry automatique après un premier échec réseau', async () => {
    vi.useFakeTimers();
    // First call fails, second succeeds
    mockGetIntegrations
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValue(mockIntegrationsData);
    mockGetWorkflowSteps
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValue(mockWorkflowStepsData);

    const { result } = renderHook(() => useCapabilities());

    expect(result.current.loading).toBe(true);

    // Avancer tous les timers (couvre le délai de backoff 1s du premier retry)
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.capabilities).not.toBeNull();
    expect(result.current.capabilities?.platforms).toHaveLength(1);
    expect(result.current.error).toBeNull();
    // Story 88-2 Task 2.3: retryCount = 1 après un retry réussi
    expect(result.current.retryCount).toBe(1);

    // First call + retry = 2 calls each
    expect(mockGetIntegrations).toHaveBeenCalledTimes(2);
    expect(mockGetWorkflowSteps).toHaveBeenCalledTimes(2);
  });

  it('2.5 — retry s\'arrête après le nombre max de tentatives (2)', async () => {
    vi.useFakeTimers();
    // All calls fail
    mockGetIntegrations.mockRejectedValue(new Error('Persistent network error'));
    mockGetWorkflowSteps.mockRejectedValue(new Error('Persistent network error'));

    const { result } = renderHook(() => useCapabilities());

    expect(result.current.loading).toBe(true);

    // Avancer tous les timers (couvre backoff 1s + 2s pour 2 retries)
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    // After MAX_RETRIES (2), should have error
    expect(result.current.loading).toBe(false);
    expect(result.current.capabilities).toBeNull();
    // Story 88-2 Task 2.3: message enrichi avec nombre de tentatives
    expect(result.current.error).toContain('Persistent network error');
    expect(result.current.error).toContain('3 tentatives');
    // Story 88-2 Task 2.3: retryCount = 2 après épuisement des retries
    expect(result.current.retryCount).toBe(2);

    // Initial + 2 retries = 3 calls
    expect(mockGetIntegrations).toHaveBeenCalledTimes(3);
  });
});
