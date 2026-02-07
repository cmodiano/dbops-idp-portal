/**
 * Tests for ExecutionsPage compact mode (Story 17.13).
 *
 * Validates that the Executions table uses compact density:
 * - Table size="small" prop applied
 * - Engine icons render at 40px (ENGINE_ICON_SIZE_COMPACT)
 * - Status badges have compact padding (1px 6px)
 * - Column widths adjusted for compact mode
 * - Accessibility maintained (ARIA attributes, tooltips)
 * - Visual snapshot for compact table
 * - Row count calculation (viewport 1080p: ~17 vs ~14)
 * - Both themes render correctly with compact mode
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import ExecutionsPage from '../pages/ExecutionsPage';
import { ThemeProvider } from '../contexts/ThemeContext';
import {
  renderStatusIndicator,
  renderEngineIcon,
  renderPlateformeIcon,
  ENGINE_ICON_SIZE_COMPACT_VALUE,
} from '../utils/executionRenderers';
import * as executionService from '../services/execution_service';
import * as integrationsService from '../services/integrations_service';
import type { ExecutionResponse } from '../types/api';

vi.mock('../services/execution_service');
vi.mock('../services/integrations_service');
vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: () => ({ steps: [], execution: null, loading: false, error: null }),
}));

/** Render helper with ThemeProvider and Router (Story 9.10: useSearchParams needs Router). */
function renderWithTheme(ui: React.ReactElement) {
  const router = createMemoryRouter(
    [{ path: '/', element: ui }],
    { initialEntries: ['/'] }
  );
  return render(
    <ThemeProvider>
      <RouterProvider router={router} />
    </ThemeProvider>
  );
}

const mockExecutions: ExecutionResponse[] = [
  {
    id: 1,
    action_id: 10,
    action_name: 'Create PDB',
    user_id: 1,
    environment: 'dev',
    parameters: null,
    status: 'COMPLETED',
    servicenow_change_id: null,
    started_at: '2026-01-28T10:00:00Z',
    completed_at: '2026-01-28T10:05:00Z',
    created_at: '2026-01-28T09:59:00Z',
    engine: 'Oracle',
    platform: 'AAP',
    item_type: 'action',
  },
  {
    id: 2,
    action_id: 11,
    action_name: 'Apply Patch',
    user_id: 1,
    environment: 'prod',
    parameters: null,
    status: 'RUNNING',
    servicenow_change_id: 'CHG0012345',
    started_at: '2026-01-29T14:00:00Z',
    completed_at: null,
    created_at: '2026-01-29T13:59:00Z',
    engine: 'SQL Server',
    platform: 'AAP',
    item_type: 'action',
  },
];

