/**
 * Tests for IntegrationForm (Story 2.28, AC3, AC4, AC5).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { IntegrationForm } from './IntegrationForm';
import type { IntegrationResponse } from '../../types/api';

const mockOnSubmit = vi.fn().mockResolvedValue({
  id: 1,
  type: 'aap' as const,
  name: 'AAP Prod',
  base_url: 'https://aap.example.com',
  credential_ref: null,
  icon: null,
  created_at: '2026-01-28T10:00:00Z',
  updated_at: '2026-01-28T10:00:00Z',
} as IntegrationResponse);
const mockOnCancel = vi.fn();
const mockOnSuccess = vi.fn();

const defaultProps = {
  open: true,
  onCancel: mockOnCancel,
  onSubmit: mockOnSubmit,
  loading: false,
  error: null,
  editIntegration: null,
  onSuccess: mockOnSuccess,
};

describe('IntegrationForm', () => {
  it('renders Nouvelle intégration when not editing', () => {
    render(<IntegrationForm {...defaultProps} />);
    expect(screen.getByText('Nouvelle intégration')).toBeInTheDocument();
  });

  it('renders Modifier l\'intégration when editing', () => {
    render(
      <IntegrationForm
        {...defaultProps}
        editIntegration={{
          id: 1,
          type: 'aap',
          name: 'AAP Prod',
          base_url: 'https://aap.example.com',
          credential_ref: null,
          icon: null,
          created_at: '2026-01-28T10:00:00Z',
          updated_at: '2026-01-28T10:00:00Z',
        }}
      />
    );
    expect(screen.getByText('Modifier l\'intégration')).toBeInTheDocument();
  });

  it('has Type, Nom, URL de base, Référence credentials, Icône fields and Aperçu', () => {
    render(<IntegrationForm {...defaultProps} />);
    expect(screen.getByLabelText(/Type de plateforme/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Nom/)).toBeInTheDocument();
    expect(screen.getByLabelText(/URL de base/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Référence credentials/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Icône/)).toBeInTheDocument();
    expect(screen.getByText('Aperçu')).toBeInTheDocument();
  });

  it('shows error alert when error prop is set', () => {
    render(<IntegrationForm {...defaultProps} error="Nom déjà utilisé." />);
    expect(screen.getByText('Nom déjà utilisé.')).toBeInTheDocument();
  });

  it('validates name and base_url required, and URL format', async () => {
    const user = userEvent.setup();
    render(<IntegrationForm {...defaultProps} />);
    await user.click(screen.getByRole('button', { name: /Créer/i }));
    await waitFor(() => {
      expect(screen.getByText(/Le nom est requis/)).toBeInTheDocument();
    });
    await user.type(screen.getByLabelText(/^Nom/), 'AAP Prod');
    await user.click(screen.getByRole('button', { name: /Créer/i }));
    await waitFor(() => {
      expect(screen.getByText(/L'URL de base est requise/)).toBeInTheDocument();
    });
    await user.type(screen.getByLabelText(/URL de base/), 'not-a-url');
    await user.click(screen.getByRole('button', { name: /Créer/i }));
    await waitFor(() => {
      expect(screen.getByText(/L'URL doit être valide/)).toBeInTheDocument();
    });
  });

  it('submits with type, name, base_url and calls onSuccess', async () => {
    const user = userEvent.setup();
    render(<IntegrationForm {...defaultProps} />);
    await user.type(screen.getByLabelText(/^Nom/), 'AAP Prod');
    await user.type(screen.getByLabelText(/URL de base/), 'https://aap.example.com');
    await user.click(screen.getByRole('button', { name: /Créer/i }));
    await waitFor(() => expect(mockOnSubmit).toHaveBeenCalled());
    expect(mockOnSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'aap',
        name: 'AAP Prod',
        base_url: 'https://aap.example.com',
        credential_ref: null,
        icon: null,
      })
    );
    expect(mockOnSuccess).toHaveBeenCalled();
  });

  it('calls onCancel when Annuler clicked', async () => {
    const user = userEvent.setup();
    render(<IntegrationForm {...defaultProps} />);
    await user.click(screen.getByRole('button', { name: /Annuler/i }));
    expect(mockOnCancel).toHaveBeenCalled();
  });

  it('populates form fields with editIntegration values in edit mode', async () => {
    const editIntegration = {
      id: 1,
      type: 'terraform' as const,
      name: 'Terraform Cloud',
      base_url: 'https://app.terraform.io',
      credential_ref: 'secret/terraform/prod',
      icon: 'https://example.com/terraform.png',
      created_at: '2026-01-28T10:00:00Z',
      updated_at: '2026-01-28T10:00:00Z',
    };
    render(<IntegrationForm {...defaultProps} editIntegration={editIntegration} />);

    // Verify form fields are populated with editIntegration values
    await waitFor(() => {
      expect(screen.getByLabelText(/^Nom/)).toHaveValue('Terraform Cloud');
    });
    expect(screen.getByLabelText(/URL de base/)).toHaveValue('https://app.terraform.io');
    expect(screen.getByLabelText(/Référence credentials/)).toHaveValue('secret/terraform/prod');
    expect(screen.getByLabelText(/Icône/)).toHaveValue('https://example.com/terraform.png');
  });

  it('shows Avatar preview when icon is a valid URL', async () => {
    const user = userEvent.setup();
    render(<IntegrationForm {...defaultProps} />);

    // Enter an icon URL
    await user.type(screen.getByLabelText(/Icône/), 'https://example.com/my-icon.png');

    // Check that an img element with the icon URL appears in the preview
    await waitFor(() => {
      const avatar = document.querySelector('img[src="https://example.com/my-icon.png"]');
      expect(avatar).toBeInTheDocument();
    });
  });

  it('shows preset icon when icon field is empty', () => {
    render(<IntegrationForm {...defaultProps} />);
    // Default type is 'aap', so the preset icon should be rendered (ApiOutlined)
    // The preview section should contain an icon (not an Avatar with URL)
    const previewLabel = screen.getByText('Aperçu');
    expect(previewLabel).toBeInTheDocument();
    // Avatar with URL would have img tag, preset icon doesn't
    const img = document.querySelector('.ant-avatar img');
    expect(img).not.toBeInTheDocument();
  });
});
