/**
 * Audit service for consultation historique (Story 6.3).
 *
 * Provides functions to fetch audit log entries for executions.
 * Access restricted to auditors (is_auditor=true).
 */

import type {
  AuditExecutionEntry,
  AuditExecutionFilters,
  AuditExecutionListResponse,
  PaginationInfo,
} from '../types/api';

const API_BASE = '/api/v1';

/**
 * Build query string from filters (Story 6.3, AC6).
 * Maps 'from' and 'to' to API query params.
 */
function buildQueryString(filters: AuditExecutionFilters): string {
  const params = new URLSearchParams();

  if (filters.from) {
    params.set('from', filters.from);
  }
  if (filters.to) {
    params.set('to', filters.to);
  }
  if (filters.environment) {
    params.set('environment', filters.environment);
  }
  if (filters.action_id !== undefined) {
    params.set('action_id', String(filters.action_id));
  }
  if (filters.user_id) {
    params.set('user_id', filters.user_id);
  }
  if (filters.status) {
    params.set('status', filters.status);
  }
  if (filters.sort) {
    params.set('sort', filters.sort);
  }
  if (filters.order) {
    params.set('order', filters.order);
  }
  if (filters.limit !== undefined) {
    params.set('limit', String(filters.limit));
  }
  if (filters.offset !== undefined) {
    params.set('offset', String(filters.offset));
  }

  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

/**
 * List execution audit entries with filters (Story 6.3, AC1, AC2, AC6).
 *
 * @param filters - Optional filters for the query
 * @returns Paginated list of audit entries
 * @throws Error with message if request fails (403 if not auditor)
 */
export async function listExecutionAudit(
  filters: AuditExecutionFilters = {},
): Promise<{ data: AuditExecutionEntry[]; pagination: PaginationInfo }> {
  const queryString = buildQueryString(filters);
  const response = await fetch(`${API_BASE}/audit/executions${queryString}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message =
      errorData?.error?.message ||
      (response.status === 403 ? 'Accès réservé aux auditeurs' : 'Erreur de chargement');
    throw new Error(message);
  }

  const result: AuditExecutionListResponse = await response.json();
  return {
    data: result.data,
    pagination: result.pagination,
  };
}

/**
 * Export audit report as CSV or PDF (Story 6.4, AC2, AC3, AC4).
 *
 * @param format - Export format: 'csv' or 'pdf'
 * @param filters - Filters to apply (same as listExecutionAudit)
 * @throws Error with message if request fails (403 if not auditor, 400 if limit exceeded)
 */
export async function exportAuditReport(
  format: 'csv' | 'pdf',
  filters: AuditExecutionFilters = {},
): Promise<void> {
  const params = new URLSearchParams();
  params.set('format', format);

  if (filters.from) {
    params.set('from', filters.from);
  }
  if (filters.to) {
    params.set('to', filters.to);
  }
  if (filters.environment) {
    params.set('environment', filters.environment);
  }
  if (filters.action_id !== undefined) {
    params.set('action_id', String(filters.action_id));
  }
  if (filters.user_id) {
    params.set('user_id', filters.user_id);
  }
  if (filters.status) {
    params.set('status', filters.status);
  }

  const response = await fetch(`${API_BASE}/audit/export?${params.toString()}`, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message =
      errorData?.error?.message ||
      (response.status === 403
        ? 'Accès réservé aux auditeurs'
        : response.status === 400 || response.status === 413
          ? 'Limite d\'export dépassée (maximum 10 000 lignes). Veuillez appliquer des filtres supplémentaires.'
          : 'Erreur lors de l\'export');
    throw new Error(message);
  }

  // Get filename from Content-Disposition header or generate default
  const contentDisposition = response.headers.get('Content-Disposition');
  let filename = `audit-export-${new Date().toISOString().split('T')[0]}.${format}`;
  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename="(.+)"/);
    if (filenameMatch) {
      filename = filenameMatch[1];
    }
  }

  // Download file
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}
