/**
 * Tests for DriftBadge component (Story 64.13, AC #1, #9).
 * Three visual states: Synchronisé, Divergé, UI only.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DriftBadge } from '../DriftBadge';
import { getDriftStatus } from '../driftUtils';

// Mock driftUtils so we can override getDriftStatus in one test for defensive branch coverage
vi.mock('../driftUtils', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../driftUtils')>();
  return {
    ...actual,
    getDriftStatus: vi.fn(actual.getDriftStatus),
  };
});

// Mock antd theme token to avoid full Ant Design theme context
vi.mock('antd', async (importOriginal) => {
  const actual = await importOriginal<typeof import('antd')>();
  return {
    ...actual,
    theme: {
      ...actual.theme,
      useToken: () => ({
        token: {
          colorSuccess: '#52c41a',
          colorWarning: '#faad14',
          colorInfo: '#1677ff',
        },
      }),
    },
  };
});

describe('getDriftStatus', () => {
  it('returns "ui-only" when last_synced_at is null', () => {
    expect(getDriftStatus(null, '2026-01-01T10:00:00Z')).toBe('ui-only');
    expect(getDriftStatus(undefined, '2026-01-01T10:00:00Z')).toBe('ui-only');
  });

  it('returns "diverged" when updated_at > last_synced_at', () => {
    expect(getDriftStatus('2026-01-01T10:00:00Z', '2026-01-02T10:00:00Z')).toBe('diverged');
  });

  it('returns "synced" when updated_at <= last_synced_at', () => {
    expect(getDriftStatus('2026-01-02T10:00:00Z', '2026-01-01T10:00:00Z')).toBe('synced');
    // equal timestamps → synced
    expect(getDriftStatus('2026-01-01T10:00:00Z', '2026-01-01T10:00:00Z')).toBe('synced');
  });
});

describe('DriftBadge', () => {
  it('affiche "Synchronisé" quand last_synced_at != null et updated_at <= last_synced_at', () => {
    render(
      <DriftBadge
        last_synced_at="2026-01-02T10:00:00Z"
        updated_at="2026-01-01T10:00:00Z"
      />
    );
    expect(screen.getByText('Synchronisé')).toBeInTheDocument();
    expect(screen.getByLabelText('Sync Git: Synchronisé')).toBeInTheDocument();
  });

  it('affiche "Divergé" quand last_synced_at != null et updated_at > last_synced_at', () => {
    render(
      <DriftBadge
        last_synced_at="2026-01-01T10:00:00Z"
        updated_at="2026-01-02T10:00:00Z"
      />
    );
    expect(screen.getByText('Divergé')).toBeInTheDocument();
    expect(screen.getByLabelText('Sync Git: Divergé')).toBeInTheDocument();
  });

  it('affiche "UI only" quand last_synced_at est null', () => {
    render(
      <DriftBadge
        last_synced_at={null}
        updated_at="2026-01-01T10:00:00Z"
      />
    );
    expect(screen.getByText('UI only')).toBeInTheDocument();
    expect(screen.getByLabelText('Sync Git: UI only')).toBeInTheDocument();
  });

  it('affiche "Divergé" avec tooltip vide quand status diverged mais last_synced_at falsy (defensive)', () => {
    vi.mocked(getDriftStatus).mockReturnValueOnce('diverged');
    render(
      <DriftBadge
        last_synced_at={null}
        updated_at="2026-01-02T10:00:00Z"
      />
    );
    expect(screen.getByText('Divergé')).toBeInTheDocument();
    expect(screen.getByLabelText('Sync Git: Divergé')).toBeInTheDocument();
  });
});
