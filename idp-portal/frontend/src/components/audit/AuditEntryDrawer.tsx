/**
 * AuditEntryDrawer — Story 34.11 (SOLID-FE-3), Story 43.5, Story 43.7
 *
 * Drawer de détail d'une entrée d'audit : qui, quoi, quand, paramètres, timeline.
 * Story 43.5 : section "Approbation" conditionnelle pour EXECUTION_APPROVED.
 * Story 43.7 : affichage adapté par entity_type — masquage des champs execution-only
 *              pour actions, intégrations, profils, etc. ; section Détails pour non-executions.
 * Extrait de AuditPage.tsx.
 */

import type { ReactNode } from 'react';
import { Typography, Drawer, Card, Descriptions, Tag, Skeleton, Alert, Divider, Table } from 'antd';
import type { TableProps } from 'antd';
import { ExecutionTimeline } from '../execution/ExecutionTimeline';
import type {
  AuditExecutionEntry,
  ExecutionResponse,
  ExecutionStepResponse,
} from '../../types/api';
import { AUDIT_STATUS_CONFIG as STATUS_CONFIG } from '../../utils/execution-status';
import { ACTION_TYPE_LABELS } from '../../constants/auditActionTypes';
import { ENTITY_TYPE_LABELS, formatDate, getEntityLabel } from './auditLabels';
import { getEnvironmentLabel } from '../../utils/environmentHelpers';
import { getApprovalInfoFromSteps } from '../../utils/executionHelpers';

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

/** Renders a change value: null/undefined → '—', object → <pre>JSON</pre>, else String(v). */
function renderChangeValue(v: unknown): ReactNode {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'object') {
    return (
      <pre style={{ margin: 0, fontSize: 11, whiteSpace: 'pre-wrap' }}>
        {JSON.stringify(v, null, 2)}
      </pre>
    );
  }
  return String(v);
}

/** Row type for the changes table (Modifications section). */
type ChangeRow = { key: string; field: string; old: unknown; new: unknown };

/** Typed columns for the changes table — FRONTEND-STANDARDS: TableProps<T>['columns']. */
const CHANGE_COLUMNS: TableProps<ChangeRow>['columns'] = [
  { title: 'Champ', dataIndex: 'field', key: 'field' },
  { title: 'Avant', dataIndex: 'old', key: 'old', render: renderChangeValue },
  { title: 'Après', dataIndex: 'new', key: 'new', render: renderChangeValue },
];

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
                {getEnvironmentLabel(entry.details?.environment ?? '') || '—'}
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

          {/* Modifications section for non-execution entries with changes (Story 61.9) */}
          {entry.entity_type !== 'execution' && entry.details?.changes && Object.keys(entry.details.changes).length > 0 && (
            <Card title="Modifications" size="small" style={{ marginBottom: 24 }}>
              <Table
                dataSource={Object.entries(entry.details.changes).map(([field, vals]) => ({
                  key: field,
                  field,
                  old: vals.old,
                  new: vals.new,
                }))}
                columns={CHANGE_COLUMNS}
                pagination={false}
                size="small"
              />
            </Card>
          )}

          {/* Details for non-execution entries (action, integration, profile, user, etc.) */}
          {entry.entity_type !== 'execution' && (() => {
            const filteredDetails = entry.details
              ? Object.entries(entry.details).filter(([k, v]) => k !== 'changes' && v !== null && v !== undefined && v !== '')
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

          {/* Approval section for EXECUTION_APPROVED (Story 71.2: read from steps per ADR-007) */}
          {entry.action_type === 'EXECUTION_APPROVED' && (() => {
            const approvalInfo = getApprovalInfoFromSteps(steps);
            return (
              <>
                <Divider titlePlacement="left" plain style={{ fontSize: 13 }}>
                  Approbation
                </Divider>
                <Descriptions size="small" column={1} style={{ marginBottom: 16 }}>
                  <Descriptions.Item label="Approuvé par">
                    {entry.user_name ?? entry.user_id ?? '—'}
                  </Descriptions.Item>
                  {approvalInfo.approvedAt && (
                    <Descriptions.Item label="Date d'approbation">
                      {formatDate(approvalInfo.approvedAt)}
                    </Descriptions.Item>
                  )}
                  {approvalInfo.approvalComment && (
                    <Descriptions.Item label="Commentaire">
                      {approvalInfo.approvalComment}
                    </Descriptions.Item>
                  )}
                </Descriptions>
              </>
            );
          })()}

          {/* Execution context section — action, targets, parameters (Story 61.10) */}
          {entry.entity_type === 'execution' && (() => {
            const hasContext =
              entry.details?.action_name ||
              (entry.details?.targets && entry.details.targets.length > 0) ||
              entry.details?.parameters;
            if (!hasContext) return null;
            return (
              <Card title="Contexte d'exécution" size="small" style={{ marginBottom: 24 }}>
                <Descriptions column={1} size="small">
                  {entry.details?.action_name && (
                    <Descriptions.Item label="Action">
                      {String(entry.details.action_name)}
                    </Descriptions.Item>
                  )}
                  {entry.details?.targets && entry.details.targets.length > 0 && (
                    <Descriptions.Item label="Cibles">
                      {entry.details.targets.join(', ')}
                    </Descriptions.Item>
                  )}
                  {entry.details?.parameters && (
                    <Descriptions.Item label="Paramètres">
                      <pre style={{ margin: 0, fontSize: 12, whiteSpace: 'pre-wrap' }}>
                        {JSON.stringify(entry.details.parameters, null, 2)}
                      </pre>
                    </Descriptions.Item>
                  )}
                </Descriptions>
              </Card>
            );
          })()}

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
