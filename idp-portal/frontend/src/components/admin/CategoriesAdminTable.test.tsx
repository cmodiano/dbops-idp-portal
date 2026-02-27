/**
 * Tests for CategoriesAdminTable (Story 48.7, AC2).
 * Verifies that invalidateCategoriesCache() is called after each mutation.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { CategoriesAdminTable } from './CategoriesAdminTable';

// Mock services
vi.mock('../../services/categories_service', () => ({
  getCategories: vi.fn(),
  deleteCategory: vi.fn(),
}));

// Mock invalidateCategoriesCache from the hook
vi.mock('../../hooks/useCategories', () => ({
  invalidateCategoriesCache: vi.fn(),
}));

// Mock CategoryForm — expose a button to trigger onSuccess directly
vi.mock('./CategoryForm', () => ({
  CategoryForm: ({
    open,
    onSuccess,
    onCancel,
  }: {
    open: boolean;
    onSuccess: () => void;
    onCancel: () => void;
    editCategory?: unknown;
  }) =>
    open ? (
      <div data-testid="category-form">
        <button data-testid="form-success-btn" onClick={() => onSuccess()}>
          Submit Form
        </button>
        <button data-testid="form-cancel-btn" onClick={onCancel}>
          Cancel Form
        </button>
      </div>
    ) : null,
}));

import { getCategories, deleteCategory } from '../../services/categories_service';
import { invalidateCategoriesCache } from '../../hooks/useCategories';

const mockGetCategories = vi.mocked(getCategories);
const mockDeleteCategory = vi.mocked(deleteCategory);
const mockInvalidateCategoriesCache = vi.mocked(invalidateCategoriesCache);

const mockNotification = {
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
  open: vi.fn(),
};
const mockModalConfirm = vi.fn();

function renderWithApp(ui: React.ReactElement) {
  vi.spyOn(App, 'useApp').mockReturnValue({
    message: {
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
      warning: vi.fn(),
      loading: vi.fn(),
      open: vi.fn(),
      destroy: vi.fn(),
    },
    notification: mockNotification,
    modal: { confirm: mockModalConfirm },
  } as unknown as ReturnType<typeof App.useApp>);
  return render(<App>{ui}</App>);
}

const mockCategories = [
  { id: 1, code: 'CAT1', label: 'Category 1', display_order: 1, is_active: 1 },
  { id: 2, code: 'CAT2', label: 'Category 2', display_order: 2, is_active: 0 },
];

describe('CategoriesAdminTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetCategories.mockResolvedValue(mockCategories);
  });

  it('affiche la liste des catégories avec toutes les colonnes', async () => {
    renderWithApp(<CategoriesAdminTable />);
    await waitFor(() => {
      expect(screen.getByText('Category 1')).toBeInTheDocument();
    });
    expect(screen.getByText('Category 2')).toBeInTheDocument();
    expect(screen.getByText('Code')).toBeInTheDocument();
    expect(screen.getByText('Libellé')).toBeInTheDocument();
    expect(screen.getByText('Ordre')).toBeInTheDocument();
    expect(screen.getByText('Actif')).toBeInTheDocument();
    // Inclut les inactives (false = active_only=false)
    expect(mockGetCategories).toHaveBeenCalledWith(false);
  });

  it('affiche le bouton Désactiver uniquement pour les catégories actives', async () => {
    renderWithApp(<CategoriesAdminTable />);
    await waitFor(() => {
      expect(screen.getByText('Category 1')).toBeInTheDocument();
    });
    const deactivateButtons = screen.getAllByRole('button', { name: /Désactiver/i });
    // Seule Category 1 (is_active=1) doit avoir le bouton
    expect(deactivateButtons).toHaveLength(1);
  });

  it('appelle invalidateCategoriesCache après suppression réussie (AC2)', async () => {
    const user = userEvent.setup();
    mockDeleteCategory.mockResolvedValue(undefined);
    mockModalConfirm.mockImplementation(({ onOk }: { onOk: () => Promise<void> }) => {
      onOk();
    });

    renderWithApp(<CategoriesAdminTable />);
    await waitFor(() => {
      expect(screen.getByText('Category 1')).toBeInTheDocument();
    });

    const deactivateButton = screen.getByRole('button', { name: /Désactiver/i });
    await user.click(deactivateButton);

    expect(mockModalConfirm).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Désactiver la catégorie' })
    );
    await waitFor(() => {
      expect(mockDeleteCategory).toHaveBeenCalledWith(1);
      expect(mockInvalidateCategoriesCache).toHaveBeenCalled();
    });
  });

  it('appelle invalidateCategoriesCache après succès du formulaire create/update (AC2)', async () => {
    const user = userEvent.setup();
    renderWithApp(<CategoriesAdminTable />);
    await waitFor(() => {
      expect(screen.getByText('Category 1')).toBeInTheDocument();
    });

    // Ouvrir le formulaire de création
    await user.click(screen.getByRole('button', { name: /Nouvelle catégorie/i }));
    await waitFor(() => {
      expect(screen.getByTestId('category-form')).toBeInTheDocument();
    });

    // Simuler le succès du formulaire
    mockGetCategories.mockClear();
    await user.click(screen.getByTestId('form-success-btn'));

    await waitFor(() => {
      expect(mockInvalidateCategoriesCache).toHaveBeenCalled();
      expect(mockGetCategories).toHaveBeenCalledWith(false); // refetch déclenché
    });
    // Le formulaire doit être fermé
    expect(screen.queryByTestId('category-form')).not.toBeInTheDocument();
  });

  it("n'appelle PAS invalidateCategoriesCache si la suppression échoue (AC2)", async () => {
    const user = userEvent.setup();
    mockDeleteCategory.mockRejectedValue(new Error('Server error'));
    mockModalConfirm.mockImplementation(({ onOk }: { onOk: () => Promise<void> }) => {
      onOk();
    });

    renderWithApp(<CategoriesAdminTable />);
    await waitFor(() => {
      expect(screen.getByText('Category 1')).toBeInTheDocument();
    });

    const deactivateButton = screen.getByRole('button', { name: /Désactiver/i });
    await user.click(deactivateButton);

    await waitFor(() => {
      expect(mockNotification.error).toHaveBeenCalled();
    });
    expect(mockInvalidateCategoriesCache).not.toHaveBeenCalled();
  });

  it('affiche une erreur si le chargement initial échoue', async () => {
    mockGetCategories.mockRejectedValueOnce(new Error('Network error'));
    renderWithApp(<CategoriesAdminTable />);
    await waitFor(() => {
      expect(mockNotification.error).toHaveBeenCalledWith(
        expect.objectContaining({ description: 'Network error' })
      );
    });
  });
});
