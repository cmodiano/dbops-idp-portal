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
import { FormattedJson } from '../common/FormattedJson';

const { Text } = Typography;

/** Story 72.3: Technical ID fields — never display to auditor (names only). */
const EXCLUDED_DETAIL_KEYS = new Set([
  'step_id',
  'execution_id',
  'referenced_action_id',
  'scheduled_execution_id',
  'integration_id',
  'action_id',
]);

/** User-friendly labels for audit detail keys (Détails section). */
const DETAIL_KEY_LABELS: Record<string, string> = {
  action_name: 'Nom de l\'action',
  previous_status: 'Statut précédent',
  new_status: 'Nouveau statut',
  environment: 'Environnement',
  status: 'Statut',
  name: 'Nom',
  integration_name: 'Nom intégration',
  integration_type: 'Type intégration',
  integration_status: 'Statut intégration',
  reason: 'Raison',
  step_name: 'Nom de l\'étape',
  step_order: 'Ordre de l\'étape',
  step_type: 'Type d\'étape',
  gate_types: 'Types de gate',
  waiting_duration_seconds: 'Durée d\'attente (s)',
  referenced_action_name: 'Action référencée',
  gate_conditions_count: 'Nombre de conditions de gate',
  error_type: 'Type d\'erreur',
  platform_job_id: 'ID job plateforme',
  retry_count: 'Tentative',
  max_retries: 'Tentatives max',
  last_error: 'Dernière erreur',
  timeout_hours: 'Timeout (heures)',
  on_timeout: 'Comportement timeout',
  error_message: 'Message d\'erreur',
  correlation_id: 'Correlation ID',
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

/**
 * Affiche les paramètres d'exécution.
 * workflow_step_parameters : step_name + (param, value) par étape — Story 72.3.
 * Gère format brut (step_id, step_name, parameters) et format audit (step_name, parameters).
 */
function ParametersDisplay({ params }: { params: Record<string, unknown> }) {
  const wsp = params.workflow_step_parameters as Record<string, Record<string, unknown>> | undefined;
  const otherKeys = Object.keys(params).filter((k) => k !== 'workflow_step_parameters');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {wsp && typeof wsp === 'object' && (
        <div>
          {Object.entries(wsp).map(([order, entry]) => {
            const stepName =
              typeof entry === 'object' && entry !== null
                ? (entry.step_name as string) ?? `Étape ${order}`
                : typeof entry === 'string'
                  ? entry
                  : `Étape ${order}`;
            const parameters =
              typeof entry === 'object' && entry !== null && 'parameters' in entry
                ? (entry.parameters as Record<string, unknown>)
                : undefined;
            const paramRows =
              parameters && typeof parameters === 'object'
                ? Object.entries(parameters).map(([param, val]) => ({
                    key: `${order}-${param}`,
                    param,
                    value: typeof val === 'object' && val !== null ? JSON.stringify(val) : String(val ?? '—'),
                  }))
                : [];
            return (
              <div key={order} style={{ marginBottom: 12 }}>
                <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                  {stepName}
                </Text>
                {paramRows.length > 0 ? (
                  <Table
                    dataSource={paramRows}
                    columns={[
                      { title: 'Paramètre', dataIndex: 'param', key: 'param', width: 140 },
                      { title: 'Valeur', dataIndex: 'value', key: 'value' },
                    ]}
                    pagination={false}
                    size="small"
                    style={{ fontSize: 11 }}
                  />
                ) : (
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    Aucun paramètre
                  </Text>
                )}
              </div>
            );
          })}
        </div>
      )}
      {otherKeys.length > 0 && (
        <FormattedJson
          value={Object.fromEntries(otherKeys.map((k) => [k, params[k]]))}
          asTable
        />
      )}
    </div>
  );
}

/** Renders a change value — Story 72.4: format tableau pour objets/tableaux */
function renderChangeValue(v: unknown): ReactNode {
  if (v === undefined) return <span>—</span>;
  const useTable = (typeof v === 'object' && v !== null) || Array.isArray(v);
  return <FormattedJson value={v} asTable={!!useTable} />;
}

/** Row type for the changes table (Modifications section). */
type ChangeRow = { key: string; field: string; oldVal: unknown; newVal: unknown };

