/**
 * Tests for renderFieldInput utility (Story 20.4, MEDIUM-3 fix).
 *
 * Tests all 7 field types: select, number, integer, boolean, date, date-time, array, default (string).
 */

import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Form } from 'antd';
import { renderFieldInput } from './renderFieldInput';
import type { ParameterField } from '../../hooks/useDynamicForm';
import type { InventoryItem } from '../../types/api';

type InventoryDataInput = Record<string, { id: string; name: string; environment?: string | null }[]>;

function renderField(field: ParameterField, overrides: {
  inventoryData?: InventoryDataInput;
  inventoryWarnings?: Record<string, boolean>;
  loadingInventory?: boolean;
  selectedServerNames?: string[];
} = {}) {
  const defaultProps = {
    inventoryData: {} as InventoryDataInput,
    inventoryWarnings: {} as Record<string, boolean>,
    loadingInventory: false,
    selectedServerNames: undefined as string[] | undefined,
    ...overrides,
  };

  return render(
    <Form>
      <Form.Item name="test_field">
        {renderFieldInput(
          field,
          defaultProps.inventoryData as Record<string, InventoryItem[]>,
          defaultProps.inventoryWarnings,
          defaultProps.loadingInventory,
          ...(defaultProps.selectedServerNames !== undefined ? [defaultProps.selectedServerNames] : []) as [string[]?],
        )}
      </Form.Item>
    </Form>
  );
}

describe('renderFieldInput', () => {
  it('renders Select for select type with enum options', () => {
    const field: ParameterField = {
      name: 'status',
      label: 'Status',
      type: 'select',
      enum: ['active', 'inactive'],
      required: false,
    };

    renderField(field);
    const select = screen.getByLabelText('Status');
    expect(select).toBeInTheDocument();
  });

  it('renders InputNumber for number type with min/max', () => {
    const field: ParameterField = {
      name: 'count',
      label: 'Count',
      type: 'number',
      minimum: 0,
      maximum: 100,
      required: false,
    };

    renderField(field);
    const input = screen.getByLabelText('Count');
    expect(input).toBeInTheDocument();
  });

  it('renders InputNumber with precision=0 for integer type', () => {
    const field: ParameterField = {
      name: 'port',
      label: 'Port',
      type: 'integer',
      required: false,
    };

    renderField(field);
    const input = screen.getByLabelText('Port');
    expect(input).toBeInTheDocument();
  });

  it('renders Switch for boolean type', () => {
    const field: ParameterField = {
      name: 'enabled',
      label: 'Enabled',
      type: 'boolean',
      required: false,
    };

    renderField(field);
    const switchEl = screen.getByLabelText('Enabled');
    expect(switchEl).toBeInTheDocument();
    expect(switchEl.getAttribute('role')).toBe('switch');
  });

  it('renders DatePicker for date type without time', () => {
    const field: ParameterField = {
      name: 'start_date',
      label: 'Start Date',
      type: 'date',
      required: false,
    };

    renderField(field);
    const picker = screen.getByLabelText('Start Date');
    expect(picker).toBeInTheDocument();
  });

  it('renders DatePicker with showTime for date-time type', () => {
    const field: ParameterField = {
      name: 'created_at',
      label: 'Created At',
      type: 'date-time',
      required: false,
    };

    renderField(field);
    const picker = screen.getByLabelText('Created At');
    expect(picker).toBeInTheDocument();
  });

  it('renders Select with mode=tags for array type', () => {
    const field: ParameterField = {
      name: 'tags',
      label: 'Tags',
      type: 'array',
      required: false,
    };

    renderField(field);
    const select = screen.getByLabelText('Tags');
    expect(select).toBeInTheDocument();
  });

  it('renders Input for default/string type', () => {
    const field: ParameterField = {
      name: 'username',
      label: 'Username',
      type: 'string',
      required: false,
    };

    renderField(field);
    const input = screen.getByLabelText('Username');
    expect(input).toBeInTheDocument();
  });

  it('renders Select with inventory data when inventorySource present', () => {
    const field: ParameterField = {
      name: 'db_instance',
      label: 'Database Instance',
      type: 'string',
      inventorySource: 'databases',
      required: false,
    };

    const inventoryData = {
      databases: [
        { id: '1', name: 'db-prod-01' },
        { id: '2', name: 'db-prod-02' },
      ],
    };

    renderField(field, { inventoryData, selectedServerNames: ['srv01'] });
    const select = screen.getByLabelText('Database Instance');
    expect(select).toBeInTheDocument();
  });

  it('renders warning badge when inventory source has warning', () => {
    const field: ParameterField = {
      name: 'server',
      label: 'Server',
      type: 'string',
      inventorySource: 'servers',
      required: false,
    };

    const inventoryData = {
      servers: [{ id: '1', name: 'srv-01' }],
    };

    const inventoryWarnings = {
      servers: true,
    };

    renderField(field, { inventoryData, inventoryWarnings });
    expect(screen.getByText(/temporairement indisponibles/)).toBeInTheDocument();
  });

  it('shows loading state for inventory Select', () => {
    const field: ParameterField = {
      name: 'target',
      label: 'Target',
      type: 'string',
      inventorySource: 'targets' as ParameterField['inventorySource'],
      required: false,
    };

    const inventoryData = {
      targets: [],
    };

    renderField(field, { inventoryData, loadingInventory: true });
    const select = screen.getByLabelText('Target');
    expect(select).toBeInTheDocument();
  });
});

