/**
 * CalendarEventContent — Story 26.6 AC6
 *
 * Extracted from CalendarPage.tsx. Renders individual calendar event
 * cells with recurring indicator icon.
 */
import { SyncOutlined } from '@ant-design/icons';
import type { EventContentArg } from '@fullcalendar/core';
import type { ScheduledExecutionListItem } from '../../types/api';

export interface CalendarEventContentProps {
  eventInfo: EventContentArg;
}

export function CalendarEventContent({ eventInfo }: CalendarEventContentProps) {
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