/** Typed columns for the changes table — FRONTEND-STANDARDS: TableProps<T>['columns']. */
const CHANGE_COLUMNS: TableProps<ChangeRow>['columns'] = [
  { title: 'Champ', dataIndex: 'field', key: 'field', width: 160 },
  {
    title: 'Avant',
    dataIndex: 'oldVal',
    key: 'oldVal',
    width: 260,
    render: (_: unknown, r: ChangeRow) => (
      <div style={{ minWidth: 240, overflow: 'auto', maxWidth: '100%' }}>{renderChangeValue(r.oldVal)}</div>
    ),
  },
  {
    title: 'Après',
    dataIndex: 'newVal',
    key: 'newVal',
    width: 260,
    render: (_: unknown, r: ChangeRow) => (
      <div style={{ minWidth: 240, overflow: 'auto', maxWidth: '100%' }}>{renderChangeValue(r.newVal)}</div>
    ),
  },
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
      styles={{ wrapper: { width: 680 } }}
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
            {/* Story 72.1: correlation_id visible pour traçabilité (audit, logs) */}
            {(entry.correlation_id || (entry.entity_type === 'execution' && execution?.correlation_id)) && (
              <Descriptions.Item label="Correlation ID">
                <Text copyable={{ text: String(entry.correlation_id ?? execution?.correlation_id ?? '') }}>
                  {String(entry.correlation_id ?? execution?.correlation_id ?? '')}
                </Text>
              </Descriptions.Item>
            )}
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
                  oldVal: vals['old'],
                  newVal: vals['new'],
                }))}
                columns={CHANGE_COLUMNS}
                pagination={false}
                size="small"
                scroll={{ x: 640 }}
              />
            </Card>
          )}

          {/* Details for non-execution entries (action, integration, profile, user, etc.) — Story 72.3: exclude ID fields */}
          {entry.entity_type !== 'execution' && (() => {
            const filteredDetails = entry.details
              ? Object.entries(entry.details).filter(
                  ([k, v]) =>
                    k !== 'changes' &&
                    !EXCLUDED_DETAIL_KEYS.has(k) &&
                    v !== null &&
                    v !== undefined &&
                    v !== '',
                )
              : [];
            if (filteredDetails.length === 0) return null;
            return (
            <Card title="Détails" size="small" style={{ marginBottom: 24 }}>
              <Descriptions column={1} size="small">
                {filteredDetails.map(([key, value]) => (
                    <Descriptions.Item key={key} label={DETAIL_KEY_LABELS[key] ?? key}>
                      <FormattedJson
                        value={value}
                        asTable={typeof value === 'object' && value !== null}
                      />
                    </Descriptions.Item>
                  ))}
              </Descriptions>
            </Card>
            );
          })()}

          {/* Details for execution entries — masqué quand Timeline présente (redondant) */}
          {entry.entity_type === 'execution' && !execution && !(steps.length > 0) && (() => {
            const ALREADY_SHOWN_KEYS = new Set([
              'action_name',
              'step_name',
              'referenced_action_name',
              'targets',
              'parameters',
              'workflow_step_parameters',
              'environment',
              'status',
              'servicenow_change_id',
              'correlation_id',
            ]);
            const filteredDetails = entry.details
              ? Object.entries(entry.details).filter(
                  ([k, v]) =>
                    k !== 'changes' &&
                    !EXCLUDED_DETAIL_KEYS.has(k) &&
                    !ALREADY_SHOWN_KEYS.has(k) &&
                    v !== null &&
                    v !== undefined &&
                    v !== '',
                )
              : [];
            if (filteredDetails.length === 0) return null;
            return (
              <Card title="Détails" size="small" style={{ marginBottom: 24 }}>
                <Descriptions column={1} size="small">
                  {filteredDetails.map(([key, value]) => (
                    <Descriptions.Item key={key} label={DETAIL_KEY_LABELS[key] ?? key}>
                      <FormattedJson
                        value={value}
                        asTable={typeof value === 'object' && value !== null}
                      />
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

          {/* Execution context section — action, targets, parameters (Story 61.10); Story 72.3: step_name, referenced_action_name */}
          {entry.entity_type === 'execution' && (() => {
            const hasContext =
              entry.details?.action_name ||
              entry.details?.step_name ||
              entry.details?.referenced_action_name ||
              (entry.details?.targets && entry.details.targets.length > 0) ||
              entry.details?.parameters ||
              entry.details?.workflow_step_parameters;
            if (!hasContext) return null;
            return (
              <Card title="Contexte d'exécution" size="small" style={{ marginBottom: 24 }}>
                <Descriptions column={1} size="small">
                  {entry.details?.action_name && (
                    <Descriptions.Item label="Action">
                      {String(entry.details.action_name)}
                    </Descriptions.Item>
                  )}
                  {entry.details?.step_name && (
                    <Descriptions.Item label="Étape">
                      {String(entry.details.step_name)}
                    </Descriptions.Item>
                  )}
                  {entry.details?.referenced_action_name && (
                    <Descriptions.Item label="Action référencée">
                      {String(entry.details.referenced_action_name)}
                    </Descriptions.Item>
                  )}
                  {entry.details?.targets && entry.details.targets.length > 0 && (
                    <Descriptions.Item label="Cibles">
                      {entry.details.targets.join(', ')}
                    </Descriptions.Item>
                  )}
                  {Boolean(entry.details?.parameters || entry.details?.workflow_step_parameters) && (
                    <Descriptions.Item label="Paramètres">
                      <ParametersDisplay
                        params={{
                          ...((entry.details?.parameters as Record<string, unknown>) || {}),
                          workflow_step_parameters:
                            entry.details?.workflow_step_parameters ??
                            (entry.details?.parameters as Record<string, unknown>)?.workflow_step_parameters,
                        }}
                      />
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
                correlationId={entry.correlation_id ?? execution?.correlation_id ?? undefined}
              />
            </Card>
          )}
        </div>
      ) : null}
    </Drawer>
  );
}
