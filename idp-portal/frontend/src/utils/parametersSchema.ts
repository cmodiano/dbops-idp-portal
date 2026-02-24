/**
 * Parameters JSON Schema ↔ list conversion (Story 2.17, Task 1.2).
 * Build/parse parameters_schema (object with type, properties, required) for the visual editor.
 */

import type { ParameterDefinition } from '../types/api';

/** Minimal JSON Schema object shape for parameters (backend accepts type, properties, required, etc.). */
export interface ParametersJsonSchema {
  type?: string;
  properties?: Record<string, Record<string, unknown>>;
  required?: string[];
  [key: string]: unknown; // Index signature for compatibility with Record<string, unknown>
}

/**
 * Map schema property type/format/enum to ParameterSchemaType.
 */
function schemaPropToParamType(prop: Record<string, unknown>): ParameterDefinition['type'] {
  if (Array.isArray(prop.enum)) {
    return 'select';
  }
  const type = prop.type as string | undefined;
  const format = prop.format as string | undefined;
  if (type === 'string' && format === 'date') return 'date';
  if (type === 'string' && format === 'date-time') return 'date-time';
  if (type === 'number') return 'number';
  if (type === 'integer') return 'integer';
  if (type === 'boolean') return 'boolean';
  return 'string';
}

/**
 * Convert backend parameters_schema (JSON Schema object) to list of ParameterDefinition for the editor.
 * Handles existing actions (AC5 migration) and empty/null schema.
 */
export function schemaToParameterList(schema: ParametersJsonSchema | null | undefined): ParameterDefinition[] {
  if (!schema || typeof schema !== 'object') {
    return [];
  }
  const properties = schema.properties;
  const requiredList = Array.isArray(schema.required) ? schema.required : [];
  if (!properties || typeof properties !== 'object') {
    return [];
  }

  const list: ParameterDefinition[] = [];
  for (const name of Object.keys(properties)) {
    const prop = properties[name];
    if (!prop || typeof prop !== 'object') continue;
    const type = schemaPropToParamType(prop);
    const def: ParameterDefinition = {
      name,
      type,
      required: requiredList.includes(name),
      default: prop.default != null ? String(prop.default) : undefined,
      description: typeof prop.description === 'string' ? prop.description : undefined,
    };
    if (type === 'select' && Array.isArray(prop.enum)) {
      def.enum = prop.enum.map((v) => String(v));
    }
    // Story 23.5: Extract source and inventory_type from schema properties
    if (prop.source === 'inventory' || prop.source === 'manual') {
      def.source = prop.source as ParameterDefinition['source'];
    }
    if (typeof prop.inventory_type === 'string' && ['servers', 'instances', 'databases'].includes(prop.inventory_type)) {
      def.inventory_type = prop.inventory_type as ParameterDefinition['inventory_type'];
    }
    // Story 37.5: Extract inventory_value_column from schema properties
    if (typeof prop.inventory_value_column === 'string' && prop.inventory_value_column) {
      def.inventory_value_column = prop.inventory_value_column;
    }
    list.push(def);
  }
  return list;
}

/**
 * Map ParameterSchemaType to JSON Schema property type/format.
 */
function paramTypeToSchemaProp(type: ParameterDefinition['type'], enumValues?: string[]): Record<string, unknown> {
  if (type === 'select' && enumValues && enumValues.length > 0) {
    return { type: 'string', enum: enumValues };
  }
  if (type === 'date') return { type: 'string', format: 'date' };
  if (type === 'date-time') return { type: 'string', format: 'date-time' };
  if (type === 'integer') return { type: 'integer' };
  if (type === 'number') return { type: 'number' };
  if (type === 'boolean') return { type: 'boolean' };
  return { type: 'string' };
}

/**
 * Convert list of ParameterDefinition to parameters_schema (JSON Schema object) for backend.
 * Produces { type: "object", properties: {...}, required: [...] } accepted by backend validation.
 */
export function parameterListToSchema(list: ParameterDefinition[]): ParametersJsonSchema | null {
  if (!list.length) {
    return null;
  }
  const properties: Record<string, Record<string, unknown>> = {};
  const required: string[] = [];

  for (const p of list) {
    const name = (p.name || '').trim();
    if (!name) continue;
    const base = paramTypeToSchemaProp(p.type, p.enum);
    if (p.description) (base as Record<string, unknown>).description = p.description;
    if (p.default !== undefined && p.default !== '') {
      const parsed = parseDefaultByType(p.default, p.type);
      if (parsed !== undefined) (base as Record<string, unknown>).default = parsed;
    }
    // Story 23.5 AC2: Only write 'source' when 'inventory' (omit when 'manual' for backward compatibility)
    if (p.source === 'inventory') {
      (base as Record<string, unknown>).source = 'inventory';
      if (p.inventory_type) {
        (base as Record<string, unknown>).inventory_type = p.inventory_type;
      }
      // Story 37.5: Write inventory_value_column only within inventory source block
      if (p.inventory_value_column) {
        (base as Record<string, unknown>).inventory_value_column = p.inventory_value_column;
      }
    }
    properties[name] = base;
    if (p.required) required.push(name);
  }

  if (Object.keys(properties).length === 0) {
    return null;
  }
  return {
    type: 'object',
    properties,
    required: required.length > 0 ? required : undefined,
  };
}

function parseDefaultByType(value: string, type: ParameterDefinition['type']): unknown {
  if (type === 'number' || type === 'integer') {
    const n = Number(value);
    if (Number.isNaN(n)) return undefined;
    return type === 'integer' ? Math.floor(n) : n;
  }
  if (type === 'boolean') {
    const lower = value.toLowerCase();
    if (lower === 'true') return true;
    if (lower === 'false') return false;
    return undefined;
  }
  return value;
}