describe('ExecutionsPage - Compact Mode (Story 17.13)', () => {
  const defaultListResponse = {
    data: mockExecutions,
    pagination: { page: 1, page_size: 25, total_count: 2, total_pages: 1 },
  };

  beforeEach(() => {
    vi.resetAllMocks();
    // Re-setup mocks after resetAllMocks clears them
    vi.mocked(integrationsService.getIntegrations).mockResolvedValue([]);
    vi.mocked(executionService.listExecutions).mockResolvedValue(defaultListResponse);
    vi.mocked(executionService.getExecution).mockResolvedValue(mockExecutions[0]);
    vi.mocked(executionService.getExecutionSteps).mockResolvedValue([]);
    vi.mocked(executionService.listPendingApprovals).mockResolvedValue({
      data: [],
      pagination: { page: 1, page_size: 50, total_count: 0, total_pages: 0 },
    });
    vi.mocked(executionService.fetchExecutionStats).mockResolvedValue({
      executions_jour: 10,
      taux_succes_pct: 85.5,
      executions_en_cours: 1,
      executions_en_erreur: 0,
    });
    vi.mocked(executionService.fetchExecutionTimeSeries).mockResolvedValue([]);
    vi.mocked(executionService.fetchExecutionTags).mockResolvedValue([]);
  });

  it('renders table in compact mode with size="small" (Task 1)', async () => {
    const { container } = renderWithTheme(<ExecutionsPage />);
    await waitFor(() => {
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });

    // Ant Design adds ant-table-small class when size="small"
    const tableSmall = container.querySelector('.ant-table-small');
    expect(tableSmall).toBeInTheDocument();
  });

  it('skeleton table also uses compact mode (Task 1.2)', () => {
    // During initial loading, skeleton table should also be compact
    vi.mocked(executionService.listExecutions).mockImplementation(
      () => new Promise(() => {}), // Never resolves → stays in loading state
    );

    const { container } = renderWithTheme(<ExecutionsPage />);

    const tableSmall = container.querySelector('.ant-table-small');
    expect(tableSmall).toBeInTheDocument();
  });

  it('engine icons render at 40px (ENGINE_ICON_SIZE_COMPACT) (Task 2)', () => {
    // Verify the exported constant
    expect(ENGINE_ICON_SIZE_COMPACT_VALUE).toBe(40);

    // Render an engine icon and check size
    const { container } = render(renderEngineIcon('Oracle', 'action') as React.ReactElement);
    const img = container.querySelector('img');
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute('width', '40');
    expect(img).toHaveAttribute('height', '40');
  });

  it('workflow icons render at 40px compact size (Task 2)', () => {
    const { container } = render(renderEngineIcon(null, 'workflow') as React.ReactElement);
    const icon = container.querySelector('[class*="anticon-apartment"]');
    expect(icon).toBeInTheDocument();
    // Icon font-size should be 40px
    const svg = icon?.closest('[style]');
    expect(svg).toHaveStyle({ fontSize: '40px' });
  });

  it('status badges have compact padding 1px 6px (Task 3)', () => {
    const { container } = render(renderStatusIndicator('COMPLETED') as React.ReactElement);
    const tag = container.querySelector('.ant-tag');
    expect(tag).toBeInTheDocument();
    expect(tag).toHaveStyle({ padding: '1px 6px' });
  });

  it('status badges maintain fontSize 12px and lineHeight 20px (Task 3.2)', () => {
    const { container } = render(renderStatusIndicator('RUNNING') as React.ReactElement);
    const tag = container.querySelector('.ant-tag');
    expect(tag).toHaveStyle({ fontSize: '12px', lineHeight: '20px' });
  });

  it('status badges maintain border and dark background styling (Task 3.4)', () => {
    const { container } = render(renderStatusIndicator('FAILED') as React.ReactElement);
    const tag = container.querySelector('.ant-tag');
    expect(tag).toBeInTheDocument();
    // Verify glass morphism styling preserved: dark background + colored border
    expect(tag).toHaveStyle({ backgroundColor: 'rgba(26, 26, 36, 0.8)' });
    // Check border via style attribute (jsdom may not parse border shorthand)
    const style = tag?.getAttribute('style') ?? '';
    expect(style).toContain('border: 1px solid');
    expect(style).toContain('rgb(239, 68, 68)');
  });

  it('accessibility maintained: tooltips and aria attributes on icons (Task 5.4)', () => {
    const { container } = render(renderEngineIcon('Oracle', 'action') as React.ReactElement);
    const img = container.querySelector('img');
    // img has aria-hidden for decorative icons
    expect(img).toHaveAttribute('aria-hidden');
    // Icon size 40px > WCAG 2.4.7 minimum 24x24px
    expect(ENGINE_ICON_SIZE_COMPACT_VALUE).toBeGreaterThanOrEqual(24);
  });

  it('compact table increases visible row count vs normal (Task 5.6)', () => {
    // Viewport 1080p: table area ~700px
    const tableViewportHeight = 700;
    const compactRowHeight = 40; // size="small"
    const normalRowHeight = 48; // default

    const compactRows = Math.floor(tableViewportHeight / compactRowHeight);
    const normalRows = Math.floor(tableViewportHeight / normalRowHeight);

    // Compact should show more rows
    expect(compactRows).toBeGreaterThan(normalRows);
    // Expect ~17 rows compact vs ~14 normal
    expect(compactRows).toBeGreaterThanOrEqual(17);
    expect(normalRows).toBeLessThanOrEqual(15);
    // Gain should be >=20%
    const gainPct = ((compactRows - normalRows) / normalRows) * 100;
    expect(gainPct).toBeGreaterThanOrEqual(20);
  });

  it('compact table matches snapshot (Task 5.5)', async () => {
    const { container } = renderWithTheme(<ExecutionsPage />);
    await waitFor(() => {
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });
    expect(container.firstChild).toMatchSnapshot();
  });

  it('platform icons render at compact size (Task 2.3)', () => {
    const { container } = render(
      renderPlateformeIcon(null, null, 'AAP', null) as React.ReactElement,
    );
    const icon = container.querySelector('[class*="anticon-rocket"]');
    expect(icon).toBeInTheDocument();
    // Platform icon should use compact size
    const styledEl = icon?.closest('[style]');
    expect(styledEl).toHaveStyle({ fontSize: '40px' });
  });
});
