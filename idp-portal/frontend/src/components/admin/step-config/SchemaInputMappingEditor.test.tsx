/**
 * Tests for SchemaInputMappingEditor — Story 84-4, AC4.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SchemaInputMappingEditor } from './SchemaInputMappingEditor';

const schema3props = {
  type: 'object',
  required: ['short_description'],
  properties: {
    short_description: { type: 'string', title: 'Description courte' },
    change_type: { type: 'string', title: 'Type de change', description: 'normal, standard ou emergency' },
    change_model_code: { type: 'string', title: 'Code modèle de change' },
  },
};

describe('SchemaInputMappingEditor', () => {
  it('rend les champs avec les bons labels depuis schema.properties', () => {
    render(<SchemaInputMappingEditor schema={schema3props} value={null} onChange={vi.fn()} />);
    expect(screen.getByText('Description courte')).toBeInTheDocument();
    expect(screen.getByText('Type de change')).toBeInTheDocument();
    expect(screen.getByText('Code modèle de change')).toBeInTheDocument();
  });

  it('rend 3 champs pour un schema à 3 propriétés', () => {
    render(<SchemaInputMappingEditor schema={schema3props} value={null} onChange={vi.fn()} />);
    const container = screen.getByTestId('schema-input-mapping-editor');
    const inputs = container.querySelectorAll('input');
    expect(inputs).toHaveLength(3);
  });

  it('affiche le marqueur * rouge pour les champs dans required', () => {
    render(<SchemaInputMappingEditor schema={schema3props} value={null} onChange={vi.fn()} />);
    // Le champ requis (short_description) doit avoir un "*" dans le DOM
    const requiredMarkers = screen.getAllByText('*');
    expect(requiredMarkers.length).toBeGreaterThanOrEqual(1);
  });

  it("n'affiche pas d'astérisque pour les champs non requis", () => {
    const schemaNoRequired = {
      type: 'object',
      properties: {
        change_type: { type: 'string', title: 'Type de change' },
      },
    };
    render(<SchemaInputMappingEditor schema={schemaNoRequired} value={null} onChange={vi.fn()} />);
    expect(screen.queryByText('*')).not.toBeInTheDocument();
  });

  it('onChange émet la valeur fusionnée sans toucher les autres clés', () => {
    const handleChange = vi.fn();
    const initialValue = { short_description: 'Initial', change_type: 'normal' };
    render(<SchemaInputMappingEditor schema={schema3props} value={initialValue} onChange={handleChange} />);

    const inputs = screen.getByTestId('schema-input-mapping-editor').querySelectorAll('input');
    // Premier input = short_description (ordre d'insertion des propriétés dans schema3props —
    // JS/V8 préserve l'ordre d'insertion pour les string keys, cohérent avec Object.entries)
    fireEvent.change(inputs[0], { target: { value: 'Nouveau texte' } });

    expect(handleChange).toHaveBeenCalledWith({
      short_description: 'Nouveau texte',
      change_type: 'normal',
    });
  });

  it('onChange sur champ avec value=null initialise correctement', () => {
    const handleChange = vi.fn();
    render(<SchemaInputMappingEditor schema={schema3props} value={null} onChange={handleChange} />);

    const inputs = screen.getByTestId('schema-input-mapping-editor').querySelectorAll('input');
    fireEvent.change(inputs[0], { target: { value: 'test' } });

    expect(handleChange).toHaveBeenCalledWith({ short_description: 'test' });
  });

  it('retourne null si schema.properties est absent', () => {
    const { container } = render(
      <SchemaInputMappingEditor schema={{ type: 'object' }} value={null} onChange={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('retourne null si schema.properties est vide', () => {
    const { container } = render(
      <SchemaInputMappingEditor schema={{ type: 'object', properties: {} }} value={null} onChange={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('affiche la valeur courante dans le champ', () => {
    render(
      <SchemaInputMappingEditor
        schema={schema3props}
        value={{ short_description: 'Valeur existante', change_type: '', change_model_code: '' }}
        onChange={vi.fn()}
      />,
    );
    const inputs = screen.getByTestId('schema-input-mapping-editor').querySelectorAll('input');
    expect((inputs[0] as HTMLInputElement).value).toBe('Valeur existante');
  });

  it('utilise description comme placeholder si title absent', () => {
    const schemaWithDesc = {
      type: 'object',
      properties: {
        my_field: { type: 'string', description: 'Mon placeholder custom' },
      },
    };
    render(<SchemaInputMappingEditor schema={schemaWithDesc} value={null} onChange={vi.fn()} />);
    expect(screen.getByPlaceholderText('Mon placeholder custom')).toBeInTheDocument();
  });

  it('utilise le placeholder par défaut si ni title ni description', () => {
    const schemaMinimal = {
      type: 'object',
      properties: {
        my_field: { type: 'string' },
      },
    };
    render(<SchemaInputMappingEditor schema={schemaMinimal} value={null} onChange={vi.fn()} />);
    expect(screen.getByPlaceholderText('{{ steps.<step_id>.output.<champ> }}')).toBeInTheDocument();
  });

  it('data-testid="schema-input-mapping-editor" sur le container principal', () => {
    render(<SchemaInputMappingEditor schema={schema3props} value={null} onChange={vi.fn()} />);
    expect(screen.getByTestId('schema-input-mapping-editor')).toBeInTheDocument();
  });

  it('désactive tous les inputs quand disabled=true', () => {
    render(<SchemaInputMappingEditor schema={schema3props} value={null} onChange={vi.fn()} disabled={true} />);
    const inputs = screen.getByTestId('schema-input-mapping-editor').querySelectorAll('input');
    expect(inputs.length).toBeGreaterThan(0);
    inputs.forEach((input) => {
      expect(input).toBeDisabled();
    });
  });

  it('les inputs sont actifs par défaut (disabled non fourni)', () => {
    render(<SchemaInputMappingEditor schema={schema3props} value={null} onChange={vi.fn()} />);
    const inputs = screen.getByTestId('schema-input-mapping-editor').querySelectorAll('input');
    inputs.forEach((input) => {
      expect(input).not.toBeDisabled();
    });
  });
});