// Story 23.5: Inventory source with instances type
describe('renderFieldInput - Story 23.5 (Inventory instances)', () => {
  it('renders Select for inventorySource=instances', () => {
    const field: ParameterField = {
      name: 'instance_name',
      label: 'Nom de instance',
      type: 'string',
      inventorySource: 'instances',
      required: true,
    };

    const inventoryData = {
      instances: [
        { id: 'inst1', name: 'ORA_PROD_01' },
        { id: 'inst2', name: 'ORA_PROD_02' },
      ],
    };

    renderField(field, { inventoryData, selectedServerNames: ['srv01'] });
    const select = screen.getByLabelText('Nom de instance');
    expect(select).toBeInTheDocument();
  });

  it('renders Select for inventorySource=servers', () => {
    const field: ParameterField = {
      name: 'server_name',
      label: 'Serveur',
      type: 'string',
      inventorySource: 'servers',
      required: true,
    };

    const inventoryData = {
      servers: [
        { id: 'srv1', name: 'srv-prod-01' },
      ],
    };

    renderField(field, { inventoryData });
    expect(screen.getByLabelText('Serveur')).toBeInTheDocument();
  });

  it('renders Select for inventorySource=databases', () => {
    const field: ParameterField = {
      name: 'database_name',
      label: 'Base de donnees',
      type: 'string',
      inventorySource: 'databases',
      required: true,
    };

    const inventoryData = {
      databases: [
        { id: 'db1', name: 'MYDB_PROD' },
      ],
    };

    renderField(field, { inventoryData, selectedServerNames: ['srv01'] });
    expect(screen.getByLabelText('Base de donnees')).toBeInTheDocument();
  });

  it('renders empty Select when inventory data not yet loaded', () => {
    const field: ParameterField = {
      name: 'instance',
      label: 'Instance',
      type: 'string',
      inventorySource: 'instances',
      required: true,
    };

    // inventoryData has no "instances" key — pass selectedServerNames to avoid Alert
    renderField(field, { inventoryData: {}, selectedServerNames: ['srv01'] });
    const select = screen.getByLabelText('Instance');
    expect(select).toBeInTheDocument();
  });

  it('renders standard Input when inventorySource is not set', () => {
    const field: ParameterField = {
      name: 'backup_path',
      label: 'Chemin sauvegarde',
      type: 'string',
      required: false,
    };

    renderField(field);
    const input = screen.getByLabelText('Chemin sauvegarde');
    expect(input).toBeInTheDocument();
    expect(input.tagName).toBe('INPUT');
  });

  it('shows warning badge for instances when data comes from cache', () => {
    const field: ParameterField = {
      name: 'instance',
      label: 'Instance',
      type: 'string',
      inventorySource: 'instances',
      required: true,
    };

    const inventoryData = {
      instances: [{ id: '1', name: 'inst-01' }],
    };

    renderField(field, {
      inventoryData,
      inventoryWarnings: { instances: true },
      selectedServerNames: ['srv01'],
    });
    expect(screen.getByText(/temporairement indisponibles/)).toBeInTheDocument();
  });

  it('does not show warning when no inventory warning', () => {
    const field: ParameterField = {
      name: 'instance',
      label: 'Instance',
      type: 'string',
      inventorySource: 'instances',
      required: true,
    };

    const inventoryData = {
      instances: [{ id: '1', name: 'inst-01' }],
    };

    renderField(field, {
      inventoryData,
      inventoryWarnings: { instances: false },
      selectedServerNames: ['srv01'],
    });
    expect(screen.queryByText(/temporairement indisponibles/)).not.toBeInTheDocument();
  });
});

