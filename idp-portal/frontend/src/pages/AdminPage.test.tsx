/**
 * AdminPage tests (Story 2.x, 8.2; Story 13.8 AC4 — scheduled-executions tab decommissioned).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfigProvider } from 'antd';
import { createMemoryRouter, RouterProvider } from 'react-router';
import AdminPage from './AdminPage';
import { lightTheme } from '../theme/desjardins';
import { ThemeProvider } from '../contexts/ThemeContext';
import * as profilesService from '../services/profiles_service';
import * as integrationsService from '../services/integrations_service';

vi.mock('../services/admin_service', () => ({
  getAdminActions: vi.fn().mockResolvedValue({
    data: [],
    pagination: { page: 1, page_size: 10, total: 0, total_pages: 0 },
  }),
  getTags: vi.fn().mockResolvedValue([]),
  checkActionNameAvailable: vi.fn().mockResolvedValue(true),
  getEligibleActionsForWorkflow: vi.fn().mockResolvedValue([]),
}));
vi.mock('../services/profiles_service');
vi.mock('../services/integrations_service');
vi.mock('../services/reference_service', () => ({
  fetchEngines: vi.fn().mockResolvedValue([
    { value: 'Oracle', label: 'Oracle' },
    { value: 'SQL Server', label: 'SQL Server' },
  ]),
  fetchPlatforms: vi.fn().mockResolvedValue([
    { value: 'AAP', label: 'AAP' },
    { value: 'GitHub Actions', label: 'GitHub Actions' },
  ]),
  fetchEnvironments: vi.fn().mockResolvedValue(['DEV', 'STAGING', 'PROD']),
}));

function renderAdminPage() {
  const user = userEvent.setup();
  const router = createMemoryRouter(
    [{ path: '/admin', element: <AdminPage /> }],
    { initialEntries: ['/admin'] }
  );
  const result = render(
    <ThemeProvider>
      <ConfigProvider theme={lightTheme}>
        <RouterProvider router={router} />
      </ConfigProvider>
    </ThemeProvider>
  );
  return { ...result, user };
}

describe('AdminPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(profilesService.getProfiles).mockResolvedValue([]);
    vi.mocked(integrationsService.getIntegrations).mockResolvedValue([]);
  });

  it('does not show Exécutions planifiées tab (Story 13.8 AC4)', async () => {
    renderAdminPage();
    await waitFor(
      () => {
        expect(screen.getByText('Administration du Catalogue')).toBeInTheDocument();
      },
      { timeout: 5000 }
    );
    expect(screen.queryByText('Exécutions planifiées')).not.toBeInTheDocument();
  });

  it('shows Actions, Profils, Intégrations, Métriques tabs', async () => {
    renderAdminPage();
    await waitFor(
      () => {
        expect(screen.getByText('Actions')).toBeInTheDocument();
        expect(screen.getByText('Profils')).toBeInTheDocument();
        expect(screen.getByText('Intégrations')).toBeInTheDocument();
        expect(screen.getByText('Métriques')).toBeInTheDocument();
      },
      { timeout: 5000 }
    );
  });

  // Story 2.29: Two distinct buttons for action/workflow creation
  describe('Story 2.29: boutons Nouvelle action et Nouveau workflow', () => {
    it('affiche les boutons « Nouvelle action » et « Nouveau workflow » dans l\'onglet Actions', async () => {
      renderAdminPage();
      await waitFor(
        () => {
          expect(screen.getByRole('button', { name: /Nouvelle action/i })).toBeInTheDocument();
          expect(screen.getByRole('button', { name: /Nouveau workflow/i })).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });

  describe('Story 46.6 — Administration densité et sous-navigation', () => {
    it('affiche le nouveau sous-titre complet', async () => {
      renderAdminPage();
      await waitFor(
        () => {
          expect(
            screen.getByText('Gérez les actions, profils, intégrations et règles métier du portail')
          ).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });

    it('rend 8 onglets avec leurs libellés', async () => {
      renderAdminPage();
      const expectedLabels = [
        'Actions', 'Profils', 'Intégrations', 'Règles métier',
        'Catégories', 'Moteurs', 'Métriques', 'Feature Flags',
      ];
      await waitFor(
        () => {
          expectedLabels.forEach((label) => {
            expect(screen.getByText(label)).toBeInTheDocument();
          });
        },
        { timeout: 5000 }
      );
    });

    it('rend des icônes SVG sur chaque onglet (AC1)', async () => {
      const { container } = renderAdminPage();
      await waitFor(
        () => {
          // Ant Design icons render as <span role="img"> with aria-label
          const tabBar = container.querySelector('.ant-tabs-nav');
          expect(tabBar).toBeInTheDocument();
          const iconSpans = tabBar!.querySelectorAll('span[role="img"]');
          expect(iconSpans.length).toBeGreaterThanOrEqual(8);
        },
        { timeout: 5000 }
      );
    });
  });
});
