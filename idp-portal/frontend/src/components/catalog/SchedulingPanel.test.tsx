/**
 * Tests for SchedulingPanel — Story 11.11 AC5.
 * Recurring options (daily/weekly/cron) hidden for non-admin.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { App } from 'antd';
import { SchedulingPanel } from './SchedulingPanel';
import type { SchedulingState } from '../../hooks/useExecutionSubmit';
import type { UseSchedulingValidationReturn } from '../../hooks/useSchedulingValidation';

function makeScheduling(overrides?: Partial<SchedulingState>): SchedulingState {
  return {
    isScheduling: false,
    schedulingType: 'one-time',
    scheduledAt: null,
    dailyHour: 10,
    dailyMinute: 0,
    weeklyDayOfWeek: 1,
    weeklyHour: 10,
    weeklyMinute: 0,
    cronExpression: '',
    cronIsValid: null,
    cronError: '',
    cronNextExecutions: [],
    cronValidating: false,
    showCronHelper: false,
    ...overrides,
  };
}

function makeValidation(): UseSchedulingValidationReturn {
  return {
    validateSchedule: vi.fn(),
    validateCronDebounced: vi.fn(),
    handleCronPresetChange: vi.fn(),
    cancelValidation: vi.fn(),
  };
}

function renderPanel(isAdmin?: boolean) {
  return render(
    <App>
      <SchedulingPanel
        scheduling={makeScheduling()}
        onSchedulingChange={vi.fn()}
        schedulingError={null}
        submitting={false}
        validation={makeValidation()}
        isAdmin={isAdmin}
      />
    </App>,
  );
}

describe('SchedulingPanel — Story 11.11 AC5', () => {
  it('shows all scheduling options for admin users', () => {
    renderPanel(true);
    expect(screen.getByLabelText('Une seule fois')).toBeInTheDocument();
    expect(screen.getByLabelText('Tous les jours')).toBeInTheDocument();
    expect(screen.getByLabelText('Toutes les semaines')).toBeInTheDocument();
    expect(screen.getByLabelText('Avancé (cron)')).toBeInTheDocument();
  });

  it('hides recurring options for non-admin users', () => {
    renderPanel(false);
    expect(screen.getByLabelText('Une seule fois')).toBeInTheDocument();
    expect(screen.queryByLabelText('Tous les jours')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Toutes les semaines')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Avancé (cron)')).not.toBeInTheDocument();
  });

  it('defaults isAdmin to true when prop is omitted', () => {
    render(
      <App>
        <SchedulingPanel
          scheduling={makeScheduling()}
          onSchedulingChange={vi.fn()}
          schedulingError={null}
          submitting={false}
          validation={makeValidation()}
        />
      </App>,
    );
    expect(screen.getByLabelText('Tous les jours')).toBeInTheDocument();
  });

  it('shows admin-only tooltip for non-admin users', () => {
    renderPanel(false);
    // Non-admin has the admin restriction info icon (with marginLeft: 8px) plus the date tooltip icon
    const icons = screen.getAllByRole('img', { name: 'info-circle' });
    expect(icons.length).toBeGreaterThanOrEqual(2);
    // The admin restriction icon has marginLeft: 8px
    const adminIcon = icons.find((el) => el.style.marginLeft === '8px');
    expect(adminIcon).toBeDefined();
  });
});
