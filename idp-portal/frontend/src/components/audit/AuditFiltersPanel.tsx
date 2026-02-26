/**
 * AuditFiltersPanel — Story 46.7
 *
 * Extraction des filtres inline de AuditPage.tsx en composant dédié.
 * Pattern harmonisé : Card + FilterOutlined + Badge actifs + bouton reset ClearOutlined.
 * Miroir de ExecutionsFiltersPanel et CalendarFiltersPanel.
 */

import {
  Card,
  Badge,
  Button,
  Space,
  Select,
  DatePicker,
  Input,
  Tag,
  Tooltip,
  theme,
} from 'antd';
import { FilterOutlined, ClearOutlined } from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import { ACTION_TYPE_OPTIONS } from '../../constants/auditActionTypes';
import type { AuditStatusFilter } from '../../types/api';
import type { CatalogAction } from '../../services/catalog_service';
import { useEnvironments } from '../../hooks/useEnvironments';

const { RangePicker } = DatePicker;

const STATUS_OPTIONS: { value: AuditStatusFilter; label: string }[] = [
  { value: 'success', label: 'Succès' },
  { value: 'failed', label: 'Échec' },
  { value: 'running', label: 'En cours' },
];

const PERIOD_PRESETS: { label: string; value: [Dayjs, Dayjs] }[] = [
  { label: '7 derniers jours', value: [dayjs().subtract(7, 'day'), dayjs()] },
  { label: '30 derniers jours', value: [dayjs().subtract(30, 'day'), dayjs()] },
  { label: '90 derniers jours', value: [dayjs().subtract(90, 'day'), dayjs()] },
];

export interface AuditFiltersPanelProps {
  // Valeurs des filtres
  dateRange: [Dayjs | null, Dayjs | null];
  setDateRange: (range: [Dayjs | null, Dayjs | null]) => void;
  environment: string | undefined;
  setEnvironment: (val: string | undefined) => void;
  engineType: string | undefined;
  setEngineType: (val: string | undefined) => void;
  actionId: number | undefined;
  setActionId: (val: number | undefined) => void;
  status: AuditStatusFilter | undefined;
  setStatus: (val: AuditStatusFilter | undefined) => void;
  correlationId: string;
  setCorrelationId: (val: string) => void;
  actionType: string | undefined;
  setActionType: (val: string | undefined) => void;
  userSearchInput: string;
  setUserSearchInput: (val: string) => void;
  // Options de sélection
  actions: CatalogAction[];
  actionsLoading: boolean;
  engineOptions: { value: string; label: string }[];
  enginesLoading: boolean;
  // État de chargement
  loading: boolean;
  // Badge et reset
  activeFilterCount: number;
  onResetFilters: () => void;
}

export function AuditFiltersPanel({
  dateRange,
  setDateRange,
  environment,
  setEnvironment,
  engineType,
  setEngineType,
  actionId,
  setActionId,
  status,
  setStatus,
  correlationId,
  setCorrelationId,
  actionType,
  setActionType,
  userSearchInput,
  setUserSearchInput,
  actions,
  actionsLoading,
  engineOptions,
  enginesLoading,
  loading,
  activeFilterCount,
  onResetFilters,
}: AuditFiltersPanelProps) {
  const { token } = theme.useToken();
  // MEDIUM-2 fix: charger dynamiquement les environnements depuis la DB (pattern ExecutionsFiltersPanel)
  const { environmentOptions, loading: environmentsLoading } = useEnvironments();

  const cardExtra = (
    <Space>
      <Badge
        count={activeFilterCount}
        style={{ backgroundColor: token.colorPrimary }}
        data-testid="audit-active-filters-badge"
      >
        <Button
          icon={<ClearOutlined />}
          size="large"
          style={{ minHeight: 44 }}
          onClick={onResetFilters}
          disabled={activeFilterCount === 0}
          data-testid="audit-filter-reset"
        >
          Réinitialiser
        </Button>
      </Badge>
    </Space>
  );

  return (
    <Card
      size="small"
      title={
        <Space>
          <FilterOutlined />
          Filtres
        </Space>
      }
      extra={cardExtra}
      style={{ marginBottom: 16 }}
      data-testid="audit-filters-panel"
    >
      <Space wrap>
        <RangePicker
          size="large"
          style={{ minHeight: 44 }}
          presets={PERIOD_PRESETS}
          value={dateRange}
          onChange={(dates) => setDateRange(dates || [null, null])}
          placeholder={['Date début', 'Date fin']}
          allowClear
        />
        <Select
          size="large"
          style={{ width: 140, minHeight: 44 }}
          placeholder="Environnement"
          aria-label="Filtre Environnement"
          options={environmentOptions}
          loading={environmentsLoading}
          value={environment}
          onChange={setEnvironment}
          allowClear
          data-testid="audit-filter-environment"
        />
        <Select
          size="large"
          style={{ width: 160, minHeight: 44 }}
          placeholder="Moteur"
          aria-label="Filtre Moteur (engine_type)"
          options={engineOptions}
          value={engineType}
          onChange={setEngineType}
          allowClear
          loading={enginesLoading}
          data-testid="audit-filter-engine-type"
        />
        <Select
          size="large"
          style={{ width: 200, minHeight: 44 }}
          placeholder="Action"
          aria-label="Filtre Action"
          options={actions.map((a) => ({ label: a.name, value: a.id }))}
          value={actionId}
          onChange={(v) => setActionId(v ?? undefined)}
          allowClear
          showSearch
          optionFilterProp="label"
          loading={actionsLoading}
          data-testid="audit-filter-action"
        />
        <Select
          size="large"
          style={{ width: 120, minHeight: 44 }}
          placeholder="Statut"
          options={STATUS_OPTIONS}
          value={status}
          onChange={setStatus}
          allowClear
        />
        <Select
          size="large"
          style={{ width: 220, minHeight: 44 }}
          placeholder="Opération"
          aria-label="Filtre Opération (action_type)"
          options={ACTION_TYPE_OPTIONS}
          value={actionType}
          onChange={(v) => setActionType(v ?? undefined)}
          allowClear
          showSearch
          optionFilterProp="label"
          disabled={loading}
          data-testid="audit-filter-action-type"
        />
        <Input
          size="large"
          style={{ width: 200, minHeight: 44 }}
          placeholder="Rechercher un utilisateur"
          aria-label="Recherche utilisateur"
          value={userSearchInput}
          onChange={(e) => setUserSearchInput(e.target.value)}
          allowClear
          data-testid="audit-filter-user-search"
        />
        <Tooltip title="Rechercher toutes les traces d'une exécution par son identifiant de corrélation">
          <Input
            size="large"
            style={{ width: 220, minHeight: 44 }}
            placeholder="Correlation ID"
            value={correlationId}
            onChange={(e) => setCorrelationId(e.target.value)}
            allowClear
            data-testid="audit-filter-correlation-id"
          />
        </Tooltip>
        {correlationId && (
          <Tag closable onClose={() => setCorrelationId('')} color="blue">
            Correlation: {correlationId}
          </Tag>
        )}
      </Space>
    </Card>
  );
}

export default AuditFiltersPanel;
