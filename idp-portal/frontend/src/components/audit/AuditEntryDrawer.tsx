/**
 * AuditEntryDrawer — Story 34.11 (SOLID-FE-3), Story 43.5, Story 43.7
 *
 * Drawer de détail d'une entrée d'audit : qui, quoi, quand, paramètres, timeline.
 * Story 43.5 : section "Approbation" conditionnelle pour EXECUTION_APPROVED.
 * Story 43.7 : affichage adapté par entity_type — masquage des champs execution-only
 *              pour actions, intégrations, profils, etc. ; section Détails pour non-executions.
 * Extrait de AuditPage.tsx.
 */

import { Typography, Drawer, Card, Descriptions, Tag, Skeleton, Alert, Divider } from 'antd';
import { ExecutionTimeline } from '../execution/ExecutionTimeline';
import type {
  AuditExecutionEntry,
  ExecutionResponse,
  ExecutionStepResponse,
} from '../../types/api';
import { AUDIT_STATUS_CONFIG as STATUS_CONFIG } from '../../utils/execution-status';
import { ACTION_TYPE_LABELS } from '../../constants/auditActionTypes';
import { ENTITY_TYPE_LABELS, formatDate, getEntityLabel } from './auditLabels';

const { Text } = Typography;

/** User-friendly labels for audit detail keys (Détails section). */
const DETAIL_KEY_LABELS: Record<string, string> = {
  action_name: 'Nom de l\'action',
  action_id: 'ID action',
  previous_status: 'Statut précédent',
  new_status: 'Nouveau statut',
  environment: 'Environnement',
  status: 'Statut',
  name: 'Nom',
  integration_id: 'ID intégration',
  integration_name: 'Nom intégration',
  integration_type: 'Type intégration',
  integration_status: 'Statut intégration',
  reason: 'Raison',
};

export interface AuditEntryDrawerProps {
  open: boolean;
  entry: AuditExecutionEntry | null;
  execution: ExecutionResponse | null;
  steps: ExecutionStepResponse[];
  loading: boolean;
  error: string | null;
  onClose: () => void;
}

export function AuditEntryDrawer({
  open,
  entry,
  execution,
  steps,
  loading,
  error,
  onClose,
}: AuditEntryDrawerProps) {
  const drawerTitle = entry
    ? `Détail — ${ENTITY_TYPE_LABELS[entry.entity_type] ?? entry.entity_type}`
    : "Détail d'audit";

  return (
    <Drawer
      title={drawerTitle}
      open={open}
      onClose={onClose}
      styles={{ wrapper: { width: 600 } }}
      destroyOnClose
    >
      {loading ? (
        <Skeleton active paragraph={{ rows: 8 }} />
      ) : error ? (
        <Alert type="error" title="Erreur de chargement" description={error} showIcon />
      ) : entry ? (
        <div>
          {/* Audit entry details — common fields */}
          <Descriptions bordered column={1} size="small" style={{ marginBottom: 24 }}>
            <Descriptions.Item label="Qui">{entry.user_name ?? entry.user_id ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="Quoi">{getEntityLabel(entry)}</Descriptions.Item>
            <Descriptions.Item label="Type">
              {ACTION_TYPE_LABELS[entry.action_type] ?? entry.action_type}
            </Descriptions.Item>
            <Descriptions.Item label="Catégorie">
              {ENTITY_TYPE_LABELS[entry.entity_type] ?? entry.entity_type}
            </Descriptions.Item>
            <Descriptions.Item label="Quand">{formatDate(entry.timestamp)}</Descriptions.Item>
            {entry.entity_type === 'execution' && (
              <Descriptions.Item label="Environnement">
                {entry.details?.environment?.toUpperCase() || '—'}
              </Descriptions.Item>
            )}
            {entry.entity_type === 'execution' && (() => {
              const config = STATUS_CONFIG[entry.derived_status];
              if (!config) return null;
              return (
                <Descriptions.Item label="Résultat">
                  <Tag color={config.color}>{config.label}</Tag>
                </Descriptions.Item>
              );
            })()}
            <Descriptions.Item label="Adresse IP">{entry.ip_address || '—'}</Descriptions.Item>
            <Descriptions.Item label="Correlation ID">
              <Text copyable={entry.correlation_id ? { text: entry.correlation_id } : undefined}>
                {entry.correlation_id || '—'}
              </Text>
            </Descriptions.Item>
            {entry.entity_type === 'execution' && entry.details?.servicenow_change_id && (
              <Descriptions.Item label="Change ServiceNow">
                <Text copyable={{ text: String(entry.details.servicenow_change_id) }}>
                  {String(entry.details.servicenow_change_id)}
                </Text>
              </Descriptions.Item>
            )}
          </Descriptions>

          {/* Details for non-execution entries (action, integration, profile, user, etc.) */}
          {entry.entity_type !== 'execution' && (() => {
            const filteredDetails = entry.details
              ? Object.entries(entry.details).filter(([, v]) => v !== null && v !== undefined && v !== '')
              : [];
            if (filteredDetails.length === 0) return null;
            return (
            <Card title="Détails" size="small" style={{ marginBottom: 24 }}>
              <Descriptions column={1} size="small">
                {filteredDetails.map(([key, value]) => (
                    <Descriptions.Item key={key} label={DETAIL_KEY_LABELS[key] ?? key}>
                      {typeof value === 'object' ? (
                        <pre style={{ margin: 0, fontSize: 11, whiteSpace: 'pre-wrap' }}>
                          {JSON.stringify(value, null, 2)}
                        </pre>
                      ) : (
                        String(value)
                      )}
                    </Descriptions.Item>
                  ))}
              </Descriptions>
            </Card>
            );
          })()}

          {/* Approval section for EXECUTION_APPROVED */}
          {entry.action_type === 'EXECUTION_APPROVED' && (
            <>
              <Divider titlePlacement="left" plain style={{ fontSize: 13 }}>
                Approbation
              </Divider>
              <Descriptions size="small" column={1} style={{ marginBottom: 16 }}>
                <Descriptions.Item label="Approuvé par">
                  {entry.user_name ?? entry.user_id ?? '—'}
                </Descriptions.Item>
                {execution?.approved_at && (
                  <Descriptions.Item label="Date d'approbation">
                    {formatDate(execution.approved_at)}
                  </Descriptions.Item>
                )}
                {execution?.approval_comment && (
                  <Descriptions.Item label="Commentaire">
                    {execution.approval_comment}
                  </Descriptions.Item>
                )}
              </Descriptions>
            </>
          )}

          {/* Parameters if available (executions only) */}
          {entry.entity_type === 'execution' && entry.details?.parameters && (
            <Card title="Paramètres" size="small" style={{ marginBottom: 24 }}>
              <pre style={{ margin: 0, fontSize: 12, whiteSpace: 'pre-wrap' }}>
                {JSON.stringify(entry.details.parameters, null, 2)}
              </pre>
            </Card>
          )}

          {/* Execution timeline if available */}
          {execution && steps.length > 0 && (
            <Card title="Timeline d'exécution" size="small">
              <ExecutionTimeline
                execution={execution}
                steps={steps}
                mode="historical"
              />
            </Card>
          )}
        </div>
      ) : null}
    </Drawer>
  );
}
