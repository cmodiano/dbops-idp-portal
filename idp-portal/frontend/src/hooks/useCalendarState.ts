/**
 * useCalendarState Hook — Story 26.6 AC4
 *
 * Extracted from CalendarPage.tsx. Manages calendar UI state:
 * selected event, popover position, calendar view, and date range.
 */
import { useState, useCallback, useRef } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { EventClickArg, DatesSetArg } from '@fullcalendar/core';
import type FullCalendar from '@fullcalendar/react';
import dayjs from 'dayjs';
import type { ScheduledExecutionListItem } from '../types/api';

export interface UseCalendarStateReturn {
  calendarRef: React.RefObject<FullCalendar | null>;
  selectedEvent: ScheduledExecutionListItem | null;
  popoverPosition: { x: number; y: number } | null;
  calendarView: 'timeGridWeek' | 'dayGridMonth';
  dateRange: { start: string; end: string } | null;
  handleEventClick: (arg: EventClickArg) => void;
  handleDatesSet: (arg: DatesSetArg) => void;
  closePopover: () => void;
  handleViewChange: (view: string) => void;
  setDateRange: Dispatch<SetStateAction<{ start: string; end: string } | null>>;
}

export function useCalendarState(): UseCalendarStateReturn {
  const calendarRef = useRef<FullCalendar | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<ScheduledExecutionListItem | null>(null);
  const [popoverPosition, setPopoverPosition] = useState<{ x: number; y: number } | null>(null);
  const [calendarView, setCalendarView] = useState<'timeGridWeek' | 'dayGridMonth'>('timeGridWeek');
  const [dateRange, setDateRange] = useState<{ start: string; end: string } | null>(null);

  const handleEventClick = useCallback((info: EventClickArg) => {
    const execution = info.event.extendedProps.execution as ScheduledExecutionListItem;
    setSelectedEvent(execution);
    const rect = info.el.getBoundingClientRect();
    setPopoverPosition({ x: rect.left + rect.width / 2, y: rect.top });
  }, []);

  const handleDatesSet = useCallback((dateInfo: DatesSetArg) => {
    const newStart = dayjs(dateInfo.start).format('YYYY-MM-DD');
    const newEnd = dayjs(dateInfo.end).format('YYYY-MM-DD');
    setDateRange((prev) => {
      if (prev && prev.start === newStart && prev.end === newEnd) {
        return prev;
      }
      return { start: newStart, end: newEnd };
    });
  }, []);

  const closePopover = useCallback(() => {
    setSelectedEvent(null);
    setPopoverPosition(null);
  }, []);

  const handleViewChange = useCallback((view: string) => {
    const newView = view as 'timeGridWeek' | 'dayGridMonth';
    setCalendarView(newView);
    calendarRef.current?.getApi().changeView(newView);
  }, []);

  return {
    calendarRef,
    selectedEvent,
    popoverPosition,
    calendarView,
    dateRange,
    handleEventClick,
    handleDatesSet,
    closePopover,
    handleViewChange,
    setDateRange,
  };
}
