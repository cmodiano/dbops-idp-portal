/**
 * Audit action type labels and options.
 * Maps backend AuditActionType enum values to display labels.
 * @see core.models.AuditActionType (backend)
 */

/** Centralized human-readable labels for all audit action types. */
export const ACTION_TYPE_LABELS: Record<string, string> = {
  // Actions
  ACTION_CREATED: 'Action créée',
  ACTION_UPDATED: 'Action modifiée',
  ACTION_PUBLISHED: 'Action publiée',
  ACTION_DISABLED: 'Action désactivée',
  ACTION_DISABLED_INTEGRATION_DELETED: 'Action désactivée (intégration supprimée)',
  ACTION_ENABLED: 'Action activée',
  ACTION_DELETED: 'Action supprimée',
  ACTION_DEACTIVATED: 'Action désactivée',
  ACTION_REACTIVATED: 'Action réactivée',
  // Profils
  PROFILE_CREATED: 'Profil créé',
  PROFILE_UPDATED: 'Profil modifié',
  PROFILE_DELETED: 'Profil supprimé',
  PROFILE_UPDATE_REJECTED: 'Mise à jour profil rejetée',
  // Intégrations
  INTEGRATION_CREATED: 'Intégration créée',
  INTEGRATION_UPDATED: 'Intégration modifiée',
  INTEGRATION_DELETED: 'Intégration supprimée',
  INTEGRATION_STATUS_UPDATED: 'Statut intégration mis à jour',
  INTEGRATION_MARKED_LEGACY: 'Intégration marquée legacy',
  INTEGRATION_TYPE_CREATED: 'Type intégration créé',
  INTEGRATION_TYPE_UPDATED: 'Type intégration modifié',
  INTEGRATION_ACTION_CREATED: 'Action intégration créée',
  INTEGRATION_ACTION_UPDATED: 'Action intégration modifiée',
  // Exécutions
  EXECUTION_SUBMITTED: 'Exécution soumise',
  EXECUTION_RUNNING: 'Exécution en cours',
  EXECUTION_COMPLETED: 'Exécution terminée',
  EXECUTION_FAILED: 'Exécution échouée',
  EXECUTION_CANCELLED: 'Exécution annulée',
  EXECUTION_PENDING_APPROVAL: "En attente d'approbation",
  EXECUTION_APPROVED: 'Exécution approuvée',
  EXECUTION_REJECTED: 'Exécution rejetée',
  EXECUTION_INTEGRATION_ERROR: 'Erreur intégration',
  EXECUTION_TARGET_FORBIDDEN: 'Cible interdite',
  EXECUTION_BLOCKED_INVALID_INTEGRATION: 'Exécution bloquée (intégration invalide)',
  EXECUTION_DEPRECATED_INTEGRATION_WARNING: 'Avertissement intégration dépréciée',
  EXECUTION_POLLING_EXHAUSTED: 'Polling épuisé',
  // Steps
  EXECUTION_STEP_RETRY_ATTEMPT: 'Tentative de retry',
  EXECUTION_STEP_RETRY_SUCCESS: 'Retry réussi',
  EXECUTION_STEP_RETRY_EXHAUSTED: 'Retry épuisé',
  EXECUTION_STEP_RETRY_ABORTED: 'Retry annulé',
  EXECUTION_STEP_WAITING: 'Étape en attente',
  EXECUTION_STEP_GATE_SATISFIED: 'Condition satisfaite',
  EXECUTION_STEP_GATE_TIMEOUT: 'Délai condition expiré',
  EXECUTION_STEP_POLICY_APPROVAL_REQUIRED: 'Approbation requise',
  EXECUTION_STEP_POLICY_AUTO_APPROVED: 'Auto-approuvé',
  EXECUTION_STEP_POLICY_EVALUATION_FAILED: 'Évaluation politique échouée',
  WORKFLOW_STEP_BLOCKED_INVALID_INTEGRATION: 'Étape bloquée (intégration invalide)',
  // Planifiées
  SCHEDULED_EXECUTION_CREATED: 'Exécution planifiée créée',
  SCHEDULED_EXECUTION_RECURRING_CREATED: 'Exécution récurrente créée',
  SCHEDULED_EXECUTION_EXECUTED: 'Exécution planifiée exécutée',
  SCHEDULED_EXECUTION_CANCELLED: 'Exécution planifiée annulée',
  SCHEDULED_EXECUTION_RECURRING_DISABLED: 'Exécution récurrente désactivée',
  SCHEDULED_EXECUTION_CELERY_TRIGGERED: 'Déclenchée par Celery',
  // Utilisateurs
  USER_CREATED: 'Utilisateur créé',
  USER_UPDATED: 'Utilisateur modifié',
  USER_LOGIN: 'Connexion',
  USER_LOGOUT: 'Déconnexion',
  USER_REFRESH: 'Token rafraîchi',
  FAVORITE_ADDED: 'Favori ajouté',
  FAVORITE_REMOVED: 'Favori supprimé',
  // Feature flags
  FEATURE_FLAG_UPDATED: 'Feature flag modifié',
  FEATURE_FLAG_CREATED: 'Feature flag créé',
  // Policies
  POLICY_CREATED: 'Politique créée',
  POLICY_UPDATED: 'Politique modifiée',
  POLICY_DELETED: 'Politique supprimée',
};

