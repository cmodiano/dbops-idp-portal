/**
 * CalendarPage - Calendar view for scheduled executions (Story 13.6, Story 13.8).
 *
 * AC1: Menu Calendrier visible for DBA/DBOPS
 * AC2: Real calendar view (week/month) with executions positioned on date/time slots
 * AC3: Click/hover shows details popover
 * AC4: Filters aligned with ExecutionsFiltersPanel
 * AC5: URL persistence of filters
 * AC6: Scheduled executions appear in calendar
 * AC7: RBAC - DBA sees own executions, DBOPS sees all
 * AC8: Read-only for DBA (no cancel button). Story 13.8: cancel/toggle for creator or DBOPS.
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Link } from 'react-router';
import { Typography, Spin, Alert, Popover, Tag, Space, Descriptions, theme, Segmented, Button, Modal, Switch, Form, DatePicker, Input, Select, Radio } from 'antd';
import { SyncOutlined, ClockCircleOutlined, LinkOutlined } from '@ant-design/icons';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import type { EventClickArg, EventContentArg, DatesSetArg } from '@fullcalendar/core';
import frLocale from '@fullcalendar/core/locales/fr';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';

import { CalendarFiltersPanel } from '../components/calendar/CalendarFiltersPanel';
import { useAuth } from '../contexts/AuthContext';
import { useCalendarFilters } from '../hooks/useCalendarFilters';
import { listScheduledExecutions, cancelScheduledExecution, toggleRecurringPattern, updateScheduledExecution } from '../services/scheduled_execution_service';
import { fetchInventoryTargets } from '../services/execution_service';
import { ApiError } from '../services/api_client';
import type { ScheduledExecutionListItem, ExecutionEnvironment, ScheduledExecutionFilters, ScheduledExecutionUpdateRequest } from '../types/api';
import { formatUtcToLocal } from '../utils/dateFormat';
import { notification } from 'antd';
import './CalendarPage.css';
import logger from '../services/logger';

dayjs.extend(utc);
dayjs.extend(timezone);

const { Title, Text } = Typography;

/** Environment color mapping (AC2). */
const ENV_COLORS: Record<ExecutionEnvironment, string> = {
  dev: '#1890ff',
  staging: '#fa8c16',
  prod: '#f5222d',
};

/** Environment labels. */
const ENV_LABELS: Record<ExecutionEnvironment, string> = {
  dev: 'Développement',
  staging: 'Staging',
  prod: 'Production',
};

/** Calendar event with extended props. */
interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end?: string;
  allDay?: boolean;
  backgroundColor: string;
  borderColor: string;
  textColor: string;
  extendedProps: {
    execution: ScheduledExecutionListItem;
  };
}

/** Normalise une date ISO en UTC pour parsing (évite interprétation locale). */
function toUtcIso(dateStr: string): string {
  if (!dateStr || typeof dateStr !== 'string') return dateStr;
  const trimmed = dateStr.trim();
  if (/Z$/.test(trimmed) || /[+-]\d{2}:?\d{2}$/.test(trimmed)) return trimmed;
  return trimmed + 'Z';
}

/** Map scheduled execution to FullCalendar event. */
function mapToCalendarEvent(exec: ScheduledExecutionListItem): CalendarEvent {
  // For recurring, use next_execution_date; for one-time, use scheduled_at
  const effectiveDate = exec.recurring_pattern?.next_execution_date ?? exec.scheduled_at;
  const envColor = ENV_COLORS[exec.environment] ?? '#888';
  if (!effectiveDate) {
    return {
      id: String(exec.scheduled_execution_id),
      title: exec.action_name,
      start: '',
      backgroundColor: envColor,
      borderColor: envColor,
      textColor: '#fff',
      extendedProps: { execution: exec },
    };
  }
  // API renvoie des dates UTC ; forcer l'interprétation UTC pour éviter décalage heure
  const utcIso = toUtcIso(effectiveDate);
  const parsed = dayjs.utc(utcIso);
  const hasTime = effectiveDate.includes('T') && /T\d{1,2}:\d{2}/.test(effectiveDate);
  const startMoment = hasTime ? parsed : parsed.hour(9).minute(0).second(0).millisecond(0);
  const startStr = startMoment.toISOString();
  const endStr = startMoment.add(1, 'hour').toISOString();

  return {
    id: String(exec.scheduled_execution_id),
    title: exec.action_name,
    start: startStr,
    end: endStr,
    allDay: false,
    backgroundColor: envColor,
    borderColor: envColor,
    textColor: '#fff',
    extendedProps: { execution: exec },
  };
}

