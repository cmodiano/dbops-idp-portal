/**
 * AuditTable — Story 34.11 (SOLID-FE-3), Story 43.4
 *
 * Table des entrées d'audit avec colonnes, pagination, tri, et expandable rows workflow.
 * Story 43.4 : colonnes Type, Opération, Entité, Catégorie + contrôle de visibilité.
 */

import { useState } from 'react';
import type { ReactNode } from 'react';
import { Typography, Table, Tag, Space, Popover, Checkbox, Button } from 'antd';
import type { TableProps } from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  CloseOutlined,
  PlayCircleOutlined,
  ExclamationCircleOutlined,
  StopOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  SendOutlined,
  TableOutlined,
} from '@ant-design/icons';
import type {
  AuditExecutionEntry,
  PaginationInfo,
} from '../../types/api';
import { AUDIT_STATUS_CONFIG as STATUS_CONFIG } from '../../utils/execution-status';

const { Text } = Typography;

const PAGE_SIZE_OPTIONS = [25, 50, 100];

type TableOnChange<T> = NonNullable<TableProps<T>['onChange']>;

// ─── Mappings ────────────────────────────────────────────────────────────────

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

interface OperationConfig {
  label: string;
  icon: ReactNode;
  color: string;
}

const OPERATION_SUFFIX_MAP: Array<{ suffix: string; config: OperationConfig }> = [
  { suffix: '_PENDING_APPROVAL', config: { label: 'En attente', icon: <ClockCircleOutlined />, color: 'orange' } },
  { suffix: '_APPROVED', config: { label: 'Approuver', icon: <CheckCircleOutlined />, color: 'green' } },
  { suffix: '_REJECTED', config: { label: 'Rejeter', icon: <CloseOutlined />, color: 'red' } },
  { suffix: '_PUBLISHED', config: { label: 'Publier', icon: <CheckCircleOutlined />, color: 'green' } },
  { suffix: '_SUBMITTED', config: { label: 'Soumettre', icon: <SendOutlined />, color: 'blue' } },
  { suffix: '_COMPLETED', config: { label: 'Terminer', icon: <CheckCircleOutlined />, color: 'green' } },
  { suffix: '_FAILED', config: { label: 'Échouer', icon: <ExclamationCircleOutlined />, color: 'red' } },
  { suffix: '_CANCELLED', config: { label: 'Annuler', icon: <StopOutlined />, color: 'volcano' } },
  { suffix: '_RUNNING', config: { label: 'Démarrer', icon: <PlayCircleOutlined />, color: 'blue' } },
  { suffix: '_DELETED', config: { label: 'Supprimer', icon: <DeleteOutlined />, color: 'red' } },
  { suffix: '_CREATED', config: { label: 'Créer', icon: <PlusOutlined />, color: 'green' } },
  { suffix: '_UPDATED', config: { label: 'Modifier', icon: <EditOutlined />, color: 'blue' } },
  { suffix: '_DISABLED', config: { label: 'Désactiver', icon: <StopOutlined />, color: 'orange' } },
  { suffix: '_ENABLED', config: { label: 'Activer', icon: <CheckCircleOutlined />, color: 'green' } },
  { suffix: '_REACTIVATED', config: { label: 'Réactiver', icon: <SyncOutlined />, color: 'blue' } },
  { suffix: '_DEACTIVATED', config: { label: 'Désactiver', icon: <StopOutlined />, color: 'orange' } },
  { suffix: '_EXECUTED', config: { label: 'Exécuter', icon: <PlayCircleOutlined />, color: 'blue' } },
  { suffix: '_TRIGGERED', config: { label: 'Déclencher', icon: <PlayCircleOutlined />, color: 'blue' } },
  { suffix: '_BLOCKED', config: { label: 'Bloquer', icon: <CloseOutlined />, color: 'red' } },
  { suffix: '_FORBIDDEN', config: { label: 'Interdit', icon: <CloseOutlined />, color: 'red' } },
  { suffix: '_INTEGRATION', config: { label: 'Intégration', icon: <ExclamationCircleOutlined />, color: 'orange' } },
  { suffix: '_EXHAUSTED', config: { label: 'Polling épuisé', icon: <ExclamationCircleOutlined />, color: 'orange' } },
  { suffix: '_WARNING', config: { label: 'Avertissement', icon: <ExclamationCircleOutlined />, color: 'orange' } },
];

