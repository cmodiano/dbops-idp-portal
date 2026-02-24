/**
 * Unit tests for parameters JSON Schema ↔ list conversion (Story 2.17, Task 1.2).
 */

import { describe, it, expect } from 'vitest';
import { schemaToParameterList, parameterListToSchema } from './parametersSchema';
import type { ParameterDefinition } from '../types/api';

describe('schemaToParameterList', () => {
  it('returns empty array for null or undefined', () => {
    expect(schemaToParameterList(null)).toEqual([]);
    expect(schemaToParameterList(undefined)).toEqual([]);
  });

  it('returns empty array when properties is missing', () => {
    expect(schemaToParameterList({ type: 'object' })).toEqual([]);
  });

  it('converts simple properties to ParameterDefinition list', () => {
    const schema = {
      type: 'object',
      properties: {
        pdb_name: { type: 'string', description: 'PDB name' },
        port: { type: 'integer', default: 1521 },
        enabled: { type: 'boolean' },
      },
      required: ['pdb_name'],
    };
    const list = schemaToParameterList(schema);
    expect(list).toHaveLength(3);
    expect(list[0]).toMatchObject({ name: 'pdb_name', type: 'string', required: true, description: 'PDB name' });
    expect(list[1]).toMatchObject({ name: 'port', type: 'integer', required: false, default: '1521' });
    expect(list[2]).toMatchObject({ name: 'enabled', type: 'boolean', required: false });
  });

  it('handles date and date-time format', () => {
    const schema = {
      type: 'object',
      properties: {
        start_date: { type: 'string', format: 'date' },
        created_at: { type: 'string', format: 'date-time' },
      },
    };
    const list = schemaToParameterList(schema);
    expect(list[0].type).toBe('date');
    expect(list[1].type).toBe('date-time');
  });

  it('handles enum as select type with enum array', () => {
    const schema = {
      type: 'object',
      properties: {
        env: { type: 'string', enum: ['DEV', 'STAGING', 'PROD'] },
      },
      required: ['env'],
    };
    const list = schemaToParameterList(schema);
    expect(list).toHaveLength(1);
    expect(list[0]).toMatchObject({ name: 'env', type: 'select', required: true, enum: ['DEV', 'STAGING', 'PROD'] });
  });
});

describe('parameterListToSchema', () => {
  it('returns null for empty list', () => {
    expect(parameterListToSchema([])).toBeNull();
  });

  it('builds schema with type, properties, required', () => {
    const list: ParameterDefinition[] = [
      { name: 'pdb_name', type: 'string', required: true, description: 'PDB name' },
      { name: 'port', type: 'integer', required: false, default: '1521' },
    ];
    const schema = parameterListToSchema(list);
    expect(schema).not.toBeNull();
    expect(schema?.type).toBe('object');
    expect(schema?.properties?.pdb_name).toMatchObject({ type: 'string', description: 'PDB name' });
    expect(schema?.properties?.port).toMatchObject({ type: 'integer', default: 1521 });
    expect(schema?.required).toEqual(['pdb_name']);
  });

  it('outputs date/date-time as string with format', () => {
    const list: ParameterDefinition[] = [
      { name: 'd', type: 'date', required: false },
      { name: 'dt', type: 'date-time', required: false },
    ];
    const schema = parameterListToSchema(list);
    expect(schema?.properties?.d).toEqual({ type: 'string', format: 'date' });
    expect(schema?.properties?.dt).toEqual({ type: 'string', format: 'date-time' });
  });

  it('outputs select type as string with enum', () => {
    const list: ParameterDefinition[] = [
      { name: 'env', type: 'select', required: true, enum: ['DEV', 'PROD'] },
    ];
    const schema = parameterListToSchema(list);
    expect(schema?.properties?.env).toEqual({ type: 'string', enum: ['DEV', 'PROD'] });
    expect(schema?.required).toContain('env');
  });

  it('round-trip: schema -> list -> schema preserves structure', () => {
    const original = {
      type: 'object',
      properties: {
        a: { type: 'string', description: 'A' },
        b: { type: 'number', required: false },
        c: { type: 'string', enum: ['X', 'Y'] },
      },
      required: ['a'],
    };
    const list = schemaToParameterList(original);
    const back = parameterListToSchema(list);
    expect(back?.type).toBe('object');
    expect(back?.properties?.a).toMatchObject({ type: 'string', description: 'A' });
    expect(back?.properties?.b?.type).toBe('number');
    expect(back?.properties?.c).toMatchObject({ type: 'string', enum: ['X', 'Y'] });
    expect(back?.required).toEqual(['a']);
  });
});

