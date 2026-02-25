/**
 * Audit action type options for the audit filter dropdown.
 * Maps backend AuditActionType enum values to display labels.
 * @see core.models.AuditActionType (backend)
 */

export const ACTION_TYPE_OPTIONS: { label: string; options: { value: string; label: string }[] }[] = [
  {
    label: 'Actions',
    options: [
      { value: 'ACTION_CREATED', label: 'Action créée' },
      { value: 'ACTION_UPDATED', label: 'Action modifiée' },
      { value: 'ACTION_PUBLISHED', label: 'Action publiée' },
      { value: 'ACTION_DISABLED', label: 'Action désactivée' },
      { value: 'ACTION_ENABLED', label: 'Action activée' },
      { value: 'ACTION_DELETED', label: 'Action supprimée' },
      { value: 'ACTION_REACTIVATED', label: 'Action réactivée' },
    ],
  },
  {
    label: 'Exécutions',
    options: [
      { value: 'EXECUTION_SUBMITTED', label: 'Exécution soumise' },
      { value: 'EXECUTION_PENDING_APPROVAL', label: "En attente d'approbation" },
      { value: 'EXECUTION_APPROVED', label: 'Exécution approuvée' },
      { value: 'EXECUTION_REJECTED', label: 'Exécution rejetée' },
      { value: 'EXECUTION_RUNNING', label: 'Exécution en cours' },
      { value: 'EXECUTION_COMPLETED', label: 'Exécution terminée' },
      { value: 'EXECUTION_FAILED', label: 'Exécution échouée' },
      { value: 'EXECUTION_CANCELLED', label: 'Exécution annulée' },
    ],
  },
  {
    label: 'Intégrations',
    options: [
      { value: 'INTEGRATION_CREATED', label: 'Intégration créée' },
      { value: 'INTEGRATION_UPDATED', label: 'Intégration modifiée' },
      { value: 'INTEGRATION_DELETED', label: 'Intégration supprimée' },
      { value: 'INTEGRATION_STATUS_UPDATED', label: 'Statut intégration mis à jour' },
      { value: 'INTEGRATION_MARKED_LEGACY', label: 'Intégration marquée legacy' },
    ],
  },
  {
    label: 'Profils',
    options: [
      { value: 'PROFILE_CREATED', label: 'Profil créé' },
      { value: 'PROFILE_UPDATED', label: 'Profil modifié' },
      { value: 'PROFILE_DELETED', label: 'Profil supprimé' },
      { value: 'PROFILE_UPDATE_REJECTED', label: 'Mise à jour profil rejetée' },
    ],
  },
  {
    label: 'Planifiées',
    options: [
      { value: 'SCHEDULED_EXECUTION_CREATED', label: 'Exécution planifiée créée' },
      { value: 'SCHEDULED_EXECUTION_CANCELLED', label: 'Exécution planifiée annulée' },
      { value: 'SCHEDULED_EXECUTION_EXECUTED', label: 'Exécution planifiée exécutée' },
    ],
  },
];
