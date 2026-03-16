import { describe, it, expect, vi } from 'vitest';
import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SchemaFormRenderer } from './SchemaFormRenderer';

// ---------------------------------------------------------------------------
// AC2 — string
// ---------------------------------------------------------------------------
describe('SchemaFormRenderer — string field', () => {
  it('renders_string_field_as_input', () => {
    render(
      <SchemaFormRenderer
        schema={{ properties: { username: { type: 'string', title: 'Nom utilisateur' } } }}
        value={{ username: 'test' }}
        onChange={vi.fn()}
      />
    );
    expect(screen.getByRole('textbox', { name: /nom utilisateur/i })).toBeInTheDocument();
  });

  it('calls_onChange_on_string_field_change', async () => {
    const handleChange = vi.fn();
    // Wrapper stateful nécessaire car le composant est contrôlé
    function Wrapper() {
      const [val, setVal] = useState<Record<string, unknown>>({ name: '' });
      return (
        <SchemaFormRenderer
          schema={{ properties: { name: { type: 'string', title: 'Nom' } } }}
          value={val}
          onChange={(v) => { setVal(v); handleChange(v); }}
        />
      );
    }
    render(<Wrapper />);
    await userEvent.type(screen.getByRole('textbox', { name: /nom/i }), 'hello');
    expect(handleChange).toHaveBeenCalled();
    const lastCall = handleChange.mock.calls[handleChange.mock.calls.length - 1][0];
    expect(lastCall.name).toBe('hello');
  });
});

// ---------------------------------------------------------------------------
// AC3 — number / integer
// ---------------------------------------------------------------------------
describe('SchemaFormRenderer — number field', () => {
  it('renders_number_field_as_input_number', () => {
    render(
      <SchemaFormRenderer
        schema={{ properties: { count: { type: 'number', title: 'Compteur' } } }}
        value={{ count: 42 }}
        onChange={vi.fn()}
      />
    );
    // InputNumber renders as a spinbutton
    expect(screen.getByRole('spinbutton', { name: /compteur/i })).toBeInTheDocument();
  });

  it('renders_integer_field_with_precision_zero', () => {
    render(
      <SchemaFormRenderer
        schema={{ properties: { qty: { type: 'integer', title: 'Quantité' } } }}
        value={{ qty: 5 }}
        onChange={vi.fn()}
      />
    );
    const input = screen.getByRole('spinbutton', { name: /quantité/i });
    expect(input).toBeInTheDocument();
    // step="1" indicates precision=0
    expect(input).toHaveAttribute('step', '1');
  });
});