// Story 23.5: Tests for source and inventory_type round-trip
describe('Story 23.5 - Inventory source/type in parameters schema', () => {
  describe('schemaToParameterList', () => {
    it('extracts source=inventory and inventory_type from schema property', () => {
      const schema = {
        type: 'object',
        properties: {
          instance_name: {
            type: 'string',
            source: 'inventory',
            inventory_type: 'instances',
          },
        },
        required: ['instance_name'],
      };
      const list = schemaToParameterList(schema);
      expect(list).toHaveLength(1);
      expect(list[0]).toMatchObject({
        name: 'instance_name',
        type: 'string',
        required: true,
        source: 'inventory',
        inventory_type: 'instances',
      });
    });

    it('extracts source=manual from schema property', () => {
      const schema = {
        type: 'object',
        properties: {
          path: { type: 'string', source: 'manual' },
        },
      };
      const list = schemaToParameterList(schema);
      expect(list[0].source).toBe('manual');
      expect(list[0].inventory_type).toBeUndefined();
    });

    it('handles param without source (backward compat)', () => {
      const schema = {
        type: 'object',
        properties: {
          path: { type: 'string' },
        },
      };
      const list = schemaToParameterList(schema);
      expect(list[0].source).toBeUndefined();
      expect(list[0].inventory_type).toBeUndefined();
    });

    it('extracts all valid inventory_type values', () => {
      const schema = {
        type: 'object',
        properties: {
          srv: { type: 'string', source: 'inventory', inventory_type: 'servers' },
          inst: { type: 'string', source: 'inventory', inventory_type: 'instances' },
          db: { type: 'string', source: 'inventory', inventory_type: 'databases' },
        },
      };
      const list = schemaToParameterList(schema);
      expect(list[0].inventory_type).toBe('servers');
      expect(list[1].inventory_type).toBe('instances');
      expect(list[2].inventory_type).toBe('databases');
    });

    it('ignores invalid inventory_type value', () => {
      const schema = {
        type: 'object',
        properties: {
          x: { type: 'string', source: 'inventory', inventory_type: 'unknown' },
        },
      };
      const list = schemaToParameterList(schema);
      expect(list[0].inventory_type).toBeUndefined();
    });
  });

  describe('parameterListToSchema', () => {
    it('includes source and inventory_type for inventory params', () => {
      const list: ParameterDefinition[] = [
        {
          name: 'instance_name',
          type: 'string',
          required: true,
          source: 'inventory',
          inventory_type: 'instances',
        },
      ];
      const schema = parameterListToSchema(list);
      expect(schema?.properties?.instance_name).toMatchObject({
        type: 'string',
        source: 'inventory',
        inventory_type: 'instances',
      });
    });

    it('does not include source/inventory_type for manual params', () => {
      const list: ParameterDefinition[] = [
        { name: 'path', type: 'string', required: false, source: 'manual' },
      ];
      const schema = parameterListToSchema(list);
      expect(schema?.properties?.path).toEqual({ type: 'string' });
      expect(schema?.properties?.path).not.toHaveProperty('source');
      expect(schema?.properties?.path).not.toHaveProperty('inventory_type');
    });

    it('does not include source/inventory_type for params without source', () => {
      const list: ParameterDefinition[] = [
        { name: 'path', type: 'string', required: false },
      ];
      const schema = parameterListToSchema(list);
      expect(schema?.properties?.path).not.toHaveProperty('source');
    });

    it('mixed params: inventory and manual', () => {
      const list: ParameterDefinition[] = [
        {
          name: 'db_name',
          type: 'string',
          required: true,
          source: 'inventory',
          inventory_type: 'databases',
        },
        {
          name: 'backup_path',
          type: 'string',
          required: true,
          source: 'manual',
        },
      ];
      const schema = parameterListToSchema(list);
      expect(schema?.properties?.db_name).toMatchObject({
        source: 'inventory',
        inventory_type: 'databases',
      });
      expect(schema?.properties?.backup_path).not.toHaveProperty('source');
    });
  });

  describe('round-trip', () => {
    it('preserves source=inventory and inventory_type through conversion', () => {
      const original = {
        type: 'object',
        properties: {
          instance_name: {
            type: 'string',
            source: 'inventory',
            inventory_type: 'instances',
            description: 'Nom de instance',
          },
          backup_path: {
            type: 'string',
            description: 'Chemin sauvegarde',
          },
        },
        required: ['instance_name'],
      };
      const list = schemaToParameterList(original);
      const back = parameterListToSchema(list);
      expect(back?.properties?.instance_name).toMatchObject({
        type: 'string',
        source: 'inventory',
        inventory_type: 'instances',
        description: 'Nom de instance',
      });
      expect(back?.properties?.backup_path).not.toHaveProperty('source');
      expect(back?.required).toEqual(['instance_name']);
    });
  });
});

