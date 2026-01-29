/**
 * Tests for ProfileForm (Story 2.9, AC #1, #2, #4).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProfileForm } from './ProfileForm';
import type { ProfileResponse } from '../../types/api';

const mockOnSubmit = vi.fn().mockResolvedValue({ id: 1, name: 'Assurance', ad_group: 'GRP-X' } as ProfileResponse);
const mockOnCancel = vi.fn();
const mockOnSuccess = vi.fn();

const defaultProps = {
  open: true,
  onCancel: mockOnCancel,
  onSubmit: mockOnSubmit,
  loading: false,
  error: null,
  editProfile: null,
  onSuccess: mockOnSuccess,
};

describe('ProfileForm', () => {
  it('renders Nouveau profil when not editing', () => {
    render(<ProfileForm {...defaultProps} />);
    expect(screen.getByText('Nouveau profil')).toBeInTheDocument();
  });

  it('renders Modifier le profil when editing', () => {
    render(
      <ProfileForm
        {...defaultProps}
        editProfile={{
          id: 1,
          name: 'Assurance',
          description: 'X',
          ad_group: 'GRP-X',
          is_admin: false,
          is_auditor: true,
          created_at: '2026-01-28T10:00:00Z',
          updated_at: '2026-01-28T10:00:00Z',
        }}
      />
    );
    expect(screen.getByText('Modifier le profil')).toBeInTheDocument();
  });

  it('has name, description, ad_group, is_admin, is_auditor fields', () => {
    render(<ProfileForm {...defaultProps} />);
    expect(screen.getByLabelText(/^Nom/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Description/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Groupe AD/)).toBeInTheDocument();
    expect(screen.getByText('Administrateur')).toBeInTheDocument();
    expect(screen.getByText('Auditeur')).toBeInTheDocument();
  });

  it('shows error alert when error prop is set', () => {
    render(<ProfileForm {...defaultProps} error="Un profil avec ce nom existe déjà." />);
    expect(screen.getByText('Un profil avec ce nom existe déjà.')).toBeInTheDocument();
  });

  it('submits with name and ad_group (required)', async () => {
    const user = userEvent.setup();
    render(<ProfileForm {...defaultProps} />);
    await user.type(screen.getByLabelText(/^Nom/), 'Assurance');
    await user.type(screen.getByLabelText(/Groupe AD/), 'GRP-IDP-ASSURANCE');
    await user.click(screen.getByRole('button', { name: /Créer/i }));
    await vi.waitFor(() => expect(mockOnSubmit).toHaveBeenCalled());
    expect(mockOnSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Assurance',
        ad_group: 'GRP-IDP-ASSURANCE',
        is_admin: false,
        is_auditor: false,
      })
    );
  });

  it('calls onCancel when Annuler clicked', async () => {
    const user = userEvent.setup();
    render(<ProfileForm {...defaultProps} />);
    await user.click(screen.getByRole('button', { name: /Annuler/i }));
    expect(mockOnCancel).toHaveBeenCalled();
  });
});
