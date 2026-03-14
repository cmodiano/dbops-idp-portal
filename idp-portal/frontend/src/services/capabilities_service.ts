/**
 * Capabilities service — Story 82.6, AC1.
 *
 * Expose les capacités backend (plateformes, services, steps workflow) via les endpoints :
 *   GET /api/v1/capabilities/integrations/
 *   GET /api/v1/capabilities/workflow-steps/
 */

import { apiFetch } from './api_client';

// ─── Interfaces ────────────────────────────────────────────────────────────────

export interface PlatformCapability {
  code: string;
  display_name: string;
  aliases: string[];
  icon: string;
  connector_type: string;
  action_platform_code: string;
  supports_health_check: boolean;
}

export interface ServiceCapability {
  code: string;
  display_name: string;
  credential_mode: 'integration' | 'credential_free';
  operations: string[];
  supports_health_check: boolean;
}

export interface GateVariant {
  code: string;
  label: string;
  config_schema: Record<string, unknown>;
}

export interface WorkflowStepCapability {
  code: string;
  label: string;
  category: string;
  config_schema: Record<string, unknown>;
  variants?: GateVariant[];
}

export interface CapabilitiesIntegrationsData {
  platforms: PlatformCapability[];
  services: ServiceCapability[];
}

export interface CapabilitiesWorkflowStepsData {
  step_types: WorkflowStepCapability[];
}

// ─── Functions ─────────────────────────────────────────────────────────────────

/**
 * Fetch integration capabilities (platforms + services).
 * apiFetch already unwraps body.data, so we receive CapabilitiesIntegrationsData directly.
 */
export async function getIntegrationsCapabilities(): Promise<CapabilitiesIntegrationsData> {
  const res = await apiFetch<CapabilitiesIntegrationsData>('/capabilities/integrations/');
  return res ?? { platforms: [], services: [] };
}

/**
 * Fetch workflow step capabilities (step_types with gate variants).
 * apiFetch already unwraps body.data, so we receive CapabilitiesWorkflowStepsData directly.
 */
export async function getWorkflowStepsCapabilities(): Promise<CapabilitiesWorkflowStepsData> {
  const res = await apiFetch<CapabilitiesWorkflowStepsData>('/capabilities/workflow-steps/');
  return res ?? { step_types: [] };
}
