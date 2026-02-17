/**
 * Tests for AvailableActionsPanel (Story 24.2 AC3, AC4, AC8).
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AvailableActionsPanel } from './AvailableActionsPanel';
import type { IntegrationTypeCatalogue } from '../../types/api';

const mockTypeWithActions: IntegrationTypeCatalogue = {
  code: 'aap',
  name: 'Ansible Automation Platform',
  description: 'Exécution de jobs Ansible',
  version: '1.0',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  actions: [
    {
      id: 1,
      action_code: 'start_job',
      action_label: 'Démarrer un job',
      description: 'Lance un job template AAP',
      required_params: {
        properties: {
          job_template_id: { type: 'integer', description: 'ID du job template' },
          inventory_id: { type: 'integer', description: 'ID de l\'inventaire' },
        },
      },
      optional_params: {
        properties: {
          extra_vars: { type: 'object', description: 'Variables extra' },
        },
      },
      response_format: {},
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    {
      id: 2,
      action_code: 'cancel_job',
      action_label: 'Annuler un job',
      description: 'Annule un job en cours',
      required_params: { properties: { job_id: { type: 'integer', description: 'ID du job' } } },
      optional_params: {},
      response_format: {},
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    {
      id: 3,
      action_code: 'inactive_action',
      action_label: 'Action inactive',
      description: 'Cette action est désactivée',
      required_params: {},
      optional_params: {},
      response_format: {},
      is_active: false,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ],
};

const mockTypeNoActions: IntegrationTypeCatalogue = {
  code: 'servicenow',
  name: 'ServiceNow ITSM',
  description: 'Gestion des change requests',
  version: '1.1',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  actions: [],
};

describe('AvailableActionsPanel', () => {
  it('renders nothing when selectedType is null', () => {
    const { container } = render(<AvailableActionsPanel selectedType={null} />);
    expect(container.innerHTML).toBe('');
  });

  it('AC3: displays actions table with correct columns', () => {
    render(<AvailableActionsPanel selectedType={mockTypeWithActions} />);

    expect(screen.getByText('Actions disponibles')).toBeInTheDocument();
    expect(screen.getByText('Démarrer un job')).toBeInTheDocument();
    expect(screen.getByText('start_job')).toBeInTheDocument();
    expect(screen.getByText('Lance un job template AAP')).toBeInTheDocument();
    expect(screen.getByText('Annuler un job')).toBeInTheDocument();
    expect(screen.getByText('cancel_job')).toBeInTheDocument();
  });

  it('AC3: only shows active actions', () => {
    render(<AvailableActionsPanel selectedType={mockTypeWithActions} />);

    expect(screen.getByText('Démarrer un job')).toBeInTheDocument();
    expect(screen.getByText('Annuler un job')).toBeInTheDocument();
    expect(screen.queryByText('Action inactive')).not.toBeInTheDocument();
  });

  it('AC3: shows required params badge count', () => {
    render(<AvailableActionsPanel selectedType={mockTypeWithActions} />);

    // "Démarrer un job" has 2 required params
    expect(screen.getByText('2 requis')).toBeInTheDocument();
    // "Annuler un job" has 1 required param
    expect(screen.getByText('1 requis')).toBeInTheDocument();
  });

  it('AC3: shows empty message when type has no actions', () => {
    render(<AvailableActionsPanel selectedType={mockTypeNoActions} />);

    expect(screen.getByText('Actions disponibles')).toBeInTheDocument();
    expect(screen.getByText(/Aucune action définie pour ce type/)).toBeInTheDocument();
  });

  it('AC8: displays version badge', () => {
    render(<AvailableActionsPanel selectedType={mockTypeWithActions} />);
    expect(screen.getByText('Version 1.0')).toBeInTheDocument();
  });

  it('AC8: displays different version for different type', () => {
    render(<AvailableActionsPanel selectedType={mockTypeNoActions} />);
    expect(screen.getByText('Version 1.1')).toBeInTheDocument();
  });

  it('AC4: can expand row to see parameter details', async () => {
    const user = userEvent.setup();
    render(<AvailableActionsPanel selectedType={mockTypeWithActions} />);

    // Click expand button on first row
    const expandButtons = document.querySelectorAll('.ant-table-row-expand-icon');
    expect(expandButtons.length).toBeGreaterThan(0);
    await user.click(expandButtons[0]);

    // Verify required params are shown
    expect(screen.getByText('Paramètres requis :')).toBeInTheDocument();
    expect(screen.getByText('job_template_id')).toBeInTheDocument();
    expect(screen.getByText(/ID du job template/)).toBeInTheDocument();

    // Verify optional params are shown
    expect(screen.getByText('Paramètres optionnels :')).toBeInTheDocument();
    expect(screen.getByText('extra_vars')).toBeInTheDocument();
    expect(screen.getByText(/Variables extra/)).toBeInTheDocument();
  });

  it('AC4: shows "Schéma non disponible" when params schema is empty', async () => {
    const typeWithEmptyParams: IntegrationTypeCatalogue = {
      ...mockTypeWithActions,
      actions: [
        {
          ...mockTypeWithActions.actions[0],
          required_params: {},
          optional_params: {},
        },
      ],
    };

    const user = userEvent.setup();
    render(<AvailableActionsPanel selectedType={typeWithEmptyParams} />);

    const expandButtons = document.querySelectorAll('.ant-table-row-expand-icon');
    await user.click(expandButtons[0]);

    const schemaMessages = screen.getAllByText(/Schéma non disponible/);
    expect(schemaMessages.length).toBeGreaterThanOrEqual(2); // Both required and optional
  });
});
