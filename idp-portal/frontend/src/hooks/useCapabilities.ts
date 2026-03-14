/**
 * useCapabilities — Story 82.6, AC2.
 *
 * Charge les capacités backend (plateformes, services, steps) en parallèle via Promise.all.
 * Cache module-level : une seule requête par session frontend.
 */
import { useState, useEffect } from 'react';
import {
  getIntegrationsCapabilities,
  getWorkflowStepsCapabilities,
} from '../services/capabilities_service';
import type { PlatformCapability, ServiceCapability, WorkflowStepCapability } from '../services/capabilities_service';

export interface CapabilitiesState {
  platforms: PlatformCapability[];
  services: ServiceCapability[];
  stepTypes: WorkflowStepCapability[];
}

// Cache module-level : une seule requête par session frontend
let _cache: CapabilitiesState | null = null;
let _pending: Promise<CapabilitiesState> | null = null;

/**
 * Réinitialise le cache module-level.
 * @internal — Réservé aux tests. Ne pas utiliser en production.
 */
export function _resetCapabilitiesCache(): void {
  _cache = null;
  _pending = null;
}

async function fetchCapabilities(): Promise<CapabilitiesState> {
  if (_cache) return _cache;
  if (_pending) return _pending;

  _pending = Promise.all([
    getIntegrationsCapabilities(),
    getWorkflowStepsCapabilities(),
  ]).then(([integrations, workflowSteps]) => {
    _cache = {
      platforms: integrations.platforms,
      services: integrations.services,
      stepTypes: workflowSteps.step_types,
    };
    _pending = null;
    return _cache;
  }).catch((err) => {
    _pending = null;
    throw err;
  });

  return _pending;
}

export function useCapabilities(): {
  capabilities: CapabilitiesState | null;
  loading: boolean;
  error: string | null;
} {
  const [capabilities, setCapabilities] = useState<CapabilitiesState | null>(_cache);
  const [loading, setLoading] = useState(!_cache);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (_cache) {
      setCapabilities(_cache);
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchCapabilities()
      .then((data) => {
        setCapabilities(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        setError((err as Error)?.message ?? 'Erreur chargement capacités');
        setLoading(false);
      });
  }, []);

  return { capabilities, loading, error };
}
