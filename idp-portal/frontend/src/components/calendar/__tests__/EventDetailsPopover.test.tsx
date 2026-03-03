/**
 * Tests for EventDetailsPopover — Story 26.6 AC9
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfigProvider } from 'antd';
import { MemoryRouter } from 'react-router';

import { EventDetailsPopover } from '../EventDetailsPopover';
import type { ScheduledExecutionListItem, DailyPatternConfig } from '../../../types/api';

vi.mock('../../../contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from '../../../contexts/AuthContext';

function makeExec(overrides: Partial<ScheduledExecutionListItem> = {}): ScheduledExecutionListItem {
  return {
    scheduled_execution_id: 42,
    action_id: 10,
    action_name: 'Deploy DB',
    user_id: 1,
    user_name: 'admin',
    environment: 'dev',
    scheduled_at: '2026-03-15T10:00:00Z',
    status: 'pending',
    created_at: '2026-03-10T08:00:00Z',
    parameters: null,
    ...overrides,
  };
}

function renderPopover(
  exec: ScheduledExecutionListItem,
  props: Partial<React.ComponentProps<typeof EventDetailsPopover>> = {},
  userOverrides: Record<string, unknown> = {},
) {
  vi.mocked(useAuth).mockReturnValue({
    user: { id: 1, profile: 'DBOPS', ...userOverrides },
  } as unknown as ReturnType<typeof useAuth>);

  return render(
    <ConfigProvider>
      <MemoryRouter>
        <EventDetailsPopover execution={exec} {...props} />
      </MemoryRouter>
    </ConfigProvider>
  );
}

describe('EventDetailsPopover', () => {
  it('should render action name and environment', () => {
    renderPopover(makeExec());
    expect(screen.getByText('Deploy DB')).toBeTruthy();
    expect(screen.getByText('Développement')).toBeTruthy();
  });

  it('should render user info', () => {
    renderPopover(makeExec());
    expect(screen.getByText('admin')).toBeTruthy();
  });

  it('should render pattern type Unique for non-recurring', () => {
    renderPopover(makeExec());
    expect(screen.getByText('Unique')).toBeTruthy();
  });

  it('should display targets when present', () => {
    const exec = makeExec({ parameters: { _targets: ['server1', 'server2'], key: 'val' } });
    renderPopover(exec);
    expect(screen.getByText('server1')).toBeTruthy();
    expect(screen.getByText('server2')).toBeTruthy();
  });

  it('should display parameters (filtering _targets)', () => {
    const exec = makeExec({ parameters: { _targets: ['s1'], visible_param: 'hello' } });
    renderPopover(exec);
    expect(screen.getByTestId('popover-parameters')).toBeTruthy();
    expect(screen.getByTestId('popover-parameters').textContent).toContain('visible_param');
    expect(screen.getByTestId('popover-parameters').textContent).not.toContain('_targets');
  });

  it('should show execution link when status=executed', () => {
    const exec = makeExec({ status: 'executed', execution_id: 99 });
    renderPopover(exec);
    expect(screen.getByTestId('link-to-execution')).toBeTruthy();
  });

  it('should not show execution link when status=pending', () => {
    renderPopover(makeExec());
    expect(screen.queryByTestId('link-to-execution')).toBeFalsy();
  });

  it('should show Cancel button for owner with pending status', () => {
    const onCancel = vi.fn();
    renderPopover(makeExec(), { onRequestCancel: onCancel });
    expect(screen.getByTestId('cancel-execution-btn')).toBeTruthy();
  });

  it('should show Edit button for DBOPS with pending status', () => {
    const onEdit = vi.fn();
    renderPopover(makeExec(), { onRequestEdit: onEdit });
    expect(screen.getByTestId('edit-execution-btn')).toBeTruthy();
  });

  it('should not show Cancel/Edit for non-owner DBA', () => {
    const onCancel = vi.fn();
    const onEdit = vi.fn();
    renderPopover(
      makeExec({ user_id: 999 }),
      { onRequestCancel: onCancel, onRequestEdit: onEdit },
      { id: 1, profile: 'DBA' },
    );
    expect(screen.queryByTestId('cancel-execution-btn')).toBeFalsy();
    expect(screen.queryByTestId('edit-execution-btn')).toBeFalsy();
  });

  it('should show recurrence toggle for DBOPS with recurring execution', () => {
    const onToggle = vi.fn();
    const exec = makeExec({
      recurring_pattern: {
        pattern_type: 'daily',
        pattern_config: {} as DailyPatternConfig,
        is_active: true,
        next_execution_date: '2026-03-16T09:00:00Z',
      },
    });
    renderPopover(exec, { onToggleRecurrence: onToggle });
    expect(screen.getByTestId('recurrence-toggle')).toBeTruthy();
    expect(screen.getByTestId('recurrence-toggle-label').textContent).toContain('Récurrence active');
  });

  it('should call onRequestCancel when Cancel button is clicked', async () => {
    const onCancel = vi.fn();
    const user = userEvent.setup();
    renderPopover(makeExec(), { onRequestCancel: onCancel });

    await user.click(screen.getByTestId('cancel-execution-btn'));
    expect(onCancel).toHaveBeenCalledWith(expect.objectContaining({ scheduled_execution_id: 42 }));
  });

  it('should call onRequestEdit when Edit button is clicked', async () => {
    const onEdit = vi.fn();
    const user = userEvent.setup();
    renderPopover(makeExec(), { onRequestEdit: onEdit });

    await user.click(screen.getByTestId('edit-execution-btn'));
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ scheduled_execution_id: 42 }));
  });

  // Story 57.17: section Origine
  it('shows origin link when source_execution_id is present', () => {
    const exec = makeExec({ source_execution_id: 100 });
    renderPopover(exec);
    expect(screen.getByTestId('link-to-source-execution')).toBeTruthy();
  });

  it('does not show origin link when source_execution_id is absent', () => {
    renderPopover(makeExec());
    expect(screen.queryByTestId('link-to-source-execution')).toBeFalsy();
  });

  it('does not show origin link when source_execution_id is null', () => {
    const exec = makeExec({ source_execution_id: null });
    renderPopover(exec);
    expect(screen.queryByTestId('link-to-source-execution')).toBeFalsy();
  });

  it('origin link navigates to correct execution URL', () => {
    const exec = makeExec({ source_execution_id: 42 });
    renderPopover(exec);
    const link = screen.getByTestId('link-to-source-execution');
    expect(link.getAttribute('href')).toBe('/executions/42');
  });
});