/** Filter dropdown options built from ACTION_TYPE_LABELS. */
export const ACTION_TYPE_OPTIONS: { label: string; options: { value: string; label: string }[] }[] = [
  {
    label: 'Actions',
    options: [
      { value: 'ACTION_CREATED', label: ACTION_TYPE_LABELS['ACTION_CREATED'] ?? 'Action créée' },
      { value: 'ACTION_UPDATED', label: ACTION_TYPE_LABELS['ACTION_UPDATED'] ?? 'Action modifiée' },
      { value: 'ACTION_PUBLISHED', label: ACTION_TYPE_LABELS['ACTION_PUBLISHED'] ?? 'Action publiée' },
      { value: 'ACTION_DISABLED', label: ACTION_TYPE_LABELS['ACTION_DISABLED'] ?? 'Action désactivée' },
      { value: 'ACTION_ENABLED', label: ACTION_TYPE_LABELS['ACTION_ENABLED'] ?? 'Action activée' },
      { value: 'ACTION_DELETED', label: ACTION_TYPE_LABELS['ACTION_DELETED'] ?? 'Action supprimée' },
      { value: 'ACTION_REACTIVATED', label: ACTION_TYPE_LABELS['ACTION_REACTIVATED'] ?? 'Action réactivée' },
    ],
  },
  {
    label: 'Exécutions',
    options: [
      { value: 'EXECUTION_SUBMITTED', label: ACTION_TYPE_LABELS['EXECUTION_SUBMITTED'] ?? 'Exécution soumise' },
      { value: 'EXECUTION_PENDING_APPROVAL', label: ACTION_TYPE_LABELS['EXECUTION_PENDING_APPROVAL'] ?? "En attente d'approbation" },
      { value: 'EXECUTION_APPROVED', label: ACTION_TYPE_LABELS['EXECUTION_APPROVED'] ?? 'Exécution approuvée' },
      { value: 'EXECUTION_REJECTED', label: ACTION_TYPE_LABELS['EXECUTION_REJECTED'] ?? 'Exécution rejetée' },
      { value: 'EXECUTION_RUNNING', label: ACTION_TYPE_LABELS['EXECUTION_RUNNING'] ?? 'Exécution en cours' },
      { value: 'EXECUTION_COMPLETED', label: ACTION_TYPE_LABELS['EXECUTION_COMPLETED'] ?? 'Exécution terminée' },
      { value: 'EXECUTION_FAILED', label: ACTION_TYPE_LABELS['EXECUTION_FAILED'] ?? 'Exécution échouée' },
      { value: 'EXECUTION_CANCELLED', label: ACTION_TYPE_LABELS['EXECUTION_CANCELLED'] ?? 'Exécution annulée' },
    ],
  },
  {
    label: 'Intégrations',
    options: [
      { value: 'INTEGRATION_CREATED', label: ACTION_TYPE_LABELS['INTEGRATION_CREATED'] ?? 'Intégration créée' },
      { value: 'INTEGRATION_UPDATED', label: ACTION_TYPE_LABELS['INTEGRATION_UPDATED'] ?? 'Intégration modifiée' },
      { value: 'INTEGRATION_DELETED', label: ACTION_TYPE_LABELS['INTEGRATION_DELETED'] ?? 'Intégration supprimée' },
      { value: 'INTEGRATION_STATUS_UPDATED', label: ACTION_TYPE_LABELS['INTEGRATION_STATUS_UPDATED'] ?? 'Statut intégration mis à jour' },
      { value: 'INTEGRATION_MARKED_LEGACY', label: ACTION_TYPE_LABELS['INTEGRATION_MARKED_LEGACY'] ?? 'Intégration marquée legacy' },
    ],
  },
  {
    label: 'Profils',
    options: [
      { value: 'PROFILE_CREATED', label: ACTION_TYPE_LABELS['PROFILE_CREATED'] ?? 'Profil créé' },
      { value: 'PROFILE_UPDATED', label: ACTION_TYPE_LABELS['PROFILE_UPDATED'] ?? 'Profil modifié' },
      { value: 'PROFILE_DELETED', label: ACTION_TYPE_LABELS['PROFILE_DELETED'] ?? 'Profil supprimé' },
      { value: 'PROFILE_UPDATE_REJECTED', label: ACTION_TYPE_LABELS['PROFILE_UPDATE_REJECTED'] ?? 'Mise à jour profil rejetée' },
    ],
  },
  {
    label: 'Planifiées',
    options: [
      { value: 'SCHEDULED_EXECUTION_CREATED', label: ACTION_TYPE_LABELS['SCHEDULED_EXECUTION_CREATED'] ?? 'Exécution planifiée créée' },
      { value: 'SCHEDULED_EXECUTION_CANCELLED', label: ACTION_TYPE_LABELS['SCHEDULED_EXECUTION_CANCELLED'] ?? 'Exécution planifiée annulée' },
      { value: 'SCHEDULED_EXECUTION_EXECUTED', label: ACTION_TYPE_LABELS['SCHEDULED_EXECUTION_EXECUTED'] ?? 'Exécution planifiée exécutée' },
    ],
  },
];
