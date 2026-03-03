/**
 * Calendar Event Utilities — Story 26.6 AC1
 *
 * Extracted from CalendarPage.tsx to separate data transformation concerns.
 * Transforms ScheduledExecutionListItem → FullCalendar event format.
 *
 * Environment colors/labels: use getEnvironmentHexColor and getEnvironmentLabel from
 * environmentHelpers — supports all inventory values (dev, developpement, staging,
 * certification, prod, production, etc.).
 */
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import type { ScheduledExecutionListItem } from '../types/api';
import { getEnvironmentHexColor } from './environmentHelpers';

dayjs.extend(utc);

/** @deprecated Use getEnvironmentHexColor(env) for inventory-aware colors. */
export const ENV_COLORS = { dev: '#3B82F6', staging: '#F97316', prod: '#EF4444' } as const;

/** @deprecated Use getEnvironmentLabel(env) from environmentHelpers for inventory-aware labels. */
export const ENV_LABELS = { dev: 'Développement', staging: 'Staging', prod: 'Production' } as const;

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
  const envColor = getEnvironmentHexColor(exec.environment ?? '');
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
