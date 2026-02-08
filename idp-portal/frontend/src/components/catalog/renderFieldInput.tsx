/**
 * renderFieldInput - Renders the appropriate form input for a parameter field.
 * Extracted from ParametersFormStep (Story 20.4, Task 2).
 * Shared by ParametersFormStep and WorkflowStepsRenderer.
 */

import {
  Select,
  Input,
  InputNumber,
  Switch,
  DatePicker,
  Badge,
} from 'antd';
import type { InventoryItem } from '../../types/api';
import type { ParameterField } from '../../hooks/useDynamicForm';

export function renderFieldInput(
  field: ParameterField,
  inventoryData: Record<string, InventoryItem[]>,
  inventoryWarnings: Record<string, boolean>,
  loadingInventory: boolean,
) {
  if (field.inventorySource && inventoryData[field.inventorySource]) {
    const hasWarning = inventoryWarnings[field.inventorySource];
    return (
      <div>
        <Select
          placeholder={`Selectionnez ${field.label.toLowerCase()}`}
          aria-label={field.label}
          loading={loadingInventory}
          options={inventoryData[field.inventorySource].map((item) => ({
            value: item.id,
            label: item.name,
          }))}
        />
        {hasWarning && (
          <Badge
            status="warning"
            text="Données inventaire temporairement indisponibles — dernières valeurs en cache"
            style={{ marginTop: 4, fontSize: '12px', color: '#faad14' }}
          />
        )}
      </div>
    );
  }

  switch (field.type) {
    case 'select':
      return (
        <Select
          placeholder={`Selectionnez ${field.label.toLowerCase()}`}
          aria-label={field.label}
          options={(field.enum || []).map((v) => ({ value: v, label: v }))}
        />
      );
    case 'number':
    case 'integer':
      return (
        <InputNumber
          style={{ width: '100%' }}
          aria-label={field.label}
          min={field.minimum}
          max={field.maximum}
          precision={field.type === 'integer' ? 0 : undefined}
        />
      );
    case 'boolean':
      return <Switch aria-label={field.label} />;
    case 'date':
    case 'date-time':
      return (
        <DatePicker
          style={{ width: '100%' }}
          showTime={field.type === 'date-time'}
          aria-label={field.label}
        />
      );
    case 'array':
      return (
        <Select
          mode="tags"
          placeholder={`Entrez ${field.label.toLowerCase()}`}
          aria-label={field.label}
        />
      );
    default:
      return <Input aria-label={field.label} />;
  }
}
