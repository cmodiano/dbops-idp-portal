import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import { ParallelGroupTimelineSection } from './ParallelGroupTimelineSection';
import type { ExecutionStepResponse } from '../../../types/api/executions';

const makeStep = (overrides: Partial<ExecutionStepResponse>): ExecutionStepResponse => ({
  id: 1,
  execution_id: 100,
  step_name: 'Step',
  step_type: 'platform',
  status: 'PENDING',
  step_order: 1,
  started_at: null,
  completed_at: null,
  error_message: null,
  output: null,
  platform_job_id: null,
  ...overrides,
});

const subSteps: ExecutionStepResponse[] = [
  makeStep({ id: 1, step_name: 'Backup DB', status: 'COMPLETED', step_order: 1 }),
  makeStep({ id: 2, step_name: 'Backup Config', status: 'RUNNING', step_order: 2 }),
];

const defaultProps = {
  groupName: 'Backups',
  subSteps,
  expandedId: null,
  onToggleExpand: vi.fn(),
  onOpenLogs: vi.fn(),
};

function renderSection(props = defaultProps) {
  return render(
    <MemoryRouter>
      <ParallelGroupTimelineSection {...props} />
    </MemoryRouter>,
  );
}

describe('ParallelGroupTimelineSection', () => {
  it("affiche l'en-tête avec le nom du groupe", () => {
    renderSection();
    expect(screen.getByText(/Groupe parallèle — Backups/)).toBeInTheDocument();
  });

  it('affiche le data-testid pour les tests', () => {
    renderSection();
    expect(screen.getByTestId('parallel-group-timeline-section')).toBeInTheDocument();
  });

  it('affiche badge "en parallèle" si ≥2 sous-steps RUNNING', () => {
    const runningSteps = [
      makeStep({ id: 1, step_name: 'Backup DB', status: 'RUNNING', step_order: 1 }),
      makeStep({ id: 2, step_name: 'Backup Config', status: 'RUNNING', step_order: 2 }),
    ];
    renderSection({ ...defaultProps, subSteps: runningSteps });
    expect(screen.getByText(/en parallèle/i)).toBeInTheDocument();
  });

  it("n'affiche pas badge si <2 sous-steps RUNNING", () => {
    renderSection();
    // Only 1 RUNNING step in default subSteps — badge should not be visible
    expect(screen.queryByText(/en parallèle/i)).not.toBeInTheDocument();
  });

  it('affiche le nom de chaque sous-step', () => {
    renderSection();
    expect(screen.getByText('Backup DB')).toBeInTheDocument();
    expect(screen.getByText('Backup Config')).toBeInTheDocument();
  });

  it('rend sans crash si subSteps est vide', () => {
    renderSection({ ...defaultProps, subSteps: [] });
    expect(screen.getByTestId('parallel-group-timeline-section')).toBeInTheDocument();
  });

  it('affiche le badge avec le bon nombre de RUNNING', () => {
    const runningSteps = [
      makeStep({ id: 1, step_name: 'A', status: 'RUNNING', step_order: 1 }),
      makeStep({ id: 2, step_name: 'B', status: 'RUNNING', step_order: 2 }),
      makeStep({ id: 3, step_name: 'C', status: 'RUNNING', step_order: 3 }),
    ];
    renderSection({ ...defaultProps, subSteps: runningSteps });
    expect(screen.getByText('3 en parallèle')).toBeInTheDocument();
  });
});
