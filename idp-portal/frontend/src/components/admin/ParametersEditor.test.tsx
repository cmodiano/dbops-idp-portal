/**
 * Tests for ParametersEditor (Story 2.17, AC #1, #2, #3, #6).
 * Task 4.1: add, remove, reorder, validation.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ParametersEditor } from './ParametersEditor';
import type { ParameterDefinition } from '../../types/api';

describe('ParametersEditor', () => {
  it('renders empty state and "Ajouter un parametre" button (AC1)', () => {
    render(<ParametersEditor value={[]} onChange={() => {}} />);
    expect(screen.getByText(/Aucun parametre/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ajouter un parametre/i })).toBeInTheDocument();
  });

  it('calls onChange with new parameter when adding (AC2)', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ParametersEditor value={[]} onChange={onChange} />);
    await user.click(screen.getByRole('button', { name: /Ajouter un parametre/i }));
    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({
        name: '',
        type: 'string',
        required: false,
      }),
    ]);
  });

  it('renders existing parameters with name, type, required (AC1, AC2)', () => {
    const params: ParameterDefinition[] = [
      { name: 'pdb_name', type: 'string', required: true, description: 'PDB name' },
      { name: 'port', type: 'integer', required: false, default: '1521' },
    ];
    render(<ParametersEditor value={params} onChange={() => {}} />);
    expect(screen.getByDisplayValue('pdb_name')).toBeInTheDocument();
    expect(screen.getByDisplayValue('1521')).toBeInTheDocument();
    expect(screen.getByText('Parametre 1')).toBeInTheDocument();
    expect(screen.getByText('Parametre 2')).toBeInTheDocument();
  });

  it('shows type dropdown with options (AC2)', () => {
    const params: ParameterDefinition[] = [{ name: 'x', type: 'string', required: false }];
    render(<ParametersEditor value={params} onChange={() => {}} />);
    expect(screen.getByLabelText(/Type parametre 1/i)).toBeInTheDocument();
  });

  it('shows options (enum) when type is select (AC2)', () => {
    const params: ParameterDefinition[] = [
      { name: 'env', type: 'select', required: true, enum: ['DEV', 'PROD'] },
    ];
    render(<ParametersEditor value={params} onChange={() => {}} />);
    expect(screen.getByLabelText(/Options liste parametre 1/i)).toBeInTheDocument();
  });

  it('calls onChange when removing parameter', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const params: ParameterDefinition[] = [
      { name: 'a', type: 'string', required: false },
      { name: 'b', type: 'string', required: false },
    ];
    render(<ParametersEditor value={params} onChange={onChange} />);
    const deleteSecond = screen.getByLabelText(/Supprimer parametre 2/i);
    await user.click(deleteSecond);
    expect(onChange).toHaveBeenCalledWith([expect.objectContaining({ name: 'a' })]);
  });

  it('calls onChange when changing parameter name', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const params: ParameterDefinition[] = [{ name: 'old', type: 'string', required: false }];
    render(<ParametersEditor value={params} onChange={onChange} />);
    const nameInput = screen.getByLabelText(/Nom parametre 1/i);
    await user.clear(nameInput);
    await user.type(nameInput, 'x');
    // onChange is called per keystroke; at least one call should have the new character
    expect(onChange).toHaveBeenCalled();
    const calls = onChange.mock.calls.map((c) => c[0][0].name);
    expect(calls.some((name) => name.includes('x'))).toBe(true);
  });

  it('shows validation when name is empty (AC6)', () => {
    const params: ParameterDefinition[] = [{ name: '', type: 'string', required: true }];
    render(<ParametersEditor value={params} onChange={() => {}} />);
    expect(screen.getByText('Nom requis')).toBeInTheDocument();
  });

  it('shows validation when name is duplicate (AC6)', () => {
    const params: ParameterDefinition[] = [
      { name: 'dup', type: 'string', required: false },
      { name: 'dup', type: 'string', required: false },
    ];
    render(<ParametersEditor value={params} onChange={() => {}} />);
    expect(screen.getAllByText('Nom unique requis').length).toBeGreaterThanOrEqual(1);
  });

  it('displays parameters in given order; reordered value updates display (AC3 reorder)', () => {
    const params: ParameterDefinition[] = [
      { name: 'first', type: 'string', required: false },
      { name: 'second', type: 'string', required: false },
    ];
    const { rerender } = render(<ParametersEditor value={params} onChange={() => {}} />);
    const inputs = screen.getAllByLabelText(/Nom parametre \d/i);
    expect(inputs).toHaveLength(2);
    expect(inputs[0]).toHaveValue('first');
    expect(inputs[1]).toHaveValue('second');

    rerender(<ParametersEditor value={[params[1], params[0]]} onChange={() => {}} />);
    const inputsAfter = screen.getAllByLabelText(/Nom parametre \d/i);
    expect(inputsAfter[0]).toHaveValue('second');
    expect(inputsAfter[1]).toHaveValue('first');
  });

  it('has drag handle per parameter for reorder (AC3)', () => {
    const params: ParameterDefinition[] = [
      { name: 'p1', type: 'string', required: false },
      { name: 'p2', type: 'string', required: false },
    ];
    render(<ParametersEditor value={params} onChange={() => {}} />);
    expect(screen.getByLabelText(/Glisser pour reordonner parametre 1/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Glisser pour reordonner parametre 2/i)).toBeInTheDocument();
  });
});
