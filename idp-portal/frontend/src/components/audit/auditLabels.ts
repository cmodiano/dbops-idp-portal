/**
 * Audit labels and helpers shared by AuditTable and AuditEntryDrawer.
 * Extracted to satisfy react-refresh/only-export-components.
 */

import { formatUtcToLocal } from '../../utils/dateFormat';
import type { AuditExecutionEntry } from '../../types/api';

export const ENTITY_TYPE_LABELS: Record<string, string> = {
  action: 'Action',
  execution: 'Exécution',
  integration: 'Intégration',
  profile: 'Profil',
  user: 'Utilisateur',
  permission: 'Permission',
  scheduled_execution: 'Exécution planifiée',
  feature_flag: 'Feature Flag',
  integration_type_catalogue: 'Catalogue intégration',
  integration_action: 'Action intégration',
  business_rule_policy: 'Politique',
};

/** Format UTC date for display in local timezone (API dates are UTC with Z suffix). */
export function formatDate(dateStr: string | null): string {
  return formatUtcToLocal(dateStr, 'datetime');
}

/** Get entity label for the Entité column. Story 72.3: no UUID, use readable names only. */
export function getEntityLabel(entry: AuditExecutionEntry): string {
  if (entry.action_name) {
    return entry.action_name;
  }
  if (entry.entity_type === 'action') {
    const raw = entry.details?.name ?? entry.details?.action_name;
    if (typeof raw === 'string') return raw;
    return 'Action';
  }
  if (entry.entity_type === 'integration') {
    const raw =
      entry.details?.integration_name ??
      entry.details?.action_code ??
      entry.details?.integration_type_code;
    if (typeof raw === 'string') return raw;
    return 'Intégration';
  }
  if (entry.entity_type === 'profile') {
    const raw = entry.details?.name;
    if (typeof raw === 'string') return raw;
    return 'Profil';
  }
  if (entry.entity_type === 'user') {
    return entry.user_name ?? entry.user_id ?? 'Utilisateur';
  }
  if (entry.entity_type && ENTITY_TYPE_LABELS[entry.entity_type]) {
    return ENTITY_TYPE_LABELS[entry.entity_type];
  }
  return '—';
}

/** @deprecated Use getEntityLabel instead. */
export function getActionName(entry: AuditExecutionEntry): string {
  return getEntityLabel(entry);
}