/** Describe pattern type in French. */
function describePatternType(exec: ScheduledExecutionListItem): string {
  if (!exec.recurring_pattern) return 'Unique';
  const { pattern_type } = exec.recurring_pattern;
  switch (pattern_type) {
    case 'daily':
      return 'Quotidien';
    case 'weekly':
      return 'Hebdomadaire';
    case 'cron':
      return 'Cron';
    default:
      return 'Récurrent';
  }
}

/** Event content with recurring indicator. */
function EventContent({ eventInfo }: { eventInfo: EventContentArg }) {
  const exec = eventInfo.event.extendedProps.execution as ScheduledExecutionListItem;
  const isRecurring = !!exec.recurring_pattern;

  return (
    <div
      style={{ display: 'flex', alignItems: 'center', gap: 4, overflow: 'hidden' }}
      data-testid="calendar-event"
    >
      {isRecurring && <SyncOutlined style={{ fontSize: 10 }} />}
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {eventInfo.event.title}
      </span>
    </div>
  );
}

/** Extract display params (exclude technical keys _targets, _env_config). Story 13.8 AC1. Exported for tests. */
export function getDisplayParameters(parameters: Record<string, unknown> | null): Record<string, unknown> {
  if (!parameters || typeof parameters !== 'object') return {};
  return Object.fromEntries(
    Object.entries(parameters).filter(([key]) => !key.startsWith('_'))
  );
}

/** Popover content for event details (AC3 Story 13.6; Story 13.8 AC1–AC4: targets, params, link, cancel, edit, toggle). Exported for tests. */
export interface EventDetailsPopoverProps {
  execution: ScheduledExecutionListItem;
  onRequestCancel?: (exec: ScheduledExecutionListItem) => void;
  onRequestEdit?: (exec: ScheduledExecutionListItem) => void;
  onToggleRecurrence?: (id: number, currentState: boolean) => void;
  cancelLoading?: boolean;
  editLoading?: boolean;
  togglingPatternId?: number | null;
}