const FALLBACK_OPERATION: OperationConfig = { label: '—', icon: null, color: 'default' };

// eslint-disable-next-line react-refresh/only-export-components
export function getOperationConfig(actionType: string): OperationConfig {
  if (!actionType) return FALLBACK_OPERATION;
  for (const { suffix, config } of OPERATION_SUFFIX_MAP) {
    if (actionType.endsWith(suffix)) return config;
  }
  return FALLBACK_OPERATION;
}

// ─── Column visibility ────────────────────────────────────────────────────────

const COLUMN_VISIBILITY_OPTIONS = [
  { label: 'Entité', value: 'entity' },
  { label: 'Type', value: 'type' },
  { label: 'Opération', value: 'operation' },
  { label: 'Utilisateur', value: 'user_id' },
  { label: 'Catégorie', value: 'category' },
  { label: 'Environnement', value: 'environment' },
  { label: 'Statut', value: 'status' },
  { label: 'Date', value: 'timestamp' },
  { label: 'Change SN', value: 'servicenow' },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Format date for display. */
// eslint-disable-next-line react-refresh/only-export-components
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
// eslint-disable-next-line react-refresh/only-export-components
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
// eslint-disable-next-line react-refresh/only-export-components
export function getActionName(entry: AuditExecutionEntry): string {
  return getEntityLabel(entry);
}

// ─── Props ────────────────────────────────────────────────────────────────────

export interface AuditTableProps {
  topLevelEntries: AuditExecutionEntry[];
  childrenByParentId: Map<number, AuditExecutionEntry[]>;
  loading: boolean;
  pagination: PaginationInfo | null;
  currentPage: number;
  pageSize: number;
  sortField: string;
  sortOrder: 'ascend' | 'descend';
  onChange: TableOnChange<AuditExecutionEntry>;
  onRowClick: (record: AuditExecutionEntry) => void;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function AuditTable({
  topLevelEntries,
  childrenByParentId,
  loading,
  pagination,
  currentPage,
  pageSize,
  sortField,
  sortOrder,
  onChange,
  onRowClick,
}: AuditTableProps) {
  const [hiddenColumns, setHiddenColumns] = useState<Set<string>>(
    new Set(['category', 'environment', 'servicenow']),
  );

  const allColumns: TableProps<AuditExecutionEntry>['columns'] = [
    {
      title: 'Entité',
      key: 'entity',
      sorter: true,
      sortOrder: sortField === 'entity' ? sortOrder : undefined,
      render: (_: unknown, record: AuditExecutionEntry) => getEntityLabel(record),
    },
    {
      title: 'Type',
      key: 'type',
      render: (_: unknown, record: AuditExecutionEntry) =>
        ACTION_TYPE_LABELS[record.action_type] ?? record.action_type,
    },
    {
      title: 'Opération',
      key: 'operation',
      width: 130,
      render: (_: unknown, record: AuditExecutionEntry) => {
        const op = getOperationConfig(record.action_type);
        if (!op.icon && op.label === '—') return <span>—</span>;
        return (
          <Space size={4}>
            <span style={{ color: op.color }}>{op.icon}</span>
            <span>{op.label}</span>
          </Space>
        );
      },
    },
    {
      title: 'Utilisateur',
      dataIndex: 'user_name',
      key: 'user_id',
      width: 140,
      render: (_: string | null, record: AuditExecutionEntry) => {
        if (record.action_type === 'EXECUTION_APPROVED') {
          return (
            <Tag icon={<CheckCircleOutlined />} color="green">
              Approuvé par {record.user_name ?? record.user_id}
            </Tag>
          );
        }
        return record.user_name ?? record.user_id ?? '—';
      },
    },
    {
      title: 'Catégorie',
      key: 'category',
      width: 140,
      render: (_: unknown, record: AuditExecutionEntry) =>
        ENTITY_TYPE_LABELS[record.entity_type] ?? record.entity_type,
    },
    {
      title: 'Environnement',
      key: 'environment',
      width: 120,
      render: (_: unknown, record: AuditExecutionEntry) =>
        record.entity_type !== 'execution' ? (
          <span>—</span>
        ) : (
          <span>{record.details?.environment?.toUpperCase() || '—'}</span>
        ),
    },
    {
      title: 'Statut',
      key: 'status',
      width: 100,
      render: (_: unknown, record: AuditExecutionEntry) => {
        if (record.entity_type !== 'execution') return <span>—</span>;
        const config = STATUS_CONFIG[record.derived_status] || STATUS_CONFIG.unknown;
        return <Tag color={config.color}>{config.label}</Tag>;
      },
    },
    {
      title: 'Date',
      dataIndex: 'timestamp',
      key: 'timestamp',
      sorter: true,
      sortOrder: sortField === 'timestamp' ? sortOrder : undefined,
      width: 160,
      render: (date: string) => formatDate(date),
    },
    {
      title: 'Change SN',
      key: 'servicenow',
      width: 130,
      render: (_: unknown, record: AuditExecutionEntry) => {
        if (record.entity_type !== 'execution') return '—';
        const changeId = record.details?.servicenow_change_id;
        return changeId ? (
          <Text copyable={{ text: String(changeId) }}>{String(changeId).slice(0, 10)}...</Text>
        ) : (
          '—'
        );
      },
    },
  ];

  const columns = allColumns.filter((col) => !hiddenColumns.has(col.key as string));

  const visibleValues = COLUMN_VISIBILITY_OPTIONS.map((o) => o.value).filter(
    (v) => !hiddenColumns.has(v),
  );

  const columnToggle = (
    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
      <Popover
        title="Colonnes visibles"
        content={
          <Checkbox.Group
            options={COLUMN_VISIBILITY_OPTIONS}
            value={visibleValues}
            onChange={(checked) => {
              const allKeys = COLUMN_VISIBILITY_OPTIONS.map((o) => o.value);
              const newHidden = new Set(allKeys.filter((k) => !(checked as string[]).includes(k)));
              setHiddenColumns(newHidden);
            }}
            style={{ display: 'flex', flexDirection: 'column', gap: 4 }}
          />
        }
        trigger="click"
      >
        <Button icon={<TableOutlined />} size="small">
          Colonnes
        </Button>
      </Popover>
    </div>
  );

  return (
    <>
      {columnToggle}
      <Table<AuditExecutionEntry>
        dataSource={topLevelEntries}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{
          current: currentPage,
          pageSize,
          total: pagination?.total || 0,
          showSizeChanger: true,
          pageSizeOptions: PAGE_SIZE_OPTIONS.map(String),
        }}
        onChange={onChange}
        onRow={(record) => ({
          onClick: () => onRowClick(record),
          style: { cursor: 'pointer' },
        })}
        expandable={{
          rowExpandable: (record) =>
            record.item_type === 'workflow' &&
            (childrenByParentId.get(record.entity_id)?.length ?? 0) > 0,
          expandedRowRender: (record) => {
            const children = childrenByParentId.get(record.entity_id) ?? [];
            if (children.length === 0) return null;
            return (
              <div style={{ padding: '8px 0 8px 24px' }}>
                <Text type="secondary" style={{ fontSize: 12, marginBottom: 8, display: 'block' }}>
                  Actions du workflow ({children.length})
                </Text>
                <Table<AuditExecutionEntry>
                  dataSource={children}
                  rowKey="id"
                  size="small"
                  pagination={false}
                  showHeader={false}
                  onRow={(childRecord) => ({
                    onClick: (e) => {
                      e.stopPropagation();
                      onRowClick(childRecord);
                    },
                    style: { cursor: 'pointer' },
                  })}
                  columns={columns}
                />
              </div>
            );
          },
        }}
        locale={{
          emptyText: "Aucune entrée d'audit trouvée",
        }}
      />
    </>
  );
}