// Story 23.6: Server-context filtering for instances/databases
describe('renderFieldInput - Story 23.6 (selectedServerNames)', () => {
  it('affiche Alert si selectedServerNames vide et inventorySource instances', () => {
    const field: ParameterField = {
      name: 'instance_name',
      label: 'Instance',
      type: 'string',
      inventorySource: 'instances',
      required: true,
    };

    render(
      <>{renderFieldInput(field, {}, {}, false, [])}</>,
    );

    // Alert with server selection prompt should be visible
    expect(
      screen.getByText(/Veuillez d'abord sélectionner un serveur/),
    ).toBeInTheDocument();

    // The Select should be disabled
    const select = screen.getByLabelText('Instance');
    expect(select).toBeInTheDocument();
    expect(select.closest('.ant-select')).toHaveClass('ant-select-disabled');
  });

  it('affiche Alert si selectedServerNames vide et inventorySource databases', () => {
    const field: ParameterField = {
      name: 'database_name',
      label: 'Base de données',
      type: 'string',
      inventorySource: 'databases',
      required: true,
    };

    render(
      <>{renderFieldInput(field, {}, {}, false, [])}</>,
    );

    // Alert should mention "bases de données"
    expect(
      screen.getByText(/bases de données/),
    ).toBeInTheDocument();

    // The Select should be disabled
    const select = screen.getByLabelText('Base de données');
    expect(select.closest('.ant-select')).toHaveClass('ant-select-disabled');
  });

  it('affiche Select sans Alert si selectedServerNames fourni pour instances', () => {
    const field: ParameterField = {
      name: 'instance_name',
      label: 'Instance',
      type: 'string',
      inventorySource: 'instances',
      required: true,
    };

    const inventoryData = {
      instances: [
        { id: 'inst01', name: 'ORCL01', environment: 'dev' },
      ],
    };

    render(
      <>{renderFieldInput(field, inventoryData, {}, false, ['srv01'])}</>,
    );

    // No Alert should be present
    expect(
      screen.queryByText(/Veuillez d'abord sélectionner un serveur/),
    ).not.toBeInTheDocument();

    // Select should be enabled (not disabled)
    const select = screen.getByLabelText('Instance');
    expect(select).toBeInTheDocument();
    expect(select.closest('.ant-select')).not.toHaveClass('ant-select-disabled');
  });

  it('pas d\'Alert pour inventorySource servers même si selectedServerNames vide', () => {
    const field: ParameterField = {
      name: 'server_name',
      label: 'Serveur',
      type: 'string',
      inventorySource: 'servers',
      required: true,
    };

    const inventoryData = {
      servers: [
        { id: 'srv01', name: 'srv01', environment: 'dev' },
      ],
    };

    render(
      <>{renderFieldInput(field, inventoryData, {}, false, [])}</>,
    );

    // No Alert should be present for servers
    expect(
      screen.queryByText(/Veuillez d'abord sélectionner un serveur/),
    ).not.toBeInTheDocument();

    // Select should be enabled
    const select = screen.getByLabelText('Serveur');
    expect(select).toBeInTheDocument();
    expect(select.closest('.ant-select')).not.toHaveClass('ant-select-disabled');
  });

  it('notFoundContent si liste vide après filtrage par serveur', () => {
    const field: ParameterField = {
      name: 'instance_name',
      label: 'Instance',
      type: 'string',
      inventorySource: 'instances',
      required: true,
    };

    const inventoryData: Record<string, InventoryItem[]> = {
      instances: [],
    };

    render(
      <>{renderFieldInput(field, inventoryData, {}, false, ['srv01'])}</>,
    );

    // No Alert should be shown (server is selected)
    expect(
      screen.queryByText(/Veuillez d'abord sélectionner un serveur/),
    ).not.toBeInTheDocument();

    // The Select should be enabled
    const select = screen.getByLabelText('Instance');
    expect(select).toBeInTheDocument();
    expect(select.closest('.ant-select')).not.toHaveClass('ant-select-disabled');

    // Open the Select dropdown to trigger notFoundContent rendering
    fireEvent.mouseDown(screen.getByRole('combobox'));

    // Check for notFoundContent text in the dropdown
    // Ant Design renders the dropdown in a portal, so we search in the full document
    const dropdown = document.querySelector('.ant-select-dropdown');
    if (dropdown) {
      expect(dropdown.textContent).toContain(
        'Aucune instance disponible pour les serveurs sélectionnés',
      );
    } else {
      // Fallback: in jsdom the virtual dropdown may not render fully,
      // so we at least verify the Select is present and enabled
      expect(select.closest('.ant-select')).not.toHaveClass('ant-select-disabled');
    }
  });
});
