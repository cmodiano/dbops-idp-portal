/**
 * Audit labels and helpers shared by AuditTable and AuditEntryDrawer.
 * Extracted to satisfy react-refresh/only-export-components.
 */

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

/** Format date for display. */
export function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  const date = new Date(dateStr);
  return date.toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Get entity label for the Entité column. Replaces getActionName. */
export function getEntityLabel(entry: AuditExecutionEntry): string {
  if (entry.action_name) {
    return entry.action_name;
  }
  if (entry.entity_type === 'action') {
    const name = (entry.details?.name ?? entry.details?.action_name) as string | undefined;
    if (name) return name;
    return `Action #${entry.entity_id}`;
  }
  if (entry.entity_type === 'integration') {
    const code = (entry.details?.action_code ?? entry.details?.integration_type_code) as string | undefined;
    if (code) return code;
    return `Intégration #${entry.entity_id}`;
  }
  if (entry.entity_type === 'profile') {
    const name = entry.details?.name as string | undefined;
    if (name) return name;
    return `Profil #${entry.entity_id}`;
  }
  if (entry.entity_type === 'user') {
    return entry.user_name ?? entry.user_id ?? `Utilisateur #${entry.entity_id}`;
  }
  if (entry.entity_id != null) {
    return `#${entry.entity_id}`;
  }
  return '—';
}

/** @deprecated Use getEntityLabel instead. */
export function getActionName(entry: AuditExecutionEntry): string {
  return getEntityLabel(entry);
}
