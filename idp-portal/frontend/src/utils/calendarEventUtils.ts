/**
 * Calendar Event Utilities — Story 26.6 AC1
 *
 * Extracted from CalendarPage.tsx to separate data transformation concerns.
 * Transforms ScheduledExecutionListItem → FullCalendar event format.
 */
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import type { ScheduledExecutionListItem, ExecutionEnvironment } from '../types/api';

dayjs.extend(utc);

/** Environment color mapping. */
export const ENV_COLORS: Record<ExecutionEnvironment, string> = {
  dev: '#1890ff',
  staging: '#fa8c16',
  prod: '#f5222d',
};

/** Environment labels in French. */
export const ENV_LABELS: Record<ExecutionEnvironment, string> = {
  dev: 'Développement',
  staging: 'Staging',
  prod: 'Production',
};

/** FullCalendar event with extended props. */
export interface CalendarEvent {
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
export function toUtcIso(dateStr: string): string {
  if (!dateStr || typeof dateStr !== 'string') return dateStr;
  const trimmed = dateStr.trim();
  if (/Z$/.test(trimmed) || /[+-]\d{2}:?\d{2}$/.test(trimmed)) return trimmed;
  return trimmed + 'Z';
}

/** Map scheduled execution to FullCalendar event. */
export function mapToCalendarEvent(exec: ScheduledExecutionListItem): CalendarEvent {
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
export function describePatternType(exec: ScheduledExecutionListItem): string {
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

/** Extract display params (exclude technical keys _targets, _env_config). */
export function getDisplayParameters(parameters: Record<string, unknown> | null): Record<string, unknown> {
  if (!parameters || typeof parameters !== 'object') return {};
  return Object.fromEntries(
    Object.entries(parameters).filter(([key]) => !key.startsWith('_'))
  );
}
