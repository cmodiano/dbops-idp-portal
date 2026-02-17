/**
 * Tests for ChangeTypeConfig (Story 2.24 + Story 21.4: dynamic environments).
 * Per-env Switch « Changement requis » + Code modèle, with environments from useEnvironments hook.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChangeTypeConfig } from './ChangeTypeConfig';
import { useEnvironments } from '../../hooks/useEnvironments';

vi.mock('../../hooks/useEnvironments', () => ({
  useEnvironments: vi.fn(),
}));

const mockUseEnvironments = useEnvironments as ReturnType<typeof vi.fn>;

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
  });

  it('renders table with environments from hook', () => {
    render(<ChangeTypeConfig value={{}} onChange={() => {}} />);
    expect(screen.getByRole('table', { name: /Configuration type de changement/i })).toBeInTheDocument();
    expect(screen.getByText('Développement')).toBeInTheDocument();
    expect(screen.getByText('Staging')).toBeInTheDocument();
    expect(screen.getByText('Production')).toBeInTheDocument();
  });

  it('renders Switch and Code modèle column headers', () => {
    render(<ChangeTypeConfig value={{}} onChange={() => {}} />);
    expect(screen.getByText('Changement requis')).toBeInTheDocument();
    expect(screen.getByText('Code modèle')).toBeInTheDocument();
  });

  it('when required is true for prod, shows input for code', () => {
    render(
      <ChangeTypeConfig value={{ prod: { required: true, change_model_code: '1516B' } }} onChange={() => {}} />
    );
    const prodCodeInput = screen.getByLabelText(/Code modèle pour prod/i);
    expect(prodCodeInput).toBeInTheDocument();
    expect(prodCodeInput).toHaveValue('1516B');
  });

  it('calls onChange when toggling Switch', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ChangeTypeConfig value={{}} onChange={onChange} />);
    const devSwitch = screen.getByLabelText(/Changement requis pour dev/i);
    await user.click(devSwitch);
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ dev: expect.objectContaining({ required: true }) }));
  });

  it('calls onChange when typing code', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ChangeTypeConfig value={{ prod: { required: true, change_model_code: '' } }} onChange={onChange} />
    );
    const input = screen.getByLabelText(/Code modèle pour prod/i);
    await user.type(input, '1516B');
    expect(onChange).toHaveBeenCalled();
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

      expect(screen.getByText('Développement')).toBeInTheDocument();
      expect(screen.getByText('Staging')).toBeInTheDocument();
      expect(screen.getByText('Production')).toBeInTheDocument();
      expect(screen.getByText('Lab')).toBeInTheDocument();
      // 4 rows (one per environment)
      const rows = screen.getAllByRole('row');
      // header row + 4 data rows = 5
      expect(rows.length).toBe(5);
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

      expect(screen.getByText('Développement')).toBeInTheDocument();
      const rows = screen.getAllByRole('row');
      // header + 1 data row = 2
      expect(rows.length).toBe(2);
    });

    it('shows skeleton when loading', () => {
      mockUseEnvironments.mockReturnValue({
        ...defaultEnvMock,
        loading: true,
      });

      render(<ChangeTypeConfig value={{}} onChange={() => {}} />);

      // Skeleton active = Ant Design skeleton element
      expect(screen.queryByRole('table')).not.toBeInTheDocument();
    });

    it('shows error alert when error but still renders grid with fallback', () => {
      mockUseEnvironments.mockReturnValue({
        ...defaultEnvMock,
        error: new Error('Network error'),
      });

      render(<ChangeTypeConfig value={{}} onChange={() => {}} />);

      // Shows warning alert
      expect(screen.getByText(/Erreur de chargement des environnements/i)).toBeInTheDocument();
      // But still renders grid with fallback environments
      expect(screen.getByRole('table')).toBeInTheDocument();
      expect(screen.getByText('Développement')).toBeInTheDocument();
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

      // Existing config only has dev and prod
      render(
        <ChangeTypeConfig
          value={{ dev: { required: true, change_model_code: 'A1' }, prod: { required: true, change_model_code: 'B2' } }}
          onChange={() => {}}
        />
      );

      // lab should appear but with default "not required" (dash shown)
      expect(screen.getByText('Lab')).toBeInTheDocument();
      // Switch for lab should exist and be unchecked (not required by default)
      const labSwitch = screen.getByLabelText(/Changement requis pour lab/i);
      expect(labSwitch).toBeInTheDocument();
      expect(labSwitch).not.toBeChecked();
    });
  });
});
