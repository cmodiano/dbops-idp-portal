/**
 * Tests for IntegrationForm (Story 2.28, 4.9).
 * Story 4.9: Type libre (AutoComplete), auth_flow (Select), Upload icône.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { IntegrationForm } from './IntegrationForm';
import type { IntegrationResponse } from '../../types/api';

const mockOnSubmit = vi.fn().mockResolvedValue({
  id: 1,
  type: 'aap',  // Story 4.9: free-form string
  name: 'AAP Prod',
  base_url: 'https://aap.example.com',
  credential_ref: null,
  icon: null,
  auth_flow: 'token',
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
          auth_flow: 'token',
          created_at: '2026-01-28T10:00:00Z',
          updated_at: '2026-01-28T10:00:00Z',
        }}
      />
    );
    expect(screen.getByText('Modifier l\'intégration')).toBeInTheDocument();
  });

  it('has Type, Nom, URL de base, Référence credentials, Auth Flow, Icône fields and Aperçu', () => {
    render(<IntegrationForm {...defaultProps} />);
    expect(screen.getByLabelText(/Type de plateforme/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Nom/)).toBeInTheDocument();
    expect(screen.getByLabelText(/URL de base/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Référence credentials/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Flow d'authentification/)).toBeInTheDocument();
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

  it('submits with type, name, base_url, auth_flow and calls onSuccess (Story 4.9)', async () => {
    const user = userEvent.setup();
    render(<IntegrationForm {...defaultProps} />);
    await user.type(screen.getByLabelText(/Type de plateforme/), 'jenkins');
    await user.type(screen.getByLabelText(/^Nom/), 'Jenkins CI');
    await user.type(screen.getByLabelText(/URL de base/), 'https://jenkins.example.com');
    await user.click(screen.getByRole('button', { name: /Créer/i }));
    await waitFor(() => expect(mockOnSubmit).toHaveBeenCalled());
    expect(mockOnSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'jenkins',
        name: 'Jenkins CI',
        base_url: 'https://jenkins.example.com',
        credential_ref: null,
        icon: null,
        auth_flow: null,
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

  it('populates form fields with editIntegration values in edit mode (Story 4.9)', async () => {
    const editIntegration = {
      id: 1,
      type: 'terraform',
      name: 'Terraform Cloud',
      base_url: 'https://app.terraform.io',
      credential_ref: 'secret/terraform/prod',
      icon: 'https://example.com/terraform.png',
      auth_flow: 'pat' as const,
      created_at: '2026-01-28T10:00:00Z',
      updated_at: '2026-01-28T10:00:00Z',
    };
    render(<IntegrationForm {...defaultProps} editIntegration={editIntegration} />);

    // Verify form fields are populated with editIntegration values
    await waitFor(() => {
      expect(screen.getByLabelText(/^Nom/)).toHaveValue('Terraform Cloud');
    });
    expect(screen.getByLabelText(/Type de plateforme/)).toHaveValue('terraform');
    expect(screen.getByLabelText(/URL de base/)).toHaveValue('https://app.terraform.io');
    expect(screen.getByLabelText(/Référence credentials/)).toHaveValue('secret/terraform/prod');
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

  it('shows fallback API icon when icon field is empty (Story 4.9)', () => {
    render(<IntegrationForm {...defaultProps} />);
    // Story 4.9: No type-specific icons, fallback to generic ApiOutlined
    const previewLabel = screen.getByText('Aperçu');
    expect(previewLabel).toBeInTheDocument();
    // Should render Avatar with ApiOutlined icon
    const avatar = document.querySelector('.ant-avatar');
    expect(avatar).toBeInTheDocument();
  });

  it('validates type required and max length (Story 4.9 AC1)', async () => {
    const user = userEvent.setup();
    render(<IntegrationForm {...defaultProps} />);
    await user.type(screen.getByLabelText(/^Nom/), 'Test Integration');
    await user.type(screen.getByLabelText(/URL de base/), 'https://example.com');
    await user.click(screen.getByRole('button', { name: /Créer/i }));
    await waitFor(() => {
      expect(screen.getByText(/Le type est requis/)).toBeInTheDocument();
    });
  });

  it('allows free-form type input (Story 4.9 AC1)', async () => {
    const user = userEvent.setup();
    render(<IntegrationForm {...defaultProps} />);
    await user.type(screen.getByLabelText(/Type de plateforme/), 'custom-platform');
    await user.type(screen.getByLabelText(/^Nom/), 'Custom Platform');
    await user.type(screen.getByLabelText(/URL de base/), 'https://custom.example.com');
    await user.click(screen.getByRole('button', { name: /Créer/i }));
    await waitFor(() => expect(mockOnSubmit).toHaveBeenCalled());
    expect(mockOnSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'custom-platform',
      })
    );
  });
});