// ---------------------------------------------------------------------------
// AC4 — boolean
// ---------------------------------------------------------------------------
describe('SchemaFormRenderer — boolean field', () => {
  it('renders_boolean_field_as_switch', () => {
    render(
      <SchemaFormRenderer
        schema={{ properties: { enabled: { type: 'boolean', title: 'Activé' } } }}
        value={{ enabled: false }}
        onChange={vi.fn()}
      />
    );
    expect(screen.getByRole('switch', { name: /activé/i })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// AC5 — enum
// ---------------------------------------------------------------------------
describe('SchemaFormRenderer — enum field', () => {
  it('renders_enum_field_as_select', async () => {
    render(
      <SchemaFormRenderer
        schema={{ properties: { color: { enum: ['a', 'b'], title: 'Couleur' } } }}
        value={{}}
        onChange={vi.fn()}
      />
    );
    // Ant Design Select renders as combobox
    const combobox = screen.getByRole('combobox', { name: /couleur/i });
    expect(combobox).toBeInTheDocument();
    // Open the dropdown and verify options 'a' and 'b' are present (AC5.2)
    // Ant Design renders visible option items with a title attribute matching the label
    await userEvent.click(combobox);
    expect(screen.getByTitle('a')).toBeInTheDocument();
    expect(screen.getByTitle('b')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// AC6 — array simple (tags)
// ---------------------------------------------------------------------------
describe('SchemaFormRenderer — array field', () => {
  it('renders_array_simple_as_tags_select', () => {
    render(
      <SchemaFormRenderer
        schema={{ properties: { tags: { type: 'array', items: { type: 'string' }, title: 'Tags' } } }}
        value={{ tags: [] }}
        onChange={vi.fn()}
      />
    );
    // mode="tags" also renders as combobox in antd
    expect(screen.getByRole('combobox', { name: /tags/i })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// AC7 — object with sub-properties
// ---------------------------------------------------------------------------
describe('SchemaFormRenderer — object with sub-properties', () => {
  it('renders_object_simple_nested_fields', () => {
    render(
      <SchemaFormRenderer
        schema={{
          properties: {
            config: {
              type: 'object',
              title: 'Config',
              properties: {
                host: { type: 'string', title: 'Hôte' },
                port: { type: 'number', title: 'Port' },
              },
            },
          },
        }}
        value={{ config: { host: 'localhost', port: 8080 } }}
        onChange={vi.fn()}
      />
    );
    expect(screen.getByRole('textbox', { name: /hôte/i })).toBeInTheDocument();
    expect(screen.getByRole('spinbutton', { name: /port/i })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// AC7 — nested object onChange propagation
// ---------------------------------------------------------------------------
describe('SchemaFormRenderer — object onChange propagation', () => {
  it('calls_onChange_for_nested_object_field', async () => {
    const handleChange = vi.fn();
    function Wrapper() {
      const [val, setVal] = useState<Record<string, unknown>>({
        config: { host: 'localhost', port: 8080 },
      });
      return (
        <SchemaFormRenderer
          schema={{
            properties: {
              config: {
                type: 'object',
                title: 'Config',
                properties: {
                  host: { type: 'string', title: 'Hôte' },
                  port: { type: 'number', title: 'Port' },
                },
              },
            },
          }}
          value={val}
          onChange={(v) => { setVal(v); handleChange(v); }}
        />
      );
    }
    render(<Wrapper />);
    const hostInput = screen.getByRole('textbox', { name: /hôte/i });
    await userEvent.clear(hostInput);
    await userEvent.type(hostInput, 'newhost');
    expect(handleChange).toHaveBeenCalled();
    const lastCall = handleChange.mock.calls[handleChange.mock.calls.length - 1][0];
    expect(lastCall.config.host).toBe('newhost');
    // Verify the sibling field is preserved
    expect(lastCall.config.port).toBe(8080);
  });
});

// ---------------------------------------------------------------------------
// AC8 — mapping key/value (additionalProperties)
// ---------------------------------------------------------------------------
describe('SchemaFormRenderer — mapping key/value', () => {
  it('renders_mapping_key_value_editor', () => {
    render(
      <SchemaFormRenderer
        schema={{
          properties: {
            env: {
              type: 'object',
              additionalProperties: { type: 'string' },
              title: 'Variables d\'environnement',
            },
          },
        }}
        value={{ env: { KEY1: 'val1' } }}
        onChange={vi.fn()}
      />
    );
    // Should render "Ajouter" button
    expect(screen.getByRole('button', { name: /ajouter/i })).toBeInTheDocument();
    // Should render the existing key/value inputs
    const inputs = screen.getAllByRole('textbox');
    // Key and value fields for KEY1=val1
    expect(inputs.length).toBeGreaterThanOrEqual(2);
  });
});

// ---------------------------------------------------------------------------
// MappingEditor interactions
// ---------------------------------------------------------------------------
describe('SchemaFormRenderer — mapping interactions', () => {
  const mappingSchema = {
    properties: {
      env: {
        type: 'object',
        additionalProperties: { type: 'string' },
        title: 'Env',
      },
    },
  };

  it('mapping_add_row_on_button_click', async () => {
    const handleChange = vi.fn();
    render(
      <SchemaFormRenderer
        schema={mappingSchema}
        value={{ env: {} }}
        onChange={handleChange}
      />
    );
    const addBtn = screen.getByRole('button', { name: /ajouter/i });
    await userEvent.click(addBtn);
    // After click, a new empty row appears — at least 2 textboxes (clé + valeur)
    expect(screen.getAllByRole('textbox').length).toBeGreaterThanOrEqual(2);
  });

  it('mapping_update_key_calls_onChange', async () => {
    const handleChange = vi.fn();
    render(
      <SchemaFormRenderer
        schema={mappingSchema}
        value={{ env: { mykey: 'myval' } }}
        onChange={handleChange}
      />
    );
    // First textbox is the key input
    const inputs = screen.getAllByRole('textbox');
    const keyInput = inputs[0];
    await userEvent.clear(keyInput);
    await userEvent.type(keyInput, 'newkey');
    expect(handleChange).toHaveBeenCalled();
  });

  it('mapping_update_value_calls_onChange', async () => {
    const handleChange = vi.fn();
    render(
      <SchemaFormRenderer
        schema={mappingSchema}
        value={{ env: { k: 'v' } }}
        onChange={handleChange}
      />
    );
    const inputs = screen.getAllByRole('textbox');
    const valInput = inputs[1];
    await userEvent.clear(valInput);
    await userEvent.type(valInput, 'newval');
    expect(handleChange).toHaveBeenCalled();
  });

  it('mapping_remove_row_on_delete_click', async () => {
    const handleChange = vi.fn();
    render(
      <SchemaFormRenderer
        schema={mappingSchema}
        value={{ env: { k1: 'v1' } }}
        onChange={handleChange}
      />
    );
    const deleteBtn = screen.getByRole('button', { name: /supprimer/i });
    await userEvent.click(deleteBtn);
    expect(handleChange).toHaveBeenCalledWith({ env: {} });
  });

  it('mapping_disabled_hides_add_and_delete_buttons', () => {
    render(
      <SchemaFormRenderer
        schema={mappingSchema}
        value={{ env: { k: 'v' } }}
        onChange={vi.fn()}
        disabled={true}
      />
    );
    expect(screen.queryByRole('button', { name: /ajouter/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /supprimer/i })).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// description rendering
// ---------------------------------------------------------------------------
describe('SchemaFormRenderer — description', () => {
  it('renders_string_field_description', () => {
    render(
      <SchemaFormRenderer
        schema={{
          properties: {
            host: { type: 'string', title: 'Hôte', description: 'ex: localhost' },
          },
        }}
        value={{}}
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText('ex: localhost')).toBeInTheDocument();
  });

  it('renders_boolean_field_with_description', () => {
    render(
      <SchemaFormRenderer
        schema={{
          properties: {
            active: { type: 'boolean', title: 'Actif', description: 'Activer ou non' },
          },
        }}
        value={{ active: false }}
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText('Activer ou non')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// object without properties and without additionalProperties → null input
// ---------------------------------------------------------------------------
describe('SchemaFormRenderer — object null case', () => {
  it('renders_object_without_properties_or_additional_renders_nothing', () => {
    const { container } = render(
      <SchemaFormRenderer
        schema={{
          properties: {
            meta: { type: 'object', title: 'Meta' },
          },
        }}
        value={{}}
        onChange={vi.fn()}
      />
    );
    // No inputs should be rendered (null case)
    expect(container.querySelector('input')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// string field uses title as label when title absent → falls back to key
// ---------------------------------------------------------------------------
describe('SchemaFormRenderer — label fallback', () => {
  it('uses_field_key_as_label_when_title_absent', () => {
    render(
      <SchemaFormRenderer
        schema={{ properties: { username: { type: 'string' } } }}
        value={{}}
        onChange={vi.fn()}
      />
    );
    // aria-label should be the key "username"
    expect(screen.getByRole('textbox', { name: /username/i })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// AC1 — customRenderers prop
// ---------------------------------------------------------------------------
describe('SchemaFormRenderer — customRenderers', () => {
  it('custom renderer fourni pour field_a est appelé et son output est dans le DOM', () => {
    const schema = {
      properties: {
        field_a: { type: 'string', title: 'Champ A' },
      },
    };
    render(
      <SchemaFormRenderer
        schema={schema}
        value={{ field_a: 'hello' }}
        onChange={vi.fn()}
        customRenderers={{
          field_a: () => <button>custom-widget-a</button>,
        }}
      />
    );
    expect(screen.getByRole('button', { name: /custom-widget-a/i })).toBeInTheDocument();
    // Le rendu standard (textbox) ne doit pas être présent
    expect(screen.queryByRole('textbox', { name: /champ a/i })).not.toBeInTheDocument();
  });

  it('schema à 2 props avec custom renderer sur 1 seule — les deux sont rendus correctement', () => {
    const schema = {
      properties: {
        field_a: { type: 'string', title: 'Champ A' },
        field_b: { type: 'string', title: 'Champ B' },
      },
    };
    render(
      <SchemaFormRenderer
        schema={schema}
        value={{ field_a: 'a', field_b: 'b' }}
        onChange={vi.fn()}
        customRenderers={{
          field_a: () => <button>custom-widget-a</button>,
        }}
      />
    );
    // field_a : custom renderer
    expect(screen.getByRole('button', { name: /custom-widget-a/i })).toBeInTheDocument();
    // field_b : rendu standard (textbox)
    expect(screen.getByRole('textbox', { name: /champ b/i })).toBeInTheDocument();
  });

  it('label du schema est affiché autour du custom renderer', () => {
    const schema = {
      properties: {
        field_a: { type: 'string', title: 'Mon Label', description: 'Ma description' },
      },
    };
    render(
      <SchemaFormRenderer
        schema={schema}
        value={{ field_a: '' }}
        onChange={vi.fn()}
        customRenderers={{
          field_a: () => <span data-testid="custom-input">widget</span>,
        }}
      />
    );
    // Le label du schema doit être visible
    expect(screen.getByText('Mon Label')).toBeInTheDocument();
    // La description aussi
    expect(screen.getByText('Ma description')).toBeInTheDocument();
    // Le custom input est là
    expect(screen.getByTestId('custom-input')).toBeInTheDocument();
  });

  it('disabled=true est transmis au custom renderer via le 3e argument', () => {
    const receivedArgs: boolean[] = [];
    const schema = {
      properties: {
        field_a: { type: 'string', title: 'Champ A' },
      },
    };
    render(
      <SchemaFormRenderer
        schema={schema}
        value={{ field_a: 'test' }}
        onChange={vi.fn()}
        disabled={true}
        customRenderers={{
          field_a: (_value, _onChange, isDisabled) => {
            receivedArgs.push(isDisabled);
            return <span data-testid="custom-disabled">widget</span>;
          },
        }}
      />
    );
    expect(screen.getByTestId('custom-disabled')).toBeInTheDocument();
    expect(receivedArgs).toContain(true);
  });
});

// ---------------------------------------------------------------------------
// AC1.4 — schéma vide
// ---------------------------------------------------------------------------
describe('SchemaFormRenderer — empty schema', () => {
  it('renders_empty_schema_without_error', () => {
    const { container } = render(
      <SchemaFormRenderer schema={{}} value={{}} onChange={vi.fn()} />
    );
    // Should render an empty div without crashing
    expect(container.firstChild).toBeInTheDocument();
    expect(container.querySelector('input')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// disabled propagation
// ---------------------------------------------------------------------------
describe('SchemaFormRenderer — disabled', () => {
  it('disabled_propagates_to_all_inputs', () => {
    const { container } = render(
      <SchemaFormRenderer
        schema={{
          properties: {
            a: { type: 'string', title: 'A' },
            b: { type: 'number', title: 'B' },
            c: { type: 'boolean', title: 'C' },
          },
        }}
        value={{}}
        onChange={vi.fn()}
        disabled={true}
      />
    );
    // HTML input elements (string, number) should be disabled
    container.querySelectorAll('input').forEach((input) => {
      expect(input).toBeDisabled();
    });
    // Switch (boolean) renders as a button and should also be disabled
    expect(screen.getByRole('switch', { name: /c/i })).toBeDisabled();
  });
});
