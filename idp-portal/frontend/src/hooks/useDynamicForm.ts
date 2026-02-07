/**
 * useDynamicForm - Dynamic form generation from JSON Schema.
 * Extracted from ExecutionWizard.tsx (Story 17.2, Task 2.4).
 *
 * Parses parameters_schema and generates form field definitions.
 */

import { useMemo } from 'react';

export interface ParameterField {
  name: string;
  type: 'string' | 'number' | 'integer' | 'boolean' | 'date' | 'date-time' | 'select' | 'array';
  label: string;
  description?: string;
  required: boolean;
  enum?: string[];
  pattern?: string;
  minimum?: number;
  maximum?: number;
  default?: unknown;
  inventorySource?: 'databases' | 'servers';
}

export function extractParameterFields(schema: Record<string, unknown> | null): ParameterField[] {
  if (!schema) return [];

  const properties = schema.properties as Record<string, Record<string, unknown>> | undefined;
  const required = (schema.required as string[]) || [];

  if (!properties || typeof properties !== 'object') return [];

  return Object.entries(properties).map(([name, prop]) => {
    let type: ParameterField['type'] = 'string';
    const propType = prop?.type as string | undefined;
    const format = prop?.format as string | undefined;

    if (prop?.enum) {
      type = 'select';
    } else if (propType === 'array') {
      type = 'array';
    } else if (propType === 'number') {
      type = 'number';
    } else if (propType === 'integer') {
      type = 'integer';
    } else if (propType === 'boolean') {
      type = 'boolean';
    } else if (format === 'date') {
      type = 'date';
    } else if (format === 'date-time') {
      type = 'date-time';
    }

    return {
      name,
      type,
      label: (prop?.title as string) || name,
      description: prop?.description as string | undefined,
      required: required.includes(name),
      enum: prop?.enum as string[] | undefined,
      pattern: prop?.pattern as string | undefined,
      minimum: prop?.minimum as number | undefined,
      maximum: prop?.maximum as number | undefined,
      default: prop?.default,
      inventorySource: (prop as Record<string, unknown>)?.source === 'inventory'
        ? ((prop as Record<string, unknown>)?.inventory_type as 'databases' | 'servers' | undefined)
        : undefined,
    };
  });
}

export interface UseDynamicFormOptions {
  schema: Record<string, unknown> | null;
}

export interface UseDynamicFormReturn {
  parameterFields: ParameterField[];
}

export function useDynamicForm({ schema }: UseDynamicFormOptions): UseDynamicFormReturn {
  const parameterFields = useMemo(
    () => extractParameterFields(schema),
    [schema]
  );

  return { parameterFields };
}
