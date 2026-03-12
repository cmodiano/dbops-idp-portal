/**
 * Centralized status mapping utilities (Story 34.2 — SOLID-FE-10, Story 35.1 — consolidation).
 *
 * Previously duplicated in ExecutionTimeline.tsx and AuditPage.tsx.
 * Single source of truth for step and audit status display configuration.
 *
 * Story 35.1: Added EXECUTION_STATUS_BADGE_CONFIG and STEP_STATUS_BADGE_CONFIG
 * to replace local STATUS_CONFIG in ExecutionView.tsx and StepDetailDrawer.tsx.
 */

import type { ExecutionStepStatus, ExecutionStatusType } from '../types/api';

/** Ant Design Badge status type. */
export type BadgeStatusType = 'success' | 'error' | 'warning' | 'processing' | 'default';

/** Color mapping for execution step statuses (migrated from ExecutionTimeline.tsx). */
export const STEP_STATUS_COLOR: Record<ExecutionStepStatus, string> = {
  PENDING: '#9CA3AF',
  RUNNING: '#3B82F6',
  COMPLETED: '#10B981',
  FAILED: '#EF4444',
  SKIPPED: '#9CA3AF',
  WAITING: '#FA8C16', // Story 58.3: orange — en attente d'approbation (gate)
};

/**
 * Badge display config for execution statuses (Story 35.1 — migrated from ExecutionView.tsx).
 * Maps ExecutionStatusType → Ant Design Badge color + French label.
 *
 * Labels intentionally use masculine form ("Soumis", "Terminé") to match ExecutionView.tsx UX.
 * Note: executionRenderers.tsx uses feminine labels ("Soumise", "Terminée") for inline renderers —
 * this divergence is deliberate (ExecutionView shows "Exécution: Soumis", renderers show standalone status).
 * PENDING_APPROVAL uses "En attente approbation" (more precise than "En attente" in executionRenderers).
 */
export const EXECUTION_STATUS_BADGE_CONFIG: Record<ExecutionStatusType, { color: BadgeStatusType; label: string }> = {
  SUBMITTED: { color: 'default', label: 'Soumis' },
  RUNNING: { color: 'processing', label: 'En cours' },
  COMPLETED: { color: 'success', label: 'Terminé' },
  FAILED: { color: 'error', label: 'Échoué' },
  CANCELLED: { color: 'default', label: 'Annulé' },
  INTEGRATION_ERROR: { color: 'error', label: 'Erreur intégration' },
  PENDING_APPROVAL: { color: 'warning', label: 'En attente approbation' },
  REJECTED: { color: 'error', label: 'Rejeté' },
};

/**
 * Badge display config for workflow step statuses (Story 35.1 — migrated from StepDetailDrawer.tsx).
 * Maps ExecutionStepStatus → Ant Design Badge color + French label.
 *
 * Includes CANCELLED defensively: ExecutionStepStatus type only covers 5 states but the backend
 * may return CANCELLED for steps in cancelled executions. The union `ExecutionStepStatus | 'CANCELLED'`
 * ensures correct display without requiring a type update that could affect other consumers.
 */
export const STEP_STATUS_BADGE_CONFIG: Record<ExecutionStepStatus | 'CANCELLED', { color: BadgeStatusType; label: string }> = {
  PENDING: { color: 'default', label: 'En attente' },
  RUNNING: { color: 'processing', label: 'En cours' },
  COMPLETED: { color: 'success', label: 'Terminé' },
  FAILED: { color: 'error', label: 'Échoué' },
  SKIPPED: { color: 'default', label: 'Ignoré' },
  CANCELLED: { color: 'default', label: 'Annulé' },
  WAITING: { color: 'warning', label: 'En attente d\'approbation' }, // Story 58.3
};

/**
 * Couleurs Ant Design <Tag color={...}> pour les statuts d'exécution.
 * Utilisé par les composants reporting qui affichent le statut en Tag (pas Badge).
 * Tag accepte à la fois des noms CSS ('green', 'red', 'blue') et les chaînes de statut
 * prédéfinies Ant Design ('success', 'processing', 'error', 'default', 'warning').
 * Badge utilise quant à lui BadgeStatusType (voir ci-dessus).
 * Note : SUBMITTED: 'processing' et CANCELLED: 'default' sont des valeurs de statut
 * prédéfinies Ant Design, pas des noms CSS.
 * Cf. SOLID-FE-10 — consolidation depuis ComparisonExecutionsDrawer.
 */
export const EXECUTION_STATUS_TAG_COLORS: Record<ExecutionStatusType, string> = {
  SUBMITTED: 'processing',
  RUNNING: 'blue',
  COMPLETED: 'green',
  FAILED: 'red',
  CANCELLED: 'default',
  INTEGRATION_ERROR: 'red',
  PENDING_APPROVAL: 'orange',
  REJECTED: 'red',
};

/**
 * Options de filtre pour les statuts d'exécution (§16.4 consolidation).
 * Labels féminins pour accord avec "exécution".
 * Ordre chronologique du cycle de vie d'une exécution.
 * Source unique pour ExecutionsFiltersPanel et AdvancedFiltersPanel.
 */
export const EXECUTION_STATUS_FILTER_OPTIONS: { label: string; value: ExecutionStatusType }[] = [
  { label: 'Soumise', value: 'SUBMITTED' },
  { label: 'Approbation requise', value: 'PENDING_APPROVAL' },
  { label: 'En cours', value: 'RUNNING' },
  { label: 'Terminée', value: 'COMPLETED' },
  { label: 'Échouée', value: 'FAILED' },
  { label: 'Annulée', value: 'CANCELLED' },
  { label: 'Rejetée', value: 'REJECTED' },
  { label: 'Erreur intégration', value: 'INTEGRATION_ERROR' },
];

/** Display config for audit execution statuses (migrated from AuditPage.tsx). */
export const AUDIT_STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  success: { color: 'success', label: 'Succès' },
  failed: { color: 'error', label: 'Échec' },
  running: { color: 'processing', label: 'En cours' },
  unknown: { color: 'default', label: 'Inconnu' },
};
