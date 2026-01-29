/**
 * Tests for ChangeTypeConfig (Story 2.2, AC #3; Story 2.8: no CAB, only Pre-approuvé).
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChangeTypeConfig } from './ChangeTypeConfig';

describe('ChangeTypeConfig', () => {
  it('renders Pre-approuvé option only (Story 2.8: no CAB)', () => {
    render(<ChangeTypeConfig value={{}} onChange={() => {}} />);
    expect(screen.getAllByText('Pre-approuvé').length).toBeGreaterThan(0);
    expect(screen.queryByText('CAB')).not.toBeInTheDocument();
  });

  it('exposes only pre_approved in dropdown (Story 2.8)', async () => {
    const user = userEvent.setup();
    render(<ChangeTypeConfig value={{}} onChange={() => {}} />);
    await user.click(screen.getByLabelText(/Type de changement pour DEV/i));
    const options = screen.getAllByRole('option');
    expect(options).toHaveLength(1);
    expect(options[0]).toHaveAttribute('aria-label', 'Pre-approuvé');
  });

  it('never emits cab (Story 2.8, AC3)', () => {
    render(<ChangeTypeConfig value={{ PROD: 'pre_approved' }} onChange={() => {}} />);
    expect(screen.queryByText('CAB')).not.toBeInTheDocument();
  });
});
