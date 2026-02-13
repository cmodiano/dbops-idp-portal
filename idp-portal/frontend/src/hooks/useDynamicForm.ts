/**
 * useDynamicForm - Dynamic form generation from JSON Schema.
 * Extracted from ExecutionWizard.tsx (Story 17.2, Task 2.4).
 *
 * Parses parameters_schema and generates form field definitions.
 */

import { useMemo } from 'react';
import type { InventorySourceType } from '../types/api';
import logger from '../services/logger';

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
  /** Story 23.5: Inventory source type for inventory-backed fields. */
  inventorySource?: InventorySourceType;
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
      inventorySource: (() => {
        if ((prop as Record<string, unknown>)?.source !== 'inventory') return undefined;
        const invType = (prop as Record<string, unknown>)?.inventory_type as string | undefined;
        if (!invType) {
          logger.warn(`Parameter '${name}': source=inventory but inventory_type is missing`);
          return undefined;
        }
        const validTypes: InventorySourceType[] = ['databases', 'servers', 'instances'];
        if (!validTypes.includes(invType as InventorySourceType)) {
          logger.warn(`Parameter '${name}': unknown inventory_type '${invType}', falling back to text input`);
          return undefined;
        }
        return invType as InventorySourceType;
      })(),
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
