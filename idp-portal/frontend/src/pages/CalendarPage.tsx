/**
 * CalendarPage - Calendar view for scheduled executions (Story 13.6).
 *
 * AC1: Menu Calendrier visible for DBA/DBOPS
 * AC2: Real calendar view (week/month) with executions positioned on date/time slots
 * AC3: Click/hover shows details popover
 * AC4: Filters aligned with ExecutionsFiltersPanel
 * AC5: URL persistence of filters
 * AC6: Scheduled executions appear in calendar
 * AC7: RBAC - DBA sees own executions, DBOPS sees all
 * AC8: Read-only for DBA (no cancel button)
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Typography, Spin, Alert, Popover, Tag, Space, Descriptions, theme, Segmented } from 'antd';
import { SyncOutlined, ClockCircleOutlined } from '@ant-design/icons';
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
import { useCalendarFilters } from '../hooks/useCalendarFilters';
import { listScheduledExecutions } from '../services/scheduled_execution_service';
import type { ScheduledExecutionListItem, ExecutionEnvironment, ScheduledExecutionFilters } from '../types/api';
import './CalendarPage.css';

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
  backgroundColor: string;
  borderColor: string;
  textColor: string;
  extendedProps: {
    execution: ScheduledExecutionListItem;
  };
}

/** Map scheduled execution to FullCalendar event. */
function mapToCalendarEvent(exec: ScheduledExecutionListItem): CalendarEvent {
  // For recurring, use next_execution_date; for one-time, use scheduled_at
  const effectiveDate = exec.recurring_pattern?.next_execution_date ?? exec.scheduled_at;
  const envColor = ENV_COLORS[exec.environment] ?? '#888';

  return {
    id: String(exec.scheduled_execution_id),
    title: exec.action_name,
    start: effectiveDate || '',
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
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, overflow: 'hidden' }}>
      {isRecurring && <SyncOutlined style={{ fontSize: 10 }} />}
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {eventInfo.event.title}
      </span>
    </div>
  );
}

/** Popover content for event details (AC3). */
function EventDetailsPopover({ execution }: { execution: ScheduledExecutionListItem }) {
  const effectiveDate = execution.recurring_pattern?.next_execution_date ?? execution.scheduled_at;
  const isRecurring = !!execution.recurring_pattern;

  return (
    <div style={{ maxWidth: 350 }} data-testid="event-details-popover">
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="Action">{execution.action_name}</Descriptions.Item>
        <Descriptions.Item label="Environnement">
          <Tag color={ENV_COLORS[execution.environment]}>
            {ENV_LABELS[execution.environment] ?? execution.environment}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Utilisateur">{execution.user_name}</Descriptions.Item>
        <Descriptions.Item label="Date/heure (UTC)">
          <Space>
            <ClockCircleOutlined />
            {effectiveDate ? dayjs.utc(effectiveDate).format('DD/MM/YYYY HH:mm') : '-'}
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
              {execution.status === 'pending' ? 'En attente' : execution.status === 'executed' ? 'Exécutée' : execution.status}
            </Tag>
          </Descriptions.Item>
        )}
      </Descriptions>
    </div>
  );
}

export function CalendarPage() {
  const { token } = theme.useToken();
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

  // Fetch scheduled executions (AC5: use URL date range when present, else calendar view range)
  const fetchExecutions = useCallback(async () => {
    setLoading(true);
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
        console.error('Failed to fetch scheduled executions:', err);
      }
    } finally {
      setLoading(false);
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
    // Use FullCalendar API to change view
    calendarRef.current?.getApi().changeView(newView);
  }, []);

  return (
    <div className="calendar-page" data-testid="calendar-page">
      <div style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>
          Calendrier des exécutions planifiées
        </Title>
        <Text type="secondary">
          Vue calendrier des exécutions planifiées (semaine/mois)
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

      {/* View Toggle */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'flex-end' }}>
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
            slotMinTime="06:00:00"
            slotMaxTime="22:00:00"
            allDaySlot={false}
            weekends
            navLinks={false}
            editable={false}
            selectable={false}
            eventDisplay="block"
          />
        </div>
      )}

      {/* Popover for event details (AC3) */}
      {selectedEvent && popoverPosition && (
        <Popover
          open
          content={<EventDetailsPopover execution={selectedEvent} />}
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
    </div>
  );
}

export default CalendarPage;
