import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { App } from './App';

function unexpectedFetchHandler(url: string | URL | Request, init?: RequestInit): never {
  const u = typeof url === 'string' ? url : url instanceof Request ? url.url : String(url);
  const method = (init?.method ?? (url instanceof Request ? url.method : 'GET')) || 'GET';
  throw new Error(`Unexpected fetch: ${method} ${u}`);
}

/** Minimal Response-like object for fetch mocks. */
function mockJsonResponse(body: unknown) {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => body,
  };
}

/**
 * Fail-fast fetch mock: handles known authenticated endpoints, throws for any other.
 * Use after mockResolvedValueOnce for auth (refresh + me).
 * @param userExtraProps - Optional extra fields to merge into the /users/me response (e.g. { is_auditor: true })
 */
function createAuthenticatedFetchMock(profile: string, navigationTabs: string[], userExtraProps: Record<string, unknown> = {}) {
  return vi.fn()
    .mockResolvedValueOnce(mockJsonResponse({ data: { access_token: 'token', token_type: 'bearer' } }))
    .mockResolvedValueOnce(mockJsonResponse({
      data: {
        id: 1,
        username: 'test.user',
        display_name: 'Test User',
        profile,
        navigation_tabs: navigationTabs,
        ...userExtraProps,
      },
    }))
    .mockImplementation((url: string | URL | Request, init?: RequestInit) => {
      const u = typeof url === 'string' ? url : url instanceof Request ? url.url : String(url);
      // Feature flags (FeatureFlagProvider)
      if (u.includes('/feature-flags/status')) {
        return Promise.resolve(mockJsonResponse({ data: {} }));
      }
      // Pending approvals count (TopNav badge)
      if (u.includes('/executions/pending-approvals') && u.includes('count_only=true')) {
        return Promise.resolve(mockJsonResponse({ count: 0 }));
      }
      // Catalog (CatalogPage)
      if (u.includes('/catalog/actions')) {
        return Promise.resolve(mockJsonResponse({ data: [] }));
      }
      if (u.includes('/catalog/tags')) {
        return Promise.resolve(mockJsonResponse({ data: [] }));
      }
      if (u.includes('/users/me/favorites')) {
        return Promise.resolve(mockJsonResponse({ data: [] }));
      }
      // Dashboard (ReportingDashboard on /analytics)
      if (u.includes('/dashboard/stats-by-technology') || u.includes('/dashboard/stats-by-environment') || u.includes('/dashboard/timeseries')) {
        return Promise.resolve(mockJsonResponse({ data: [] }));
      }
      if (u.includes('/dashboard/filter-options')) {
        return Promise.resolve(mockJsonResponse({ engines: [], environments: [], tags: [], statuses: [] }));
      }
      // Executions (ExecutionsPage, useExecutionsData)
      const emptyExecPagination = { data: [], pagination: { total: 0, total_pages: 0 } };
      if (u.includes('/executions/pending-approvals') && !u.includes('count_only=true')) {
        return Promise.resolve(mockJsonResponse(emptyExecPagination));
      }
      if (u.includes('/executions/timeseries')) {
        return Promise.resolve(mockJsonResponse({ data: [] }));
      }
      if (u.includes('/executions/stats')) {
        return Promise.resolve(mockJsonResponse({
          data: {
            executions_jour: 0,
            taux_succes_pct: 100,
            executions_en_cours: 0,
            executions_en_erreur: 0,
          },
        }));
      }
      if (u.includes('/executions') && (u.includes('?') || u.endsWith('/executions'))) {
        return Promise.resolve(mockJsonResponse(emptyExecPagination));
      }
      // Integrations (ExecutionsPage integration icons)
      if (u.includes('/admin/integrations')) {
        return Promise.resolve(mockJsonResponse({ data: [] }));
      }
      // Engine icons (AppLayout prefetchEngineIcons)
      if (u.includes('/reference/engines')) {
        return Promise.resolve(mockJsonResponse({ data: [] }));
      }
      // Scheduled executions (CalendarPage)
      if (u.includes('/scheduled-executions')) {
        return Promise.resolve(mockJsonResponse({ data: [], available_actions: [] }));
      }
      // Audit executions (AuditPage)
      if (u.includes('/audit/executions')) {
        return Promise.resolve(mockJsonResponse({ data: [], pagination: { total: 0, total_pages: 0 } }));
      }
      unexpectedFetchHandler(url, init);
    });
}

function mockAuthSession(profile: string, navigationTabs: string[], userExtraProps: Record<string, unknown> = {}) {
  global.fetch = createAuthenticatedFetchMock(profile, navigationTabs, userExtraProps);
}

