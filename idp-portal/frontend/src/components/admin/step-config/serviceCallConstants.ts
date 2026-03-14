/**
 * Constants for ServiceCallStepConfig — Story 57.13, AC3.
 *
 * SYNC: Les opérations doivent rester synchronisées avec
 * django_backend/executions/step_handlers/service_call_handler.py#_ALLOWED_OPERATIONS
 */

// SYNC with service_call_handler.py#_ALLOWED_OPERATIONS
export const SERVICE_CALL_OPERATIONS: Record<string, string[]> = {
  servicenow: ['create_change', 'update_change', 'close_change', 'get_change_status', 'cancel_change'],
  vault: ['get_secret'], // pragma: allowlist secret
  jira: ['create_issue', 'update_issue', 'get_issue'],
  notification: ['send_email', 'send_teams', 'notify_execution_event'],
};

export const INTEGRATION_LABELS: Record<string, string> = {
  servicenow: 'ServiceNow',
  vault: 'HashiCorp Vault',
  jira: 'Jira',
  notification: 'Notification',
};