// Story 37.5: Tests pour inventory_value_column
describe('Story 37.5 - inventory_value_column in parameters schema', () => {
  it('test_schema_to_list_extracts_inventory_value_column', () => {
    const schema = {
      type: 'object',
      properties: {
        inst_ref: {
          type: 'string',
          source: 'inventory',
          inventory_type: 'instances',
          inventory_value_column: 'server_ref',
        },
      },
    };
    const list = schemaToParameterList(schema);
    expect(list).toHaveLength(1);
    expect(list[0].inventory_value_column).toBe('server_ref');
    expect(list[0].source).toBe('inventory');
    expect(list[0].inventory_type).toBe('instances');
  });

  it('test_schema_to_list_absent_inventory_value_column', () => {
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
    const list = schemaToParameterList(schema);
    expect(list[0].inventory_value_column).toBeUndefined();
  });

  it('test_list_to_schema_writes_inventory_value_column', () => {
    const list: ParameterDefinition[] = [
      {
        name: 'env_ref',
        type: 'string',
        required: false,
        source: 'inventory',
        inventory_type: 'servers',
        inventory_value_column: 'environment',
      },
    ];
    const schema = parameterListToSchema(list);
    expect(schema?.properties?.env_ref).toMatchObject({
      source: 'inventory',
      inventory_type: 'servers',
      inventory_value_column: 'environment',
    });
  });

  it('test_list_to_schema_omits_inventory_value_column_when_absent', () => {
    const list: ParameterDefinition[] = [
      {
        name: 'srv',
        type: 'string',
        required: false,
        source: 'inventory',
        inventory_type: 'servers',
      },
    ];
    const schema = parameterListToSchema(list);
    expect(schema?.properties?.srv).not.toHaveProperty('inventory_value_column');
  });

  it('test_round_trip_inventory_value_column', () => {
    const original = {
      type: 'object',
      properties: {
        db_ref: {
          type: 'string',
          source: 'inventory',
          inventory_type: 'databases',
          inventory_value_column: 'id',
        },
      },
      required: ['db_ref'],
    };
    const list = schemaToParameterList(original);
    const back = parameterListToSchema(list);
    expect(back?.properties?.db_ref).toMatchObject({
      source: 'inventory',
      inventory_type: 'databases',
      inventory_value_column: 'id',
    });
    expect(back?.required).toContain('db_ref');
  });
});
