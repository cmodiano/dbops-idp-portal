import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useDynamicForm, extractParameterFields } from './useDynamicForm';

describe('extractParameterFields', () => {
  it('returns empty array for null schema', () => {
    expect(extractParameterFields(null)).toEqual([]);
  });

  it('returns empty array for schema without properties', () => {
    expect(extractParameterFields({ type: 'object' })).toEqual([]);
  });

  it('extracts string fields', () => {
    const schema = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name', description: 'Enter name' },
      },
      required: ['name'],
    };
    const fields = extractParameterFields(schema);
    expect(fields).toHaveLength(1);
    expect(fields[0]).toMatchObject({
      name: 'name',
      type: 'string',
      label: 'Name',
      description: 'Enter name',
      required: true,
    });
  });

  it('extracts number and integer fields', () => {
    const schema = {
      type: 'object',
      properties: {
        count: { type: 'integer', title: 'Count', minimum: 0, maximum: 100 },
        price: { type: 'number', title: 'Price', minimum: 0.01 },
      },
      required: [],
    };
    const fields = extractParameterFields(schema);
    expect(fields).toHaveLength(2);
    expect(fields[0]).toMatchObject({ name: 'count', type: 'integer', minimum: 0, maximum: 100 });
    expect(fields[1]).toMatchObject({ name: 'price', type: 'number', minimum: 0.01 });
  });

  it('extracts boolean fields', () => {
    const schema = {
      type: 'object',
      properties: {
        enabled: { type: 'boolean', title: 'Enabled' },
      },
    };
    const fields = extractParameterFields(schema);
    expect(fields[0]).toMatchObject({ name: 'enabled', type: 'boolean' });
  });

  it('extracts select fields from enum', () => {
    const schema = {
      type: 'object',
      properties: {
        color: { type: 'string', title: 'Color', enum: ['red', 'green', 'blue'] },
      },
    };
    const fields = extractParameterFields(schema);
    expect(fields[0]).toMatchObject({ name: 'color', type: 'select', enum: ['red', 'green', 'blue'] });
  });

  it('extracts date and date-time fields', () => {
    const schema = {
      type: 'object',
      properties: {
        birthDate: { type: 'string', title: 'Birth Date', format: 'date' },
        createdAt: { type: 'string', title: 'Created At', format: 'date-time' },
      },
    };
    const fields = extractParameterFields(schema);
    expect(fields[0]).toMatchObject({ name: 'birthDate', type: 'date' });
    expect(fields[1]).toMatchObject({ name: 'createdAt', type: 'date-time' });
  });

  it('extracts array fields', () => {
    const schema = {
      type: 'object',
      properties: {
        tags: { type: 'array', title: 'Tags' },
      },
    };
    const fields = extractParameterFields(schema);
    expect(fields[0]).toMatchObject({ name: 'tags', type: 'array' });
  });

  it('extracts inventory source fields', () => {
    const schema = {
      type: 'object',
      properties: {
        database: { type: 'string', title: 'Database', source: 'inventory', inventory_type: 'databases' },
      },
    };
    const fields = extractParameterFields(schema);
    expect(fields[0]).toMatchObject({ name: 'database', inventorySource: 'databases' });
  });

  // Story 23.5: Inventory source with instances type
  it('extracts inventory source with instances type', () => {
    const schema = {
      type: 'object',
      properties: {
        instance_name: { type: 'string', title: 'Instance', source: 'inventory', inventory_type: 'instances' },
      },
    };
    const fields = extractParameterFields(schema);
    expect(fields[0]).toMatchObject({ name: 'instance_name', inventorySource: 'instances' });
  });

  it('extracts inventory source with servers type', () => {
    const schema = {
      type: 'object',
      properties: {
        server_name: { type: 'string', title: 'Serveur', source: 'inventory', inventory_type: 'servers' },
      },
    };
    const fields = extractParameterFields(schema);
    expect(fields[0]).toMatchObject({ name: 'server_name', inventorySource: 'servers' });
  });

  it('does not set inventorySource when source is not inventory', () => {
    const schema = {
      type: 'object',
      properties: {
        path: { type: 'string', title: 'Path', source: 'manual' },
      },
    };
    const fields = extractParameterFields(schema);
    expect(fields[0].inventorySource).toBeUndefined();
  });

  it('does not set inventorySource when source is absent', () => {
    const schema = {
      type: 'object',
      properties: {
        path: { type: 'string', title: 'Path' },
      },
    };
    const fields = extractParameterFields(schema);
    expect(fields[0].inventorySource).toBeUndefined();
  });

  it('handles mixed inventory and manual params', () => {
    const schema = {
      type: 'object',
      properties: {
        instance: { type: 'string', title: 'Instance', source: 'inventory', inventory_type: 'instances' },
        path: { type: 'string', title: 'Path' },
        db: { type: 'string', title: 'Base', source: 'inventory', inventory_type: 'databases' },
      },
      required: ['instance'],
    };
    const fields = extractParameterFields(schema);
    expect(fields[0].inventorySource).toBe('instances');
    expect(fields[1].inventorySource).toBeUndefined();
    expect(fields[2].inventorySource).toBe('databases');
  });

  it('uses field name as label when title is missing', () => {
    const schema = {
      type: 'object',
      properties: {
        my_field: { type: 'string' },
      },
    };
    const fields = extractParameterFields(schema);
    expect(fields[0].label).toBe('my_field');
  });

  it('extracts pattern for validation', () => {
    const schema = {
      type: 'object',
      properties: {
        email: { type: 'string', title: 'Email', pattern: '^[a-z@.]+$' },
      },
    };
    const fields = extractParameterFields(schema);
    expect(fields[0].pattern).toBe('^[a-z@.]+$');
  });
});

