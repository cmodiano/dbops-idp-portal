/**
 * CalendarPage - Calendar view for scheduled executions (Story 13.6, Story 13.8).
 * Refactored in Story 26.6: extracted utils, hooks, and components.
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { App, Typography, Spin, Alert, Popover, Space, theme, Segmented } from 'antd';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import frLocale from '@fullcalendar/core/locales/fr';

import { CalendarFiltersPanel } from '../components/calendar/CalendarFiltersPanel';
import { CalendarEventContent } from '../components/calendar/CalendarEventContent';
import { EventDetailsPopover } from '../components/calendar/EventDetailsPopover';
import { CancelExecutionModal } from '../components/calendar/CancelExecutionModal';
import { EditExecutionModal } from '../components/calendar/EditExecutionModal';
import { useCalendarFilters } from '../hooks/useCalendarFilters';
import { useCalendarState } from '../hooks/useCalendarState';
import { useCancelExecution } from '../hooks/useCancelExecution';
import { useEditExecution } from '../hooks/useEditExecution';
import { listScheduledExecutions, toggleRecurringPattern } from '../services/scheduled_execution_service';
import { ENV_COLORS, ENV_LABELS, mapToCalendarEvent } from '../utils/calendarEventUtils';
import type { CalendarEvent } from '../utils/calendarEventUtils';
import type { ScheduledExecutionListItem, ScheduledExecutionFilters } from '../types/api';
import './CalendarPage.css';
import logger from '../services/logger';

const { Title, Text } = Typography;

export function CalendarPage() {
  const { notification } = App.useApp();
  const { token } = theme.useToken();
  const { filters, applyFilters, resetFilters, activeFilterCount } = useCalendarFilters();

  const {
    calendarRef,
    selectedEvent,
    popoverPosition,
    calendarView,
    dateRange,
    handleEventClick,
    handleDatesSet,
    closePopover,
    handleViewChange,
  } = useCalendarState();

  const [executions, setExecutions] = useState<ScheduledExecutionListItem[]>([]);
  const [availableActions, setAvailableActions] = useState<{ action_id: number; action_name: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [togglingPatternId, setTogglingPatternId] = useState<number | null>(null);
  const initialLoadDone = useRef(false);

  const fetchExecutions = useCallback(async () => {
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

  const {
    executionToCancel,
    cancelModalVisible,
    cancelLoading,
    openCancelModal,
    closeCancelModal,
    confirmCancel,
  } = useCancelExecution(fetchExecutions, closePopover);

  const {
    executionToEdit,
    editModalVisible,
    editLoading,
    editForm,
    targetOptions,
    openEditModal,
    closeEditModal,
    submitEdit,
  } = useEditExecution(fetchExecutions, closePopover);

  const calendarEvents: CalendarEvent[] = useMemo(() => {
    return executions
      .filter((exec) => exec.status === 'pending')
      .filter((exec) => exec.recurring_pattern?.next_execution_date ?? exec.scheduled_at)
      .map(mapToCalendarEvent);
  }, [executions]);

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
    [fetchExecutions, notification]
  );

  return (
    <div className="calendar-page" data-testid="calendar-page">
      <div style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Calendrier des exécutions planifiées</Title>
        <Text type="secondary">Vue calendrier des exécutions planifiées (semaine/mois) — Heures en heure locale</Text>
      </div>

      <CalendarFiltersPanel
        filters={filters}
        onApplyFilters={applyFilters}
        onResetFilters={resetFilters}
        activeFilterCount={activeFilterCount}
        loading={loading}
        availableActions={availableActions}
      />

      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <Space size="middle" wrap data-testid="calendar-legend">
          <Text type="secondary">Environnement :</Text>
          {(['dev', 'staging', 'prod'] as const).map((env) => (
            <Space key={env} size={8}>
              <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: 2, backgroundColor: ENV_COLORS[env] }} aria-hidden />
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

      {error && (
        <Alert type="error" title={error} showIcon closable style={{ marginBottom: 16 }} data-testid="error-alert" />
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: 48 }} data-testid="loading-spinner">
          <Spin size="large" />
          <div style={{ marginTop: 16 }}><Text type="secondary">Chargement du calendrier...</Text></div>
        </div>
      )}

      {!loading && (
        <div
          className="calendar-container"
          style={{ background: token.colorBgContainer, borderRadius: token.borderRadiusLG, padding: 16 }}
          data-testid="calendar-container"
        >
          <FullCalendar
            ref={calendarRef}
            plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
            initialView={calendarView}
            headerToolbar={{ left: 'prev,next today', center: 'title', right: '' }}
            locale={frLocale}
            height="auto"
            events={calendarEvents}
            eventClick={handleEventClick}
            eventContent={(eventInfo) => <CalendarEventContent eventInfo={eventInfo} />}
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

      {selectedEvent && popoverPosition && (
        <Popover
          open
          content={
            <EventDetailsPopover
              execution={selectedEvent}
              onRequestCancel={openCancelModal}
              onRequestEdit={openEditModal}
              onToggleRecurrence={handleToggleRecurrence}
              cancelLoading={cancelLoading}
              editLoading={editLoading}
              togglingPatternId={togglingPatternId}
            />
          }
          title={selectedEvent.action_name}
          placement="top"
          onOpenChange={(open) => { if (!open) closePopover(); }}
          trigger="click"
        >
          <div style={{ position: 'fixed', left: popoverPosition.x, top: popoverPosition.y, width: 1, height: 1 }} />
        </Popover>
      )}

      <CancelExecutionModal
        execution={executionToCancel}
        open={cancelModalVisible}
        loading={cancelLoading}
        onCancel={closeCancelModal}
        onConfirm={confirmCancel}
      />

      <EditExecutionModal
        execution={executionToEdit}
        open={editModalVisible}
        loading={editLoading}
        form={editForm}
        targetOptions={targetOptions}
        onCancel={closeEditModal}
        onSubmit={submitEdit}
      />
    </div>
  );
}

export default CalendarPage;
