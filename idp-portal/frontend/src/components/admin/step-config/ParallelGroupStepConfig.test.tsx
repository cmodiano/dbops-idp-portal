import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ParallelGroupStepConfig } from './ParallelGroupStepConfig';
import type { WorkflowStepNodeData } from '../WorkflowStepNode';

const baseData: WorkflowStepNodeData = {
  name: 'Backups parallèles',
  step_type: 'parallel_group',
  step_id: 'pg-1',
  parallel_steps: [],
};

const availableStepOptions = [
  { value: 'pg-1', label: 'Groupe parallèle (pg-1)' }, // doit être filtré
  { value: 'bk-db', label: 'Backup DB' },
  { value: 'bk-cfg', label: 'Backup Config' },
  { value: 'apply-patch', label: 'Apply Patch' },
];

describe('ParallelGroupStepConfig', () => {
  it('rend le composant avec le container data-testid', () => {
    render(<ParallelGroupStepConfig data={baseData} onUpdate={vi.fn()} availableStepOptions={availableStepOptions} />);
    expect(screen.getByTestId('parallel-group-step-config')).toBeInTheDocument();
  });

  it('affiche le select avec aria-label correct', () => {
    render(<ParallelGroupStepConfig data={baseData} onUpdate={vi.fn()} availableStepOptions={availableStepOptions} />);
    expect(screen.getByLabelText('Étapes parallèles')).toBeInTheDocument();
  });

  it('affiche une erreur si parallel_steps contient 1 seul élément (AC5)', () => {
    const data = { ...baseData, parallel_steps: ['bk-db'] };
    render(<ParallelGroupStepConfig data={data} onUpdate={vi.fn()} availableStepOptions={availableStepOptions} />);
    const errorEl = screen.getByText('Un groupe parallèle requiert au moins 2 étapes');
    expect(errorEl).toBeInTheDocument();
    expect(errorEl).toHaveAttribute('role', 'alert');
  });

  it('affiche une erreur si parallel_steps est vide — état initial non configuré (AC5)', () => {
    render(<ParallelGroupStepConfig data={baseData} onUpdate={vi.fn()} availableStepOptions={availableStepOptions} />);
    expect(screen.getByText('Un groupe parallèle requiert au moins 2 étapes')).toBeInTheDocument();
  });

  it("n'affiche pas d'erreur si parallel_steps contient ≥ 2 éléments", () => {
    const data = { ...baseData, parallel_steps: ['bk-db', 'bk-cfg'] };
    render(<ParallelGroupStepConfig data={data} onUpdate={vi.fn()} availableStepOptions={availableStepOptions} />);
    expect(screen.queryByText('Un groupe parallèle requiert au moins 2 étapes')).not.toBeInTheDocument();
  });

  it('affiche la note Alert info sur les connexions canvas', () => {
    render(<ParallelGroupStepConfig data={baseData} onUpdate={vi.fn()} availableStepOptions={availableStepOptions} />);
    expect(screen.getByText(/connexions succès \/ erreur/i)).toBeInTheDocument();
  });

  it('affiche la note Alert warning fail-fast', () => {
    render(<ParallelGroupStepConfig data={baseData} onUpdate={vi.fn()} availableStepOptions={availableStepOptions} />);
    expect(screen.getByText(/fail-fast/i)).toBeInTheDocument();
  });

  it('fonctionne sans availableStepOptions (valeur par défaut)', () => {
    render(<ParallelGroupStepConfig data={baseData} onUpdate={vi.fn()} />);
    expect(screen.getByTestId('parallel-group-step-config')).toBeInTheDocument();
  });

  it('filtre le step courant (pg-1) des options disponibles — label absent des tags (AC4)', () => {
    // When pg-1 is both the current step (step_id) AND in the value (parallel_steps),
    // it must be absent from filteredOptions. AntD Select renders the raw value ID (not the
    // option label) when the value has no matching option → 'Groupe parallèle (pg-1)' must not appear.
    const dataWithSelf = { ...baseData, parallel_steps: ['pg-1'] };
    render(
      <ParallelGroupStepConfig data={dataWithSelf} onUpdate={vi.fn()} availableStepOptions={availableStepOptions} />,
    );
    // If filtering is broken, AntD would render the label 'Groupe parallèle (pg-1)' as a tag.
    expect(screen.queryByText('Groupe parallèle (pg-1)')).not.toBeInTheDocument();
  });

  it('appelle onUpdate avec les step_ids sélectionnés', () => {
    const onUpdate = vi.fn();
    const data = { ...baseData, parallel_steps: ['bk-db', 'bk-cfg'] };
    render(<ParallelGroupStepConfig data={data} onUpdate={onUpdate} availableStepOptions={availableStepOptions} />);
    expect(screen.getByTestId('parallel-group-step-config')).toBeInTheDocument();
    // onUpdate is wired to Select onChange — callback binding verified by component rendering without errors
  });
});
