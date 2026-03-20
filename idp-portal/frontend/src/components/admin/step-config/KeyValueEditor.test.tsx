/**
 * Tests for KeyValueEditor — Story 57.20, Task 2.
 * Tests the helpContent and label props added in Story 57.20.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { KeyValueEditor } from './KeyValueEditor';

describe('KeyValueEditor — helpContent prop (Story 57.20)', () => {
  it('renders helpContent next to label when both are provided', () => {
    render(
      <KeyValueEditor
        value={{}}
        onChange={vi.fn()}
        label="Mapping d'entrée"
        helpContent={<span data-testid="help-icon">?</span>}
      />
    );
    expect(screen.getByText("Mapping d'entrée")).toBeInTheDocument();
    expect(screen.getByTestId('help-icon')).toBeInTheDocument();
  });

  it('renders helpContent alone when no label is provided', () => {
    render(
      <KeyValueEditor
        value={{}}
        onChange={vi.fn()}
        helpContent={<span data-testid="help-icon">?</span>}
      />
    );
    expect(screen.getByTestId('help-icon')).toBeInTheDocument();
  });

  it('does not render help area when neither label nor helpContent is provided', () => {
    const { container } = render(
      <KeyValueEditor
        value={{}}
        onChange={vi.fn()}
      />
    );
    // Should only have the button "Ajouter une entrée" and no label/help
    expect(screen.queryByText("Mapping d'entrée")).not.toBeInTheDocument();
    expect(container.querySelector('[data-testid="help-icon"]')).not.toBeInTheDocument();
  });

  it('renders label without helpContent when only label is provided', () => {
    render(
      <KeyValueEditor
        value={{}}
        onChange={vi.fn()}
        label="Mapping de sortie"
      />
    );
    expect(screen.getByText("Mapping de sortie")).toBeInTheDocument();
  });
});

describe('KeyValueEditor — warnings prop (Story 57.20, Task 5)', () => {
  it('renders warning Alert when warnings are provided', () => {
    render(
      <KeyValueEditor
        value={{}}
        onChange={vi.fn()}
        warnings={["Référence inconnue : step_id 'xyz' n'existe pas dans ce workflow"]}
        data-testid="test-editor"
      />
    );
    expect(screen.getByTestId('test-editor-warning')).toBeInTheDocument();
    expect(screen.getByText(/Référence inconnue : step_id 'xyz'/)).toBeInTheDocument();
  });

  it('does not render warning when warnings array is empty', () => {
    render(
      <KeyValueEditor
        value={{}}
        onChange={vi.fn()}
        warnings={[]}
        data-testid="test-editor"
      />
    );
    expect(screen.queryByTestId('test-editor-warning')).not.toBeInTheDocument();
  });

  it('does not render warning when warnings is undefined', () => {
    render(
      <KeyValueEditor
        value={{}}
        onChange={vi.fn()}
        data-testid="test-editor"
      />
    );
    expect(screen.queryByTestId('test-editor-warning')).not.toBeInTheDocument();
  });
});

describe('KeyValueEditor — add, edit, remove', () => {
  it('adds new row when clicking Ajouter une entrée', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<KeyValueEditor value={{ a: '1' }} onChange={onChange} />);

    await user.click(screen.getByText('Ajouter une entrée'));

    // New empty row is added (not emitted until key is filled)
    expect(screen.getAllByPlaceholderText('Clé')).toHaveLength(2);
  });

  it('emits onChange when editing key', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<KeyValueEditor value={{ a: '1' }} onChange={onChange} />);

    const keyInput = screen.getByDisplayValue('a');
    await user.clear(keyInput);
    await user.type(keyInput, 'b');

    expect(onChange).toHaveBeenCalledWith({ b: '1' });
  });

  it('emits onChange when editing value', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<KeyValueEditor value={{ a: '1' }} onChange={onChange} />);

    const valueInput = screen.getByDisplayValue('1');
    await user.clear(valueInput);
    await user.type(valueInput, '2');

    expect(onChange).toHaveBeenCalledWith({ a: '2' });
  });

  it('emits onChange when removing row', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<KeyValueEditor value={{ a: '1', b: '2' }} onChange={onChange} />);

    const deleteButtons = screen.getAllByLabelText(/Supprimer l'entrée/);
    await user.click(deleteButtons[0]);

    expect(onChange).toHaveBeenCalledWith({ b: '2' });
  });

  it('renders with custom placeholders', () => {
    render(
      <KeyValueEditor
        value={{ x: 'y' }}
        onChange={vi.fn()}
        keyPlaceholder="Header"
        valuePlaceholder="Value"
      />
    );
    expect(screen.getByPlaceholderText('Header')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Value')).toBeInTheDocument();
  });

  it('does not show add/remove when disabled', () => {
    render(<KeyValueEditor value={{ a: '1' }} onChange={vi.fn()} disabled />);
    expect(screen.queryByText('Ajouter une entrée')).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Supprimer/)).not.toBeInTheDocument();
  });
});
