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
  Alert,
} from 'antd';
import type { InventoryItem } from '../../types/api';
import type { ParameterField } from '../../hooks/useDynamicForm';

export function renderFieldInput(
  field: ParameterField,
  inventoryData: Record<string, InventoryItem[]>,
  inventoryWarnings: Record<string, boolean>,
  loadingInventory: boolean,
  /** Story 23.6 - Selected server names for filtering instances/databases. */
  selectedServerNames: string[] = [],
) {
  if (field.inventorySource) {
    const items = inventoryData[field.inventorySource] ?? [];
    const hasWarning = inventoryWarnings[field.inventorySource];

    // Story 23.6 - Show help message when no server selected for instance/database fields
    const needsServerSelection = (field.inventorySource === 'instances' || field.inventorySource === 'databases')
      && selectedServerNames.length === 0;

    if (needsServerSelection) {
      // Story 23.6 - Show help message when no server selected for instance/database fields
      // Note: French hardcoded per project config.yaml document_output_language
      const entityLabel = field.inventorySource === 'instances' ? 'instances' : 'bases de données';
      return (
        <div>
          <Alert
            type="info"
            showIcon
            closable={false}
            title={`Veuillez d'abord sélectionner un serveur à l'étape 1 pour afficher les ${entityLabel} disponibles.`}
            style={{ marginBottom: 8 }}
          />
          <Select
            placeholder={`Sélectionnez ${field.label.toLocaleLowerCase('fr-FR')}`}
            aria-label={field.label}
            disabled
            notFoundContent="Sélectionnez d'abord un serveur"
          />
        </div>
      );
    }

    const entityLabel = field.inventorySource === 'instances' ? 'instance'
      : field.inventorySource === 'databases' ? 'base de données'
      : field.inventorySource;
    const notFoundMessage = items.length === 0 && selectedServerNames.length > 0
      ? `Aucune ${entityLabel} disponible pour les serveurs sélectionnés`
      : 'Aucune donnée disponible';

    return (
      <div>
        <Select
          placeholder={`Sélectionnez ${field.label.toLocaleLowerCase('fr-FR')}`}
          aria-label={field.label}
          loading={loadingInventory}
          showSearch
          filterOption={(input, option) =>
            (String(option?.label ?? '')).toLowerCase().includes(input.toLowerCase())
          }
          notFoundContent={loadingInventory ? undefined : notFoundMessage}
          options={items.map((item) => {
            // Story 37.5: Use configured column if set, else default (id as value, name as label)
            if (field.inventoryValueColumn) {
              const colVal = (item as Record<string, unknown>)[field.inventoryValueColumn];
              const strVal = colVal != null && colVal !== '' ? String(colVal) : item.name;
              return { value: strVal, label: strVal };
            }
            return { value: item.id, label: item.name };
          })}
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
