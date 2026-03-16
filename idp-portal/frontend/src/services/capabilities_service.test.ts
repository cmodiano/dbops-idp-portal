/**
 * Tests for capabilities_service — Story 82.6, AC7 (T7.1, T7.2).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as apiClient from './api_client';
import {
  getIntegrationsCapabilities,
  getWorkflowStepsCapabilities,
  type CapabilitiesIntegrationsData,
  type CapabilitiesWorkflowStepsData,
} from './capabilities_service';

vi.mock('./api_client');

const mockApiFetch = vi.mocked(apiClient.apiFetch);

// ─── T7.1 : getIntegrationsCapabilities ────────────────────────────────────────

describe('getIntegrationsCapabilities', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('retourne platforms et services depuis la réponse API', async () => {
    const mockData: CapabilitiesIntegrationsData = {
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
          credential_mode: 'integration',
          operations: [{ code: 'create_change', label: 'Créer un changement', input_schema: {}, output_schema: {}, ui_hints: {} }, { code: 'update_change', label: 'Mettre à jour un changement', input_schema: {}, output_schema: {}, ui_hints: {} }],
          supports_health_check: false,
          supports_service_call: true,
        },
      ],
    };
    mockApiFetch.mockResolvedValue(mockData);

    const result = await getIntegrationsCapabilities();

    expect(mockApiFetch).toHaveBeenCalledWith('/capabilities/integrations/');
    expect(result.platforms).toHaveLength(1);
    expect(result.platforms[0].code).toBe('aap');
    expect(result.services).toHaveLength(1);
    expect(result.services[0].code).toBe('servicenow');
    expect(result.services[0].operations[0].code).toBe('create_change');
  });

  it("retourne des listes vides si l'API retourne null", async () => {
    mockApiFetch.mockResolvedValue(null);

    const result = await getIntegrationsCapabilities();

    expect(result).toEqual({ platforms: [], services: [] });
  });

  it("propage l'erreur si apiFetch échoue", async () => {
    mockApiFetch.mockRejectedValue(new Error('Network error'));

    await expect(getIntegrationsCapabilities()).rejects.toThrow('Network error');
  });
});

// ─── T7.2 : getWorkflowStepsCapabilities ───────────────────────────────────────

describe('getWorkflowStepsCapabilities', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('retourne step_types avec variants gate depuis la réponse API', async () => {
    const mockData: CapabilitiesWorkflowStepsData = {
      step_types: [
        { code: 'platform', label: 'Exécuter', category: 'execution', config_schema: {}, constraints: {} },
        { code: 'service_call', label: 'Service', category: 'integration', config_schema: {}, constraints: {} },
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
    mockApiFetch.mockResolvedValue(mockData);

    const result = await getWorkflowStepsCapabilities();

    expect(mockApiFetch).toHaveBeenCalledWith('/capabilities/workflow-steps/');
    expect(result.step_types).toHaveLength(3);
    const gateStep = result.step_types.find((s) => s.code === 'gate');
    expect(gateStep).toBeDefined();
    expect(gateStep?.variants).toHaveLength(2);
    expect(gateStep?.variants?.[0].code).toBe('maintenance_window');
    expect(gateStep?.variants?.[1].code).toBe('approval');
  });

  it("retourne step_types vide si l'API retourne null", async () => {
    mockApiFetch.mockResolvedValue(null);

    const result = await getWorkflowStepsCapabilities();

    expect(result).toEqual({ step_types: [] });
  });

  it("propage l'erreur si apiFetch échoue", async () => {
    mockApiFetch.mockRejectedValue(new Error('Network error'));

    await expect(getWorkflowStepsCapabilities()).rejects.toThrow('Network error');
  });
});
