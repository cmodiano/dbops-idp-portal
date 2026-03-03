/**
 * Tests for TimelineStepItem — Story 57.17 (schedule_execution traceability).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { TimelineStepItem } from './TimelineStepItem';
import type { ExecutionStepResponse } from '../../../types/api';

// Mock formatUtcToLocal to return a predictable string in tests
vi.mock('../../../utils/dateFormat', () => ({
  formatUtcToLocal: (s: string) => `formatted:${s}`,
}));

// Mock formatDuration utility
vi.mock('./utils', () => ({
  formatDuration: () => '',
}));

function makeScheduleStep(overrides: Partial<ExecutionStepResponse> = {}): ExecutionStepResponse {
  return {
    id: 5,
    execution_id: 100,
    step_order: 2,
    step_name: 'Planifier l\'application',
    step_type: 'schedule_execution',
    status: 'COMPLETED',
    started_at: '2026-03-03T10:00:00Z',
    completed_at: '2026-03-03T10:00:05Z',
    output: {
      scheduled_execution_id: 789,
      action_name: 'Patch Oracle mensuel',
      scheduled_at: '2026-03-15T02:00:00Z',
    },
    platform_job_id: null,
    error_message: null,
    ...overrides,
  };
}

function renderStep(step: ExecutionStepResponse, isExpanded = true) {
  return render(
    <MemoryRouter>
      <TimelineStepItem
        step={step}
        isExpanded={isExpanded}
        isLast={false}
        onToggleExpand={vi.fn()}
        onOpenLogs={vi.fn()}
      />
    </MemoryRouter>
  );
}

describe('TimelineStepItem — Story 57.17: schedule_execution badge', () => {
  it('shows schedule link for schedule_execution COMPLETED step with scheduled_execution_id', () => {
    renderStep(makeScheduleStep());
    expect(screen.getByTestId('schedule-execution-badge')).toBeTruthy();
    expect(screen.getByTestId('link-to-calendar')).toBeTruthy();
    expect(screen.getByTestId('link-to-calendar').getAttribute('href')).toBe('/calendar');
  });

  it('shows scheduled_execution_id in the badge', () => {
    renderStep(makeScheduleStep());
    expect(screen.getByTestId('schedule-execution-badge').textContent).toContain('789');
  });

  it('shows action_name in the badge when available in step output', () => {
    renderStep(makeScheduleStep());
    expect(screen.getByTestId('schedule-execution-badge').textContent).toContain('Patch Oracle mensuel');
  });

  it('shows formatted scheduled_at when available in step output', () => {
    renderStep(makeScheduleStep());
    expect(screen.getByTestId('schedule-execution-badge').textContent).toContain('formatted:2026-03-15T02:00:00Z');
  });

  it('does not show schedule link for FAILED schedule_execution step', () => {
    renderStep(makeScheduleStep({ status: 'FAILED' }));
    expect(screen.queryByTestId('schedule-execution-badge')).toBeFalsy();
  });

  it('does not show schedule link when scheduled_execution_id is absent in output', () => {
    renderStep(makeScheduleStep({
      output: { action_name: 'Test', scheduled_at: '2026-03-15T02:00:00Z' },
    }));
    expect(screen.queryByTestId('schedule-execution-badge')).toBeFalsy();
  });

  it('does not show schedule link for non-schedule_execution step types', () => {
    renderStep(makeScheduleStep({ step_type: 'platform' }));
    expect(screen.queryByTestId('schedule-execution-badge')).toBeFalsy();
  });

  it('does not show schedule link when step is not expanded', () => {
    renderStep(makeScheduleStep(), false);
    expect(screen.queryByTestId('schedule-execution-badge')).toBeFalsy();
  });

  it('does not show schedule link for PENDING schedule_execution step', () => {
    renderStep(makeScheduleStep({ status: 'PENDING', output: null }));
    expect(screen.queryByTestId('schedule-execution-badge')).toBeFalsy();
  });

  it('shows badge without action_name when action_name is absent', () => {
    renderStep(makeScheduleStep({
      output: { scheduled_execution_id: 789, scheduled_at: '2026-03-15T02:00:00Z' },
    }));
    const badge = screen.getByTestId('schedule-execution-badge');
    expect(badge.textContent).toContain('789');
    expect(badge.textContent).not.toContain('Patch Oracle');
  });

  it('shows badge without scheduled_at when scheduled_at is absent', () => {
    renderStep(makeScheduleStep({
      output: { scheduled_execution_id: 789, action_name: 'Patch Oracle mensuel' },
    }));
    const badge = screen.getByTestId('schedule-execution-badge');
    expect(badge.textContent).toContain('789');
    expect(badge.textContent).toContain('Patch Oracle mensuel');
    expect(badge.textContent).not.toContain('formatted:');
  });
});

// ---------------------------------------------------------------------------
// Story 58.3 — WAITING step display
// ---------------------------------------------------------------------------

describe('TimelineStepItem — Story 58.3: WAITING gate display', () => {
  function makeWaitingStep(overrides: Partial<ExecutionStepResponse> = {}): ExecutionStepResponse {
    return {
      id: 10,
      execution_id: 1,
      step_order: 1,
      step_name: 'Approbation initiale',
      step_type: 'platform',
      status: 'WAITING',
      started_at: null,
      completed_at: null,
      output: null,
      platform_job_id: null,
      error_message: null,
      ...overrides,
    };
  }

  it('shows "En attente d\'approbation" badge for WAITING step', () => {
    renderStep(makeWaitingStep());
    expect(screen.getByText("En attente d'approbation")).toBeTruthy();
  });

  it('does not show "En cours" badge for WAITING step', () => {
    renderStep(makeWaitingStep());
    expect(screen.queryByText('En cours')).toBeFalsy();
  });

  it('renders step name for WAITING step', () => {
    renderStep(makeWaitingStep());
    expect(screen.getByText('Approbation initiale')).toBeTruthy();
  });
});