export function EventDetailsPopover({
  execution,
  onRequestCancel,
  onRequestEdit,
  onToggleRecurrence,
  cancelLoading = false,
  editLoading = false,
  togglingPatternId = null,
}: EventDetailsPopoverProps) {
  const { user } = useAuth();
  const effectiveDate = execution.recurring_pattern?.next_execution_date ?? execution.scheduled_at;
  const isRecurring = !!execution.recurring_pattern;
  const targets = (execution.parameters?._targets as string[] | undefined) ?? [];
  const hasTargets = Array.isArray(targets) && targets.length > 0;
  const displayParams = getDisplayParameters(execution.parameters ?? null);
  const hasDisplayParams = Object.keys(displayParams).length > 0;
  const showExecutionLink =
    execution.status === 'executed' &&
    execution.execution_id != null;
  const isDbops = user?.profile?.toLowerCase() === 'dbops';
  const canCancel =
    execution.status === 'pending' &&
    onRequestCancel != null &&
    (execution.user_id === user?.id || isDbops);
  const canEdit =
    execution.status === 'pending' &&
    onRequestEdit != null &&
    (execution.user_id === user?.id || isDbops);
  const showRecurrenceToggle =
    isDbops &&
    isRecurring &&
    execution.recurring_pattern != null &&
    onToggleRecurrence != null;
  const toggling = togglingPatternId === execution.scheduled_execution_id;

  return (
    <div style={{ maxWidth: 400 }} data-testid="event-details-popover">
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="Action">
          {execution.action_name}
          {execution.action_id != null && (
            <Text type="secondary" style={{ marginLeft: 8 }}>(ID {execution.action_id})</Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="Environnement">
          <Tag color={ENV_COLORS[execution.environment]}>
            {ENV_LABELS[execution.environment] ?? execution.environment}
          </Tag>
        </Descriptions.Item>
        {hasTargets && (
          <Descriptions.Item label="Targets">
            <Space size={[0, 4]} wrap>
              {targets.map((t) => (
                <Tag key={t} color="blue">{t}</Tag>
              ))}
            </Space>
          </Descriptions.Item>
        )}
        {hasDisplayParams && (
          <Descriptions.Item label="Paramètres">
            <pre
              style={{
                margin: 0,
                padding: 8,
                fontSize: 12,
                maxWidth: 360,
                overflow: 'auto',
                background: 'var(--ant-color-fill-quaternary)',
                borderRadius: 4,
              }}
              data-testid="popover-parameters"
            >
              {JSON.stringify(displayParams, null, 2)}
            </pre>
          </Descriptions.Item>
        )}
        <Descriptions.Item label="Utilisateur">
          {execution.user_name}
          {execution.user_id != null && (
            <Text type="secondary" style={{ marginLeft: 8 }}>(ID {execution.user_id})</Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="Date/heure">
          <Space>
            <ClockCircleOutlined />
            {formatUtcToLocal(effectiveDate ?? null)}
          </Space>
        </Descriptions.Item>
        <Descriptions.Item label="Type">
          <Space>
            {isRecurring && <SyncOutlined />}
            {describePatternType(execution)}
          </Space>
        </Descriptions.Item>
        {execution.platform != null && execution.platform !== '' && (
          <Descriptions.Item label="Plateforme">{execution.platform}</Descriptions.Item>
        )}
        {execution.engine != null && execution.engine !== '' && (
          <Descriptions.Item label="Technologie">{execution.engine}</Descriptions.Item>
        )}
        {execution.status && (
          <Descriptions.Item label="Statut">
            <Tag color={execution.status === 'pending' ? 'blue' : execution.status === 'executed' ? 'green' : 'default'}>
              {execution.status === 'pending' ? 'En attente' : execution.status === 'executed' ? 'Exécutée' : execution.status === 'cancelled' ? 'Annulée' : execution.status}
            </Tag>
          </Descriptions.Item>
        )}
        {showExecutionLink && (
          <Descriptions.Item label="Exécution">
            <Link to={`/executions/${execution.execution_id}`} data-testid="link-to-execution">
              <LinkOutlined /> Voir l'exécution
            </Link>
          </Descriptions.Item>
        )}
      </Descriptions>
      {showRecurrenceToggle && (
        <div style={{ marginTop: 12 }}>
          <Space>
            <Switch
              checked={execution.recurring_pattern?.is_active ?? false}
              onChange={() =>
                onToggleRecurrence?.(execution.scheduled_execution_id, !(execution.recurring_pattern?.is_active ?? false))
              }
              loading={toggling}
              data-testid="recurrence-toggle"
            />
            <span data-testid="recurrence-toggle-label">
              {execution.recurring_pattern?.is_active ? 'Récurrence active' : 'Récurrence inactive'}
            </span>
          </Space>
        </div>
      )}
      {(canCancel || canEdit) && (
        <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          {canEdit && (
            <Button
              type="default"
              loading={editLoading}
              onClick={() => onRequestEdit?.(execution)}
              data-testid="edit-execution-btn"
            >
              Modifier
            </Button>
          )}
          {canCancel && (
            <Button
              type="primary"
              danger
              loading={cancelLoading}
              onClick={() => onRequestCancel?.(execution)}
              data-testid="cancel-execution-btn"
            >
              Annuler
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

export function CalendarPage() {
  const { token } = theme.useToken();
  const { user } = useAuth();
  const { filters, applyFilters, resetFilters, activeFilterCount } = useCalendarFilters();
  const calendarRef = useRef<FullCalendar>(null);

  const [executions, setExecutions] = useState<ScheduledExecutionListItem[]>([]);
  const [availableActions, setAvailableActions] = useState<{ action_id: number; action_name: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<ScheduledExecutionListItem | null>(null);
  const [popoverPosition, setPopoverPosition] = useState<{ x: number; y: number } | null>(null);
  const [calendarView, setCalendarView] = useState<'timeGridWeek' | 'dayGridMonth'>('timeGridWeek');
  const [dateRange, setDateRange] = useState<{ start: string; end: string } | null>(null);
  const [executionToCancel, setExecutionToCancel] = useState<ScheduledExecutionListItem | null>(null);
  const [cancelModalVisible, setCancelModalVisible] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [executionToEdit, setExecutionToEdit] = useState<ScheduledExecutionListItem | null>(null);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [editForm] = Form.useForm();
  const [targetOptions, setTargetOptions] = useState<{ label: string; value: string }[]>([]);
  const [togglingPatternId, setTogglingPatternId] = useState<number | null>(null);
  const initialLoadDone = useRef(false);

  // Fetch scheduled executions (AC5: use URL date range when present, else calendar view range)
  const fetchExecutions = useCallback(async () => {
    // Ne pas afficher le spinner lors des refetch (changement de semaine/mois), sinon le calendrier se démonte et prev/next semblent ne pas marcher
    if (!initialLoadDone.current) {
      setLoading(true);
    }
    setError(null);
    try {
      const apiFilters: ScheduledExecutionFilters = {};
      if (filters.action_id != null && !Number.isNaN(filters.action_id)) apiFilters.action_id = filters.action_id;
      if (filters.environment) apiFilters.environment = filters.environment;
      if (filters.engine) apiFilters.engine = filters.engine;
      if (filters.platform) apiFilters.platform = filters.platform;
      // AC5: Apply date range from URL first; fallback to calendar view range (dateRange)
      if (filters.start_date && filters.end_date) {
        apiFilters.scheduled_from = filters.start_date;
        apiFilters.scheduled_to = filters.end_date;
      } else if (dateRange) {
        apiFilters.scheduled_from = dateRange.start;
        apiFilters.scheduled_to = dateRange.end;
      }

      const response = await listScheduledExecutions(apiFilters, 100, 0);
      setExecutions(response.data);
      if (response.available_actions) {
        setAvailableActions(response.available_actions);
      }
    } catch (err) {
      setError('Erreur lors du chargement des exécutions planifiées');
      if (import.meta.env.DEV) {
        logger.error('Failed to fetch scheduled executions', { error: err instanceof Error ? err.message : String(err) });
      }
    } finally {
      setLoading(false);
      initialLoadDone.current = true;
    }
  }, [filters.action_id, filters.environment, filters.engine, filters.platform, filters.start_date, filters.end_date, dateRange]);

  useEffect(() => {
    fetchExecutions();
  }, [fetchExecutions]);

  // Map to calendar events (filtering now done server-side)
  const calendarEvents: CalendarEvent[] = useMemo(() => {
    return executions
      .filter((exec) => exec.status === 'pending') // Only show pending executions
      .filter((exec) => {
        const effectiveDate = exec.recurring_pattern?.next_execution_date ?? exec.scheduled_at;
        return effectiveDate; // Must have a date to display
      })
      .map(mapToCalendarEvent);
  }, [executions]);

  // Handle event click (AC3)
  const handleEventClick = useCallback((info: EventClickArg) => {
    const execution = info.event.extendedProps.execution as ScheduledExecutionListItem;
    setSelectedEvent(execution);
    // Position popover near click
    const rect = info.el.getBoundingClientRect();
    setPopoverPosition({ x: rect.left + rect.width / 2, y: rect.top });
  }, []);

  // Handle dates change to fetch appropriate range
  const handleDatesSet = useCallback((dateInfo: DatesSetArg) => {
    const newStart = dayjs(dateInfo.start).format('YYYY-MM-DD');
    const newEnd = dayjs(dateInfo.end).format('YYYY-MM-DD');
    setDateRange((prev) => {
      // Avoid infinite loop: only update if dates actually changed
      if (prev && prev.start === newStart && prev.end === newEnd) {
        return prev;
      }
      return { start: newStart, end: newEnd };
    });
  }, []);

  // Close popover
  const closePopover = useCallback(() => {
    setSelectedEvent(null);
    setPopoverPosition(null);
  }, []);

  // View toggle handler
  const handleViewChange = useCallback((view: string) => {
    const newView = view as 'timeGridWeek' | 'dayGridMonth';
    setCalendarView(newView);
    calendarRef.current?.getApi().changeView(newView);
  }, []);

  // Story 13.8 AC2: Request cancel -> open confirmation modal
  const handleRequestCancel = useCallback((exec: ScheduledExecutionListItem) => {
    setExecutionToCancel(exec);
    setCancelModalVisible(true);
  }, []);

  // Story 13.8 AC2: Confirm cancel and call API
  const handleConfirmCancel = useCallback(async () => {
    if (!executionToCancel) return;
    setCancelLoading(true);
    try {
      await cancelScheduledExecution(executionToCancel.scheduled_execution_id);
      notification.success({
        message: 'Succès',
        description: 'Exécution planifiée annulée avec succès',
      });
      setCancelModalVisible(false);
      setExecutionToCancel(null);
      closePopover();
      fetchExecutions();
    } catch (err: unknown) {
      const status = err instanceof ApiError ? err.status : undefined;
      const msg = (err as Error).message ?? '';
      if (status === 403 || (!status && (msg.includes('permission') || msg.includes('refusée') || msg.includes('Permission')))) {
        notification.error({
          message: 'Permission refusée',
          description: "Vous n'avez pas la permission d'annuler cette exécution",
        });
      } else if (status === 400 || (!status && (msg.includes('attente') || msg.includes('modifiées') || msg.includes('status') || msg.includes('INVALID')))) {
        notification.error({
          message: 'Erreur',
          description: 'Cette exécution ne peut plus être annulée',
        });
      } else {
        notification.error({
          message: 'Erreur',
          description: msg || "Une erreur est survenue lors de l'annulation",
        });
      }
    } finally {
      setCancelLoading(false);
    }
  }, [executionToCancel, closePopover, fetchExecutions]);

  // Story 13.8 AC4: Request edit -> open edit modal
  const handleRequestEdit = useCallback((exec: ScheduledExecutionListItem) => {
    setExecutionToEdit(exec);
    setEditModalVisible(true);
    const targets = (exec.parameters?._targets as string[] | undefined) ?? [];
    const rp = exec.recurring_pattern;
    const pc = rp?.pattern_config as { hour?: number; minute?: number; day_of_week?: number; cron_expression?: string } | undefined;
    editForm.setFieldsValue({
      scheduled_at: exec.scheduled_at ? dayjs.utc(exec.scheduled_at) : undefined,
      parameters_json: JSON.stringify(getDisplayParameters(exec.parameters ?? null), null, 2),
      target_names: Array.isArray(targets) ? targets : [],
      environment: exec.environment,
      pattern_type: rp?.pattern_type ?? 'daily',
      pattern_hour: pc?.hour ?? 0,
      pattern_minute: pc?.minute ?? 0,
      pattern_day_of_week: pc?.day_of_week ?? 1,
      cron_expression: pc?.cron_expression ?? '',
    });
  }, [editForm]);

  // Load target options when edit modal opens (only when authenticated to avoid 401)
  useEffect(() => {
    if (!editModalVisible || !executionToEdit || !user) return;
    fetchInventoryTargets()
      .then((items) => setTargetOptions(items.map((t) => ({ label: `${t.name} (${t.environment})`, value: t.name }))))
      .catch(() => setTargetOptions([]));
  }, [editModalVisible, executionToEdit, user]);

  // Story 13.8 AC4: Submit edit
  const handleSubmitEdit = useCallback(async () => {
    if (!executionToEdit) return;
    try {
      const values = await editForm.validateFields();
      const payload: ScheduledExecutionUpdateRequest = {};
      const isRecurring = !!executionToEdit.recurring_pattern;

      if (!isRecurring && values.scheduled_at) {
        payload.scheduled_at = values.scheduled_at.utc().format();
      }
      if (values.parameters_json) {
        try {
          const parsed = JSON.parse(values.parameters_json as string);
          if (parsed && typeof parsed === 'object') {
            const existing = executionToEdit.parameters ?? {};
            payload.parameters = { ...existing, ...parsed };
          }
        } catch {
          // keep existing params if JSON invalid
        }
      }
      if (values.target_names != null && Array.isArray(values.target_names)) {
        payload.target_names = values.target_names;
      }
      if (payload.target_names == null && values.environment) {
        payload.environment = values.environment as ExecutionEnvironment;
      }
      if (isRecurring && values.pattern_type) {
        const patternType = values.pattern_type as 'daily' | 'weekly' | 'cron';
        if (patternType === 'cron' && values.cron_expression) {
          payload.recurring_pattern = { pattern_type: 'cron', pattern_config: { cron_expression: values.cron_expression } };
        } else if (patternType === 'daily') {
          payload.recurring_pattern = {
            pattern_type: 'daily',
            pattern_config: { hour: values.pattern_hour ?? 0, minute: values.pattern_minute ?? 0 },
          };
        } else if (patternType === 'weekly') {
          payload.recurring_pattern = {
            pattern_type: 'weekly',
            pattern_config: {
              day_of_week: values.pattern_day_of_week ?? 1,
              hour: values.pattern_hour ?? 0,
              minute: values.pattern_minute ?? 0,
            },
          };
        }
      }

      setEditLoading(true);
      await updateScheduledExecution(executionToEdit.scheduled_execution_id, payload);
      notification.success({ message: 'Succès', description: 'Exécution planifiée modifiée avec succès' });
      setEditModalVisible(false);
      setExecutionToEdit(null);
      closePopover();
      fetchExecutions();
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'errorFields' in err) return; // form validation
      const apiErr = err instanceof ApiError ? err : null;
      const status = apiErr?.status;
      const msg = (err as Error).message ?? '';
      const errorBody = apiErr?.responseBody?.error;
      const description = (errorBody?.message ?? msg) || "Une erreur est survenue lors de la modification";
      if (status === 400 && errorBody?.details && typeof errorBody.details === 'object') {
        const details = errorBody.details as Record<string, unknown>;
        editForm.setFields(
          Object.entries(details).map(([name, value]) => ({
            name,
            errors: [typeof value === 'string' ? value : JSON.stringify(value)],
          }))
        );
      }
      if (status === 403) {
        notification.error({ message: 'Permission refusée', description: "Vous n'avez pas la permission de modifier cette exécution planifiée" });
      } else if (status === 404) {
        notification.error({ message: 'Erreur', description: 'Exécution planifiée introuvable' });
      } else if (status === 400) {
        notification.error({ message: 'Erreur de validation', description });
      } else {
        notification.error({ message: 'Erreur', description });
      }
    } finally {
      setEditLoading(false);
    }
  }, [executionToEdit, editForm, closePopover, fetchExecutions]);

  // Story 13.8 AC3: Toggle recurrence (DBOPS)
  const handleToggleRecurrence = useCallback(
    async (id: number, newState: boolean) => {
      setTogglingPatternId(id);
      try {
        await toggleRecurringPattern(id, newState);
        notification.success({
          message: newState ? 'Récurrence activée' : 'Récurrence désactivée',
          description: newState
            ? 'La récurrence a été activée avec succès'
            : 'La récurrence a été désactivée avec succès',
        });
        fetchExecutions();
      } catch (err: unknown) {
        const msg = (err as Error).message ?? '';
        notification.error({
          message: 'Erreur',
          description: msg || 'Une erreur est survenue',
        });
      } finally {
        setTogglingPatternId(null);
      }
    },
    [fetchExecutions]
  );

  return (
    <div className="calendar-page" data-testid="calendar-page">
      <div style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>
          Calendrier des exécutions planifiées
        </Title>
        <Text type="secondary">
          Vue calendrier des exécutions planifiées (semaine/mois) — Heures en heure locale
        </Text>
      </div>

      {/* Filters Panel (AC4, AC5) */}
      <CalendarFiltersPanel
        filters={filters}
        onApplyFilters={applyFilters}
        onResetFilters={resetFilters}
        activeFilterCount={activeFilterCount}
        loading={loading}
        availableActions={availableActions}
      />

      {/* View Toggle + Légende environnements */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <Space size="middle" wrap data-testid="calendar-legend">
          <Text type="secondary">Environnement :</Text>
          {(['dev', 'staging', 'prod'] as const).map((env) => (
            <Space key={env} size={8}>
              <span
                style={{
                  display: 'inline-block',
                  width: 12,
                  height: 12,
                  borderRadius: 2,
                  backgroundColor: ENV_COLORS[env],
                }}
                aria-hidden
              />
              <span>{ENV_LABELS[env]}</span>
            </Space>
          ))}
        </Space>
        <Segmented
          value={calendarView}
          onChange={handleViewChange}
          options={[
            { label: 'Semaine', value: 'timeGridWeek' },
            { label: 'Mois', value: 'dayGridMonth' },
          ]}
          data-testid="view-toggle"
        />
      </div>

      {/* Error Alert */}
      {error && (
        <Alert
          type="error"
          message={error}
          showIcon
          closable
          style={{ marginBottom: 16 }}
          data-testid="error-alert"
        />
      )}

      {/* Loading Spinner */}
      {loading && (
        <div style={{ textAlign: 'center', padding: 48 }} data-testid="loading-spinner">
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>
            <Text type="secondary">Chargement du calendrier...</Text>
          </div>
        </div>
      )}

      {/* Calendar View (AC2) */}
      {!loading && (
        <div
          className="calendar-container"
          style={{
            background: token.colorBgContainer,
            borderRadius: token.borderRadiusLG,
            padding: 16,
          }}
          data-testid="calendar-container"
        >
          <FullCalendar
            ref={calendarRef}
            plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
            initialView={calendarView}
            headerToolbar={{
              left: 'prev,next today',
              center: 'title',
              right: '',
            }}
            locale={frLocale}
            height="auto"
            events={calendarEvents}
            eventClick={handleEventClick}
            eventContent={(eventInfo) => <EventContent eventInfo={eventInfo} />}
            datesSet={handleDatesSet}
            nowIndicator
            slotMinTime="00:00:00"
            slotMaxTime="24:00:00"
            allDaySlot={false}
            weekends
            navLinks={false}
            editable={false}
            selectable={false}
            eventDisplay="block"
          />
        </div>
      )}

      {/* Popover for event details (AC3, Story 13.8) */}
      {selectedEvent && popoverPosition && (
        <Popover
          open
          content={
            <EventDetailsPopover
              execution={selectedEvent}
              onRequestCancel={handleRequestCancel}
              onRequestEdit={handleRequestEdit}
              onToggleRecurrence={handleToggleRecurrence}
              cancelLoading={cancelLoading}
              editLoading={editLoading}
              togglingPatternId={togglingPatternId}
            />
          }
          title={selectedEvent.action_name}
          placement="top"
          onOpenChange={(open) => {
            if (!open) closePopover();
          }}
          trigger="click"
        >
          <div
            style={{
              position: 'fixed',
              left: popoverPosition.x,
              top: popoverPosition.y,
              width: 1,
              height: 1,
            }}
          />
        </Popover>
      )}

      {/* Modal confirmation annulation (Story 13.8 AC2) — zIndex au-dessus du Popover */}
      <Modal
        title="Confirmer l'annulation"
        open={cancelModalVisible}
        zIndex={1100}
        onCancel={() => {
          setCancelModalVisible(false);
          setExecutionToCancel(null);
        }}
        footer={[
          <Button key="back" onClick={() => setCancelModalVisible(false)}>
            Annuler
          </Button>,
          <Button
            key="confirm"
            type="primary"
            danger
            loading={cancelLoading}
            onClick={handleConfirmCancel}
            data-testid="confirm-cancel-execution-btn"
          >
            Confirmer l'annulation
          </Button>,
        ]}
        data-testid="cancel-execution-modal"
      >
        {executionToCancel && (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="Action">{executionToCancel.action_name}</Descriptions.Item>
            <Descriptions.Item label="Date planifiée">
              {formatUtcToLocal(executionToCancel.recurring_pattern?.next_execution_date ?? executionToCancel.scheduled_at ?? null)}
            </Descriptions.Item>
            <Descriptions.Item label="Utilisateur">{executionToCancel.user_name}</Descriptions.Item>
            <Descriptions.Item label="Environnement">
              <Tag color={ENV_COLORS[executionToCancel.environment]}>
                {ENV_LABELS[executionToCancel.environment] ?? executionToCancel.environment}
              </Tag>
            </Descriptions.Item>
          </Descriptions>
        )}
        {executionToCancel?.recurring_pattern && (
          <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
            Il s'agit d'une annulation de l'occurrence unique (la récurrence reste active).
          </Text>
        )}
      </Modal>

      {/* Modal modification (Story 13.8 AC4) */}
      <Modal
        title="Modifier l'exécution planifiée"
        open={editModalVisible}
        zIndex={1100}
        onCancel={() => {
          setEditModalVisible(false);
          setExecutionToEdit(null);
        }}
        footer={[
          <Button key="back" onClick={() => setEditModalVisible(false)}>
            Annuler
          </Button>,
          <Button key="submit" type="primary" loading={editLoading} onClick={() => handleSubmitEdit()} data-testid="confirm-edit-execution-btn">
            Enregistrer
          </Button>,
        ]}
        width={560}
        data-testid="edit-execution-modal"
      >
        {executionToEdit && (
          <Form form={editForm} layout="vertical">
            {!executionToEdit.recurring_pattern ? (
              <Form.Item name="scheduled_at" label="Date/heure planifiée (UTC)" rules={[{ required: true, message: 'Requis' }]}>
                <DatePicker showTime format="DD/MM/YYYY HH:mm" style={{ width: '100%' }} disabledDate={(d) => d && d.isBefore(dayjs().startOf('minute'))} />
              </Form.Item>
            ) : (
              <>
                <Form.Item name="pattern_type" label="Type de récurrence">
                  <Radio.Group options={[{ label: 'Quotidien', value: 'daily' }, { label: 'Hebdomadaire', value: 'weekly' }, { label: 'Cron', value: 'cron' }]} />
                </Form.Item>
                <Form.Item noStyle shouldUpdate={(prev, curr) => prev?.pattern_type !== curr?.pattern_type}>
                  {({ getFieldValue }) =>
                    getFieldValue('pattern_type') === 'cron' ? (
                      <Form.Item name="cron_expression" label="Expression cron">
                        <Input placeholder="0 9 * * 1-5" />
                      </Form.Item>
                    ) : (
                      <Space>
                        {getFieldValue('pattern_type') === 'weekly' && (
                          <Form.Item name="pattern_day_of_week" label="Jour (1=Lu, 7=Di)">
                            <Select options={[1, 2, 3, 4, 5, 6, 7].map((d) => ({ label: ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'][d - 1], value: d }))} style={{ width: 100 }} />
                          </Form.Item>
                        )}
                        <Form.Item name="pattern_hour" label="Heure (UTC)">
                          <Select options={Array.from({ length: 24 }, (_, i) => ({ label: i.toString().padStart(2, '0'), value: i }))} style={{ width: 70 }} />
                        </Form.Item>
                        <Form.Item name="pattern_minute" label="Minute">
                          <Select options={Array.from({ length: 60 }, (_, i) => ({ label: i.toString().padStart(2, '0'), value: i }))} style={{ width: 70 }} />
                        </Form.Item>
                      </Space>
                    )
                  }
                </Form.Item>
              </>
            )}
            <Form.Item name="target_names" label="Targets">
              <Select mode="multiple" placeholder="Sélectionner les targets" options={targetOptions} allowClear showSearch optionFilterProp="label" />
            </Form.Item>
            <Form.Item name="environment" label="Environnement (si pas de targets)">
              <Select options={[{ label: ENV_LABELS.dev, value: 'dev' }, { label: ENV_LABELS.staging, value: 'staging' }, { label: ENV_LABELS.prod, value: 'prod' }]} />
            </Form.Item>
            <Form.Item name="parameters_json" label="Paramètres (JSON)">
              <Input.TextArea rows={4} placeholder='{"key": "value"}' />
            </Form.Item>
          </Form>
        )}
      </Modal>
    </div>
  );
}

export default CalendarPage;
