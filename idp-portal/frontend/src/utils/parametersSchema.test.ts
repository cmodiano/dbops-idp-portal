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
