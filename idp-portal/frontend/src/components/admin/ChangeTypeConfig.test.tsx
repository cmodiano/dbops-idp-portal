/**
 * Tests for ChangeTypeConfig (Story 2.24 + Story 21.4 + Story 31.4).
 * Two-block layout: Gates (allowed, maintenance, approval) + ServiceNow (required, model/template, change type).
 * Unified "Modèle / Template ID" field merging Code modèle + Template ID.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChangeTypeConfig } from './ChangeTypeConfig';
import { useEnvironments } from '../../hooks/useEnvironments';
import { useServiceNowIntegrations } from '../../hooks/useServiceNowIntegrations';

vi.mock('../../hooks/useEnvironments', () => ({
  useEnvironments: vi.fn(),
}));

vi.mock('../../hooks/useServiceNowIntegrations', () => ({
  useServiceNowIntegrations: vi.fn(),
}));

const mockUseEnvironments = useEnvironments as ReturnType<typeof vi.fn>;
const mockUseServiceNowIntegrations = useServiceNowIntegrations as ReturnType<typeof vi.fn>;

const defaultSnMock = {
  integrations: [],
  integrationOptions: [],
  loading: false,
  error: null,
};

const defaultEnvMock = {
  environments: ['dev', 'staging', 'prod'],
  environmentOptions: [
    { value: 'dev', label: 'Développement' },
    { value: 'staging', label: 'Staging' },
    { value: 'prod', label: 'Production' },
  ],
  loading: false,
  error: null,
};

describe('ChangeTypeConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseEnvironments.mockReturnValue(defaultEnvMock);
    mockUseServiceNowIntegrations.mockReturnValue(defaultSnMock);
  });

  it('renders table with environments from hook', () => {
    render(<ChangeTypeConfig value={{}} onChange={() => {}} />);
    expect(screen.getByRole('table', { name: /Configuration type de changement/i })).toBeInTheDocument();
    // Each env appears twice (once per block)
    expect(screen.getAllByText('Développement')).toHaveLength(2);
    expect(screen.getAllByText('Staging')).toHaveLength(2);
    expect(screen.getAllByText('Production')).toHaveLength(2);
  });

  // Story 31.4: two-block layout with separate headers
  it('renders two-block headers: Gates and Changement ServiceNow', () => {
    render(<ChangeTypeConfig value={{}} onChange={() => {}} />);
    // Bloc 1 — Gates
    expect(screen.getByRole('group', { name: /Gates/i })).toBeInTheDocument();
    expect(screen.getByText('Autorisé')).toBeInTheDocument();
    expect(screen.getByText('Plage maintenance')).toBeInTheDocument();
    expect(screen.getByText('Approbation')).toBeInTheDocument();
    // Bloc 2 — ServiceNow
    expect(screen.getByRole('group', { name: /Changement ServiceNow/i })).toBeInTheDocument();
    expect(screen.getByText('Changement requis')).toBeInTheDocument();
    expect(screen.getByText('Modèle / Template ID')).toBeInTheDocument();
    expect(screen.getByText('Change type')).toBeInTheDocument();
  });

  // Story 31.4: no more separate "Code modèle" and "Template ID" columns
  it('does not render separate Code modèle or Template ID column headers', () => {
    render(<ChangeTypeConfig value={{}} onChange={() => {}} />);
    expect(screen.queryByText('Code modèle')).not.toBeInTheDocument();
    expect(screen.queryByText('Template ID')).not.toBeInTheDocument();
  });

  it('when required is true for prod, shows unified model/template input', () => {
    render(
      <ChangeTypeConfig value={{ prod: { required: true, change_model_code: '1516B' } }} onChange={() => {}} />
    );
    const prodInput = screen.getByLabelText(/Modèle \/ Template ID pour prod/i);
    expect(prodInput).toBeInTheDocument();
    expect(prodInput).toHaveValue('1516B');
  });

  it('calls onChange when toggling Switch', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ChangeTypeConfig value={{}} onChange={onChange} />);
    const devSwitch = screen.getByLabelText(/Changement requis pour dev/i);
    await user.click(devSwitch);
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ dev: expect.objectContaining({ required: true }) }));
  });

  // Story 31.4: Gates block switches
  it('calls onChange when toggling Autorisé switch', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ChangeTypeConfig value={{}} onChange={onChange} />);
    const devSwitch = screen.getByLabelText(/Exécution autorisée pour dev/i);
    await user.click(devSwitch);
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ dev: expect.objectContaining({ allowed: false }) }));
  });

  it('calls onChange when toggling Plage maintenance switch', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ChangeTypeConfig value={{}} onChange={onChange} />);
    const devSwitch = screen.getByLabelText(/Plage de maintenance requise pour dev/i);
    await user.click(devSwitch);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ dev: expect.objectContaining({ requires_maintenance_window: true }) })
    );
  });

  it('calls onChange when toggling Approbation switch', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ChangeTypeConfig value={{}} onChange={onChange} />);
    const devSwitch = screen.getByLabelText(/Approbation requise pour dev/i);
    await user.click(devSwitch);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ dev: expect.objectContaining({ requires_approval: true }) })
    );
  });

  it('calls onChange when typing in unified model/template field', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ChangeTypeConfig value={{ prod: { required: true, change_model_code: '' } }} onChange={onChange} />
    );
    const input = screen.getByLabelText(/Modèle \/ Template ID pour prod/i);
    await user.type(input, 'CHG_TPL');
    expect(onChange).toHaveBeenCalled();
    // Verify both fields are written
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall.prod.change_model_code).toBeDefined();
    expect(lastCall.prod.template_id).toBeDefined();
    expect(lastCall.prod.change_model_code).toBe(lastCall.prod.template_id);
  });

  // Story 31.4: unified field reads template_id with fallback to change_model_code
  it('displays template_id value in the unified field (priority over change_model_code)', () => {
    render(
      <ChangeTypeConfig
        value={{ prod: { required: true, template_id: 'TPL_A', change_model_code: 'CODE_B' } }}
        onChange={() => {}}
      />
    );
    const input = screen.getByLabelText(/Modèle \/ Template ID pour prod/i);
    expect(input).toHaveValue('TPL_A');
  });

  it('falls back to change_model_code when template_id is empty', () => {
    render(
      <ChangeTypeConfig
        value={{ prod: { required: true, change_model_code: 'CODE_B' } }}
        onChange={() => {}}
      />
    );
    const input = screen.getByLabelText(/Modèle \/ Template ID pour prod/i);
    expect(input).toHaveValue('CODE_B');
  });

  // Story 21.4 tests
  describe('Story 21.4: dynamic environments', () => {
    it('renders 4 environments when hook returns 4', () => {
      mockUseEnvironments.mockReturnValue({
        environments: ['dev', 'staging', 'prod', 'lab'],
        environmentOptions: [
          { value: 'dev', label: 'Développement' },
          { value: 'staging', label: 'Staging' },
          { value: 'prod', label: 'Production' },
          { value: 'lab', label: 'Lab' },
        ],
        loading: false,
        error: null,
      });

      render(<ChangeTypeConfig value={{}} onChange={() => {}} />);

      // Each env appears twice (once per block)
      expect(screen.getAllByText('Développement')).toHaveLength(2);
      expect(screen.getAllByText('Staging')).toHaveLength(2);
      expect(screen.getAllByText('Production')).toHaveLength(2);
      expect(screen.getAllByText('Lab')).toHaveLength(2);
      // Two blocks: Gates header + 4 data rows + ServiceNow header + 4 data rows = 10
      const rows = screen.getAllByRole('row');
      expect(rows.length).toBe(10);
    });

    it('renders 1 environment when hook returns 1', () => {
      mockUseEnvironments.mockReturnValue({
        environments: ['dev'],
        environmentOptions: [
          { value: 'dev', label: 'Développement' },
        ],
        loading: false,
        error: null,
      });

      render(<ChangeTypeConfig value={{}} onChange={() => {}} />);

      expect(screen.getAllByText('Développement')).toHaveLength(2);
      const rows = screen.getAllByRole('row');
      // 2 header rows + 2 × 1 data row = 4
      expect(rows.length).toBe(4);
    });

    it('shows skeleton when loading', () => {
      mockUseEnvironments.mockReturnValue({
        ...defaultEnvMock,
        loading: true,
      });

      render(<ChangeTypeConfig value={{}} onChange={() => {}} />);

      expect(screen.queryByRole('table')).not.toBeInTheDocument();
    });

    it('shows error alert when error but still renders grid with fallback', () => {
      mockUseEnvironments.mockReturnValue({
        ...defaultEnvMock,
        error: new Error('Network error'),
      });

      render(<ChangeTypeConfig value={{}} onChange={() => {}} />);

      expect(screen.getByText(/Erreur de chargement des environnements/i)).toBeInTheDocument();
      expect(screen.getByRole('table', { name: /Gates par environnement/i })).toBeInTheDocument();
      expect(screen.getAllByText('Développement')).toHaveLength(2);
    });

    it('renders new env with default values (not required)', () => {
      mockUseEnvironments.mockReturnValue({
        environments: ['dev', 'staging', 'prod', 'lab'],
        environmentOptions: [
          { value: 'dev', label: 'Développement' },
          { value: 'staging', label: 'Staging' },
          { value: 'prod', label: 'Production' },
          { value: 'lab', label: 'Lab' },
        ],
        loading: false,
        error: null,
      });

      render(
        <ChangeTypeConfig
          value={{ dev: { required: true, change_model_code: 'A1' }, prod: { required: true, change_model_code: 'B2' } }}
          onChange={() => {}}
        />
      );

      expect(screen.getAllByText('Lab')).toHaveLength(2);
      const labSwitch = screen.getByLabelText(/Changement requis pour lab/i);
      expect(labSwitch).toBeInTheDocument();
      expect(labSwitch).not.toBeChecked();
    });
  });

  // Story 31.6: ServiceNow integration selector tests
  describe('Story 31.6: ServiceNow integration selector', () => {
    it('shows integration selector when any env has required=true and integrations available', () => {
      mockUseServiceNowIntegrations.mockReturnValue({
        integrations: [{ id: 1, name: 'SN Prod', type: 'servicenow', status: 'active' }],
        integrationOptions: [{ value: 1, label: 'SN Prod (servicenow)' }],
        loading: false,
        error: null,
      });

      render(
        <ChangeTypeConfig
          value={{ prod: { required: true, change_model_code: 'A1' } }}
          onChange={() => {}}
          gateConfig={null}
          onGateConfigChange={() => {}}
        />
      );

      expect(screen.getByText('Intégration ServiceNow :')).toBeInTheDocument();
      expect(screen.getByLabelText('Intégration ServiceNow')).toBeInTheDocument();
    });

    it('does not show integration selector when no env has required=true', () => {
      mockUseServiceNowIntegrations.mockReturnValue({
        integrations: [{ id: 1, name: 'SN Prod', type: 'servicenow', status: 'active' }],
        integrationOptions: [{ value: 1, label: 'SN Prod (servicenow)' }],
        loading: false,
        error: null,
      });

      render(
        <ChangeTypeConfig value={{}} onChange={() => {}} gateConfig={null} onGateConfigChange={() => {}} />
      );

      expect(screen.queryByText('Intégration ServiceNow :')).not.toBeInTheDocument();
    });

    it('shows warning when integrations available but none selected', () => {
      mockUseServiceNowIntegrations.mockReturnValue({
        integrations: [{ id: 1, name: 'SN Prod', type: 'servicenow', status: 'active' }],
        integrationOptions: [{ value: 1, label: 'SN Prod (servicenow)' }],
        loading: false,
        error: null,
      });

      render(
        <ChangeTypeConfig
          value={{ prod: { required: true, change_model_code: 'A1' } }}
          onChange={() => {}}
          gateConfig={null}
          onGateConfigChange={() => {}}
        />
      );

      expect(screen.getByText('Intégration non sélectionnée')).toBeInTheDocument();
    });

    it('shows "no integrations" message when none configured', () => {
      render(
        <ChangeTypeConfig
          value={{ prod: { required: true, change_model_code: 'A1' } }}
          onChange={() => {}}
          gateConfig={null}
          onGateConfigChange={() => {}}
        />
      );

      expect(screen.getByText(/Aucune intégration ServiceNow configurée/)).toBeInTheDocument();
    });

    // Task 10.4: onGateConfigChange called with correct integration_id on selection
    it('calls onGateConfigChange with correct integration_id when selecting an integration', async () => {
      const user = userEvent.setup();
      const onGateConfigChange = vi.fn();

      mockUseServiceNowIntegrations.mockReturnValue({
        integrations: [
          { id: 1, name: 'SN Prod', type: 'servicenow', status: 'active' },
          { id: 2, name: 'SN Dev', type: 'servicenow', status: 'active' },
        ],
        integrationOptions: [
          { value: 1, label: 'SN Prod (servicenow)' },
          { value: 2, label: 'SN Dev (servicenow)' },
        ],
        loading: false,
        error: null,
      });

      render(
        <ChangeTypeConfig
          value={{ prod: { required: true, change_model_code: 'A1' } }}
          onChange={() => {}}
          gateConfig={null}
          onGateConfigChange={onGateConfigChange}
        />
      );

      // Open the Select and choose the first option
      const select = screen.getByLabelText('Intégration ServiceNow');
      await user.click(select);
      const option = await screen.findByText('SN Prod (servicenow)');
      await user.click(option);

      expect(onGateConfigChange).toHaveBeenCalledWith(
        expect.objectContaining({
          servicenow_change: expect.objectContaining({ integration_id: 1 }),
        })
      );
    });
  });
});

// ─── Coverage extras ──────────────────────────────────────────────────────────
describe('ChangeTypeConfig — coverage extras', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseEnvironments.mockReturnValue(defaultEnvMock);
    mockUseServiceNowIntegrations.mockReturnValue(defaultSnMock);
  });

  it('shows error alert for model/template input longer than max length', async () => {
    const onChange = vi.fn();
    const { container } = render(
      <ChangeTypeConfig value={{ dev: { required: true, change_model_code: '' } }} onChange={onChange} />
    );
    const input = container.querySelector('input[aria-label="Modèle / Template ID pour dev"]') as HTMLInputElement;
    expect(input).not.toBeNull();
    // Simulate input with value > 50 chars
    const longValue = 'A'.repeat(51);
    const { fireEvent } = await import('@testing-library/react');
    fireEvent.change(input, { target: { value: longValue } });
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    // onChange should NOT have been called since length > max
    expect(onChange).not.toHaveBeenCalled();
  });

  it('shows error for model/template input with invalid characters', async () => {
    const onChange = vi.fn();
    const { container } = render(
      <ChangeTypeConfig value={{ dev: { required: true, change_model_code: '' } }} onChange={onChange} />
    );
    const input = container.querySelector('input[aria-label="Modèle / Template ID pour dev"]') as HTMLInputElement;
    const { fireEvent } = await import('@testing-library/react');
    fireEvent.change(input, { target: { value: 'has space!' } });
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(onChange).not.toHaveBeenCalled();
  });

  it('clears model/template errors when required is toggled off', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ChangeTypeConfig value={{ dev: { required: true, change_model_code: '' } }} onChange={onChange} />
    );
    const reqSwitch = screen.getByLabelText(/Changement requis pour dev/i);
    await user.click(reqSwitch);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ dev: expect.objectContaining({ required: false }) })
    );
  });

  it('sets change_model_code and template_id to undefined when model/template value cleared', async () => {
    const { fireEvent } = await import('@testing-library/react');
    const onChange = vi.fn();
    const { container } = render(
      <ChangeTypeConfig value={{ dev: { required: true, change_model_code: 'ABC' } }} onChange={onChange} />
    );
    const input = container.querySelector('input[aria-label="Modèle / Template ID pour dev"]') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '' } });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ dev: expect.objectContaining({ change_model_code: undefined, template_id: undefined }) })
    );
  });

  it('sets change_type to undefined when change type field is cleared', async () => {
    const { fireEvent } = await import('@testing-library/react');
    const onChange = vi.fn();
    const { container } = render(
      <ChangeTypeConfig value={{ dev: { required: false, change_type: 'normal' } }} onChange={onChange} />
    );
    const ctInput = container.querySelector('input[aria-label="Change type pour dev"]') as HTMLInputElement;
    fireEvent.change(ctInput, { target: { value: '' } });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ dev: expect.objectContaining({ change_type: undefined }) })
    );
  });

  it('getLabel returns env.toUpperCase() when no option found for that env', () => {
    mockUseEnvironments.mockReturnValue({
      environments: ['custom_env'],
      environmentOptions: [],
      loading: false,
      error: null,
    });
    render(<ChangeTypeConfig value={{}} onChange={() => {}} />);
    // Falls back to 'custom_env'.toUpperCase() = 'CUSTOM_ENV'
    expect(screen.getAllByText('CUSTOM_ENV')).toHaveLength(2);
  });
});
