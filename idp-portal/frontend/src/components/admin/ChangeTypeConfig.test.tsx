/**
 * Tests for ChangeTypeConfig (Story 2.24: per-env Switch « Changement requis » + Code modèle).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChangeTypeConfig } from './ChangeTypeConfig';

describe('ChangeTypeConfig', () => {
  it('renders table with environments DEV, STAGING, PROD', () => {
    render(<ChangeTypeConfig value={{}} onChange={() => {}} />);
    expect(screen.getByRole('table', { name: /Configuration type de changement/i })).toBeInTheDocument();
    expect(screen.getByText('DEV')).toBeInTheDocument();
    expect(screen.getByText('STAGING')).toBeInTheDocument();
    expect(screen.getByText('PROD')).toBeInTheDocument();
  });

  it('renders Switch and Code modèle column headers', () => {
    render(<ChangeTypeConfig value={{}} onChange={() => {}} />);
    expect(screen.getByText('Changement requis')).toBeInTheDocument();
    expect(screen.getByText('Code modèle')).toBeInTheDocument();
  });

  it('when required is true for PROD, shows input for code', () => {
    render(
      <ChangeTypeConfig value={{ PROD: { required: true, change_model_code: '1516B' } }} onChange={() => {}} />
    );
    const prodCodeInput = screen.getByLabelText(/Code modèle pour PROD/i);
    expect(prodCodeInput).toBeInTheDocument();
    expect(prodCodeInput).toHaveValue('1516B');
  });

  it('calls onChange when toggling Switch', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ChangeTypeConfig value={{}} onChange={onChange} />);
    const devSwitch = screen.getByLabelText(/Changement requis pour DEV/i);
    await user.click(devSwitch);
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ DEV: expect.objectContaining({ required: true }) }));
  });

  it('calls onChange when typing code', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <ChangeTypeConfig value={{ PROD: { required: true, change_model_code: '' } }} onChange={onChange} />
    );
    const input = screen.getByLabelText(/Code modèle pour PROD/i);
    await user.type(input, '1516B');
    expect(onChange).toHaveBeenCalled();
  });
});
