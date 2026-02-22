/**
 * Centralized status mapping utilities (Story 34.2 — SOLID-FE-10).
 *
 * Previously duplicated in ExecutionTimeline.tsx and AuditPage.tsx.
 * Single source of truth for step and audit status display configuration.
 */

import type { ExecutionStepStatus } from '../types/api';

/** Color mapping for execution step statuses (migrated from ExecutionTimeline.tsx). */
export const STEP_STATUS_COLOR: Record<ExecutionStepStatus, string> = {
  PENDING: '#9CA3AF',
  RUNNING: '#3B82F6',
  COMPLETED: '#10B981',
  FAILED: '#EF4444',
  SKIPPED: '#9CA3AF',
};

/** Display config for audit execution statuses (migrated from AuditPage.tsx). */
export const AUDIT_STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  success: { color: 'success', label: 'Succès' },
  failed: { color: 'error', label: 'Échec' },
  running: { color: 'processing', label: 'En cours' },
  unknown: { color: 'default', label: 'Inconnu' },
};
