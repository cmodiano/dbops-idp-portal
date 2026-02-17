/**
 * Tests for CalendarEventContent — Story 26.6 AC9
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { EventContentArg } from '@fullcalendar/core';

import { CalendarEventContent } from '../CalendarEventContent';

function makeEventInfo(overrides: Record<string, unknown> = {}): EventContentArg {
  return {
    event: {
      title: 'Deploy DB',
      extendedProps: {
        execution: {
          recurring_pattern: null,
          ...overrides,
        },
      },
    },
  } as unknown as EventContentArg;
}

describe('CalendarEventContent', () => {
  it('should render event title', () => {
    render(<CalendarEventContent eventInfo={makeEventInfo()} />);
    expect(screen.getByText('Deploy DB')).toBeTruthy();
  });

  it('should show recurring icon when recurring_pattern exists', () => {
    const eventInfo = makeEventInfo({
      recurring_pattern: { pattern_type: 'daily', is_active: true },
    });
    const { container } = render(<CalendarEventContent eventInfo={eventInfo} />);
    // SyncOutlined renders an SVG with role="img"
    const icon = container.querySelector('[aria-label="sync"]') ?? container.querySelector('.anticon-sync');
    expect(icon).toBeTruthy();
  });

  it('should not show recurring icon when no recurring_pattern', () => {
    const { container } = render(<CalendarEventContent eventInfo={makeEventInfo()} />);
    const icon = container.querySelector('[aria-label="sync"]') ?? container.querySelector('.anticon-sync');
    expect(icon).toBeFalsy();
  });

  it('should have data-testid calendar-event', () => {
    render(<CalendarEventContent eventInfo={makeEventInfo()} />);
    expect(screen.getByTestId('calendar-event')).toBeTruthy();
  });
});
