/**
 * Tests for useCalendarState hook — Story 26.6 AC9
 */
import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import type { EventClickArg, DatesSetArg } from '@fullcalendar/core';

import { useCalendarState } from '../useCalendarState';

describe('useCalendarState', () => {
  it('should initialize with default values', () => {
    const { result } = renderHook(() => useCalendarState());
    expect(result.current.selectedEvent).toBeNull();
    expect(result.current.popoverPosition).toBeNull();
    expect(result.current.calendarView).toBe('timeGridWeek');
    expect(result.current.dateRange).toBeNull();
  });

  it('handleEventClick should set selectedEvent and popoverPosition', () => {
    const { result } = renderHook(() => useCalendarState());

    const mockExec = { scheduled_execution_id: 1, action_name: 'Test' };
    const mockArg = {
      event: {
        extendedProps: { execution: mockExec },
      },
      el: {
        getBoundingClientRect: () => ({ left: 100, top: 200, width: 50, height: 30 }),
      },
    } as unknown as EventClickArg;

    act(() => {
      result.current.handleEventClick(mockArg);
    });

    expect(result.current.selectedEvent).toBe(mockExec);
    expect(result.current.popoverPosition).toEqual({ x: 125, y: 200 });
  });

  it('handleDatesSet should set dateRange', () => {
    const { result } = renderHook(() => useCalendarState());

    // Use midday UTC to avoid timezone-shifting the date
    const mockArg = {
      start: new Date('2026-03-10T12:00:00Z'),
      end: new Date('2026-03-17T12:00:00Z'),
    } as unknown as DatesSetArg;

    act(() => {
      result.current.handleDatesSet(mockArg);
    });

    expect(result.current.dateRange).not.toBeNull();
    expect(result.current.dateRange!.start).toMatch(/2026-03-10/);
    expect(result.current.dateRange!.end).toMatch(/2026-03-17/);
  });

  it('handleDatesSet should not update if dates unchanged', () => {
    const { result } = renderHook(() => useCalendarState());

    const mockArg = {
      start: new Date('2026-03-10T12:00:00Z'),
      end: new Date('2026-03-17T12:00:00Z'),
    } as unknown as DatesSetArg;

    act(() => {
      result.current.handleDatesSet(mockArg);
    });

    const firstRange = result.current.dateRange;

    act(() => {
      result.current.handleDatesSet(mockArg);
    });

    // Should be the same object reference (no re-render)
    expect(result.current.dateRange).toBe(firstRange);
  });

  it('closePopover should reset selectedEvent and popoverPosition', () => {
    const { result } = renderHook(() => useCalendarState());

    const mockArg = {
      event: { extendedProps: { execution: { id: 1 } } },
      el: { getBoundingClientRect: () => ({ left: 100, top: 200, width: 50, height: 30 }) },
    } as unknown as EventClickArg;

    act(() => {
      result.current.handleEventClick(mockArg);
    });
    act(() => {
      result.current.closePopover();
    });

    expect(result.current.selectedEvent).toBeNull();
    expect(result.current.popoverPosition).toBeNull();
  });

  it('handleViewChange should set calendarView', () => {
    const { result } = renderHook(() => useCalendarState());

    act(() => {
      result.current.handleViewChange('dayGridMonth');
    });

    expect(result.current.calendarView).toBe('dayGridMonth');
  });
});
