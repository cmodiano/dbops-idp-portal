/**
 * Tests for EngineForm (Story 31.10, AC2/AC5).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { EngineForm } from './EngineForm';
import type { RefEngine } from '../../services/reference_service';

vi.mock('../../services/engines_service', () => ({
  updateEngine: vi.fn(),
}));

import { updateEngine } from '../../services/engines_service';

const mockUpdateEngine = vi.mocked(updateEngine);

const mockNotification = {
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
  open: vi.fn(),
};

function renderWithApp(ui: React.ReactElement) {
  vi.spyOn(App, 'useApp').mockReturnValue({
    message: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn(), loading: vi.fn() },
    notification: mockNotification,
    modal: { confirm: vi.fn() },
  } as ReturnType<typeof App.useApp>);
  return render(<App>{ui}</App>);
}

const engine: RefEngine = {
  id: 1,
  code: 'ORACLE',
  label: 'Oracle',
  display_order: 1,
  is_active: 1,
  icon_url: '/icons/oracle.svg',
};

const defaultProps = {
  open: true,
  onCancel: vi.fn(),
  onSuccess: vi.fn(),
  editEngine: engine,
};

describe('EngineForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUpdateEngine.mockResolvedValue(engine);
  });

  it('renders modal with engine fields', () => {
    renderWithApp(<EngineForm {...defaultProps} />);
    expect(screen.getByText('Modifier le moteur')).toBeInTheDocument();
    expect(screen.getByLabelText('Code du moteur')).toBeInTheDocument();
    expect(screen.getByLabelText('Libellé du moteur')).toBeInTheDocument();
    expect(screen.getByLabelText("URL de l'icône")).toBeInTheDocument();
    expect(screen.getByLabelText("Ordre d'affichage")).toBeInTheDocument();
    expect(screen.getByLabelText('Moteur actif')).toBeInTheDocument();
  });

  it('code field is disabled (read-only)', () => {
    renderWithApp(<EngineForm {...defaultProps} />);
    const codeInput = screen.getByLabelText('Code du moteur');
    expect(codeInput).toBeDisabled();
  });

  it('populates form with engine values', () => {
    renderWithApp(<EngineForm {...defaultProps} />);
    expect(screen.getByLabelText('Code du moteur')).toHaveValue('ORACLE');
    expect(screen.getByLabelText('Libellé du moteur')).toHaveValue('Oracle');
    expect(screen.getByLabelText("URL de l'icône")).toHaveValue('/icons/oracle.svg');
  });

  it('calls updateEngine on submit (AC2)', async () => {
    const user = userEvent.setup();
    renderWithApp(<EngineForm {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

    await waitFor(() => {
      expect(mockUpdateEngine).toHaveBeenCalledWith(1, {
        label: 'Oracle',
        icon_url: '/icons/oracle.svg',
        display_order: 1,
        is_active: 1,
      });
    });
  });

  it('calls onSuccess after successful update', async () => {
    const user = userEvent.setup();
    renderWithApp(<EngineForm {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

    await waitFor(() => {
      expect(defaultProps.onSuccess).toHaveBeenCalled();
    });
  });

  it('shows success notification after update', async () => {
    const user = userEvent.setup();
    renderWithApp(<EngineForm {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

    await waitFor(() => {
      expect(mockNotification.success).toHaveBeenCalledWith(
        expect.objectContaining({ description: expect.stringContaining('Oracle') })
      );
    });
  });

  it('shows error notification on update failure', async () => {
    mockUpdateEngine.mockRejectedValueOnce(new Error('Server error'));
    const user = userEvent.setup();
    renderWithApp(<EngineForm {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

    await waitFor(() => {
      expect(mockNotification.error).toHaveBeenCalledWith(
        expect.objectContaining({ description: 'Server error' })
      );
    });
  });

  it('calls onCancel when cancel button clicked', async () => {
    const user = userEvent.setup();
    renderWithApp(<EngineForm {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /Annuler/i }));
    expect(defaultProps.onCancel).toHaveBeenCalled();
  });

  it('validates label is required', async () => {
    const user = userEvent.setup();
    renderWithApp(<EngineForm {...defaultProps} />);

    const labelInput = screen.getByLabelText('Libellé du moteur');
    await user.clear(labelInput);
    await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

    await waitFor(() => {
      expect(screen.getByText('Le libellé est requis')).toBeInTheDocument();
    });
    expect(mockUpdateEngine).not.toHaveBeenCalled();
  });

  it('sends icon_url as null when empty', async () => {
    const user = userEvent.setup();
    renderWithApp(<EngineForm {...defaultProps} />);

    const iconInput = screen.getByLabelText("URL de l'icône");
    await user.clear(iconInput);
    await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

    await waitFor(() => {
      expect(mockUpdateEngine).toHaveBeenCalledWith(1, expect.objectContaining({ icon_url: null }));
    });
  });
});