describe('App routing', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    // Mock matchMedia for theme context
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('dark') ? false : true,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    // Default: no session
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });
  });

  it('redirects to /login when not authenticated', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/Se connecter|connexion|login|SSO/i)).toBeInTheDocument();
    });
  });

  it('renders Catalogue when authenticated on /catalog', async () => {
    mockAuthSession('dbops', ['catalog', 'executions', 'dashboard', 'admin']);

    // Navigate to /catalog
    window.history.pushState({}, '', '/catalog');
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Catalogue')).toBeInTheDocument();
    });
  });

  it('renders NotFoundPage on unknown route', async () => {
    window.history.pushState({}, '', '/unknown-route-xyz');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText('404')).toBeInTheDocument();
    });
  });

  it('AdminGuard redirects DBA user from /admin to /catalog', async () => {
    // DBA user: no 'admin' tab in navigation_tabs
    mockAuthSession('dba_applicatif', ['catalog', 'executions', 'dashboard']);

    window.history.pushState({}, '', '/admin');
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Catalogue')).toBeInTheDocument();
    });
    // Should have been redirected away from /admin — no Admin tab visible
    expect(screen.queryByText('Admin')).not.toBeInTheDocument();
  });

  // Story 56.3: AnalyticsGuard uses hasTab('dashboard') instead of profile === 'dbops'
  it('AnalyticsGuard allows access to /analytics when user has dashboard in navigation_tabs (AC1)', async () => {
    // User with 'dashboard' in navigation_tabs can access /analytics
    mockAuthSession('dbops', ['catalog', 'executions', 'dashboard', 'admin']);

    window.history.pushState({}, '', '/analytics');
    render(<App />);

    await waitFor(() => {
      // Guard must NOT redirect: URL stays at /analytics (not /executions or /catalog)
      expect(window.location.pathname).toBe('/analytics');
      // Confirm no redirection to catalog or executions occurred
      expect(screen.queryByText('Catalogue')).not.toBeInTheDocument();
    });
  });

  // Story 56.3 AC3: access is based on navigation_tabs, NOT on profile name
  it('AnalyticsGuard allows access to /analytics for non-DBOPS profile if dashboard is in navigation_tabs (AC3)', async () => {
    // A non-DBOPS profile that has 'dashboard' in navigation_tabs must be granted access
    // This validates that profile name is irrelevant — only hasTab('dashboard') matters
    mockAuthSession('dba_applicatif', ['catalog', 'executions', 'dashboard']);

    window.history.pushState({}, '', '/analytics');
    render(<App />);

    await waitFor(() => {
      // Guard must NOT redirect: URL stays at /analytics
      expect(window.location.pathname).toBe('/analytics');
      expect(screen.queryByText('Catalogue')).not.toBeInTheDocument();
    });
  });

  it('AnalyticsGuard redirects to /executions when user lacks dashboard in navigation_tabs (AC2)', async () => {
    // User without 'dashboard' in navigation_tabs is redirected from /analytics
    mockAuthSession('dba_applicatif', ['catalog', 'executions', 'calendar']);

    window.history.pushState({}, '', '/analytics');
    render(<App />);

    await waitFor(() => {
      // Should be redirected to /executions page
      expect(screen.getByText(/exécutions|executions/i)).toBeInTheDocument();
    });
  });

  // Story 13.6 AC1: CalendarGuard — access based on 'calendar' navigation tab
  it('CalendarGuard allows access to /calendar when user has calendar in navigation_tabs', async () => {
    // User with 'calendar' in navigation_tabs can access /calendar (no redirect)
    mockAuthSession('dbops', ['catalog', 'executions', 'calendar']);

    window.history.pushState({}, '', '/calendar');
    render(<App />);

    await waitFor(() => {
      // Guard must NOT redirect: URL stays at /calendar
      expect(window.location.pathname).toBe('/calendar');
      // Both assertions must pass together inside waitFor: while CalendarPage lazy-loads,
      // Suspense suspends the entire Routes tree (AppLayout included), so "Catalogue" nav
      // is not in the DOM — this window is when both conditions are simultaneously true.
      expect(screen.queryByText('Catalogue')).not.toBeInTheDocument();
    });
  });

  it('CalendarGuard redirects to /catalog when user lacks calendar in navigation_tabs', async () => {
    // User without 'calendar' in navigation_tabs is redirected from /calendar
    mockAuthSession('dba_applicatif', ['catalog', 'executions']);

    window.history.pushState({}, '', '/calendar');
    render(<App />);

    await waitFor(() => {
      // Should be redirected to /catalog
      expect(screen.getByText('Catalogue')).toBeInTheDocument();
    });
  });

  // Story 6.3 AC8: AuditGuard — access for 'audit' tab OR is_auditor
  it('AuditGuard allows access to /audit when user has audit in navigation_tabs', async () => {
    // User with 'audit' in navigation_tabs can access /audit (no redirect)
    mockAuthSession('dbops', ['catalog', 'audit']);

    window.history.pushState({}, '', '/audit');
    render(<App />);

    await waitFor(() => {
      // Guard must NOT redirect: URL stays at /audit
      // Both assertions must pass together inside waitFor: while AuditPage lazy-loads,
      // Suspense suspends the entire Routes tree (AppLayout included), so "Catalogue" nav
      // is not in the DOM — this window is when both conditions are simultaneously true.
      expect(window.location.pathname).toBe('/audit');
      expect(screen.queryByText('Catalogue')).not.toBeInTheDocument();
    });
  });

  it('AuditGuard allows access to /audit when user has is_auditor: true without audit tab (AC8)', async () => {
    // Auditor user: is_auditor=true but 'audit' NOT in navigation_tabs — alternative access path
    mockAuthSession('auditor', ['catalog'], { is_auditor: true });

    window.history.pushState({}, '', '/audit');
    render(<App />);

    await waitFor(() => {
      // Guard must NOT redirect: is_auditor path grants access
      // Both assertions must pass together inside waitFor: while AuditPage lazy-loads,
      // Suspense suspends the entire Routes tree (AppLayout included), so "Catalogue" nav
      // is not in the DOM — this window is when both conditions are simultaneously true.
      expect(window.location.pathname).toBe('/audit');
      expect(screen.queryByText('Catalogue')).not.toBeInTheDocument();
    });
  });

  it('AuditGuard redirects to /catalog when user lacks audit tab AND is_auditor is false', async () => {
    // Regular user: no 'audit' tab, is_auditor=false → redirected from /audit
    mockAuthSession('dba_applicatif', ['catalog', 'executions'], { is_auditor: false });

    window.history.pushState({}, '', '/audit');
    render(<App />);

    await waitFor(() => {
      // Should be redirected to /catalog
      expect(screen.getByText('Catalogue')).toBeInTheDocument();
    });
  });
});