describe('useDynamicForm', () => {
  it('returns parameterFields from schema', () => {
    const schema = {
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name' },
      },
      required: ['name'],
    };
    const { result } = renderHook(() => useDynamicForm({ schema }));
    expect(result.current.parameterFields).toHaveLength(1);
    expect(result.current.parameterFields[0].name).toBe('name');
  });

  it('returns empty array for null schema', () => {
    const { result } = renderHook(() => useDynamicForm({ schema: null }));
    expect(result.current.parameterFields).toEqual([]);
  });

  it('memoizes result for same schema reference', () => {
    const schema = {
      type: 'object',
      properties: { x: { type: 'string', title: 'X' } },
    };
    const { result, rerender } = renderHook(() => useDynamicForm({ schema }));
    const first = result.current.parameterFields;
    rerender();
    expect(result.current.parameterFields).toBe(first);
  });
});

// Story 37.5: Tests pour inventoryValueColumn
describe('Story 37.5 - inventoryValueColumn extraction', () => {
  it('test_extracts_inventory_value_column_from_schema', () => {
    const schema = {
      type: 'object',
      properties: {
        db_name: {
          type: 'string',
          source: 'inventory',
          inventory_type: 'databases',
          inventory_value_column: 'id',
        },
      },
    };
    const fields = extractParameterFields(schema);
    expect(fields[0].inventorySource).toBe('databases');
    expect(fields[0].inventoryValueColumn).toBe('id');
  });

  it('test_absent_inventory_value_column_gives_undefined', () => {
    const schema = {
      type: 'object',
      properties: {
        srv: {
          type: 'string',
          source: 'inventory',
          inventory_type: 'servers',
        },
      },
    };
    const fields = extractParameterFields(schema);
    expect(fields[0].inventoryValueColumn).toBeUndefined();
  });

  it('test_inventory_value_column_ignored_when_not_inventory', () => {
    const schema = {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          source: 'manual',
          inventory_value_column: 'name',
        },
      },
    };
    const fields = extractParameterFields(schema);
    expect(fields[0].inventoryValueColumn).toBeUndefined();
  });
});
