import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock AuthContext
const mockLogin = vi.fn();
const mockLoginWithCredentials = vi.fn();
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    login: mockLogin,
    loginWithCredentials: mockLoginWithCredentials,
    user: null,
    accessToken: null,
    isAuthenticated: false,
    isLoading: false,
    logout: vi.fn(),
    refreshToken: vi.fn(),
    hasTab: vi.fn(),
    isBusinessProfile: false,
  }),
}));

import LoginPage from './LoginPage';

function renderLoginPage() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: no SAML
    (import.meta.env as Record<string, unknown>).VITE_PORTAL_AUTH_METHODS = 'ldap';
  });

  it('renders login form with username and password fields', () => {
    renderLoginPage();

    expect(screen.getByPlaceholderText('Identifiant')).toBeTruthy();
    expect(screen.getByPlaceholderText('Mot de passe')).toBeTruthy();
    expect(screen.getByRole('button', { name: /se connecter/i })).toBeTruthy();
    expect(screen.getByText('IDP Portal')).toBeTruthy();
  });

  it('successful login redirects to /catalog', async () => {
    const user = userEvent.setup();
    mockLoginWithCredentials.mockResolvedValueOnce(undefined);

    renderLoginPage();

    await user.type(screen.getByPlaceholderText('Identifiant'), 'admin');
    await user.type(screen.getByPlaceholderText('Mot de passe'), 'password123');
    await user.click(screen.getByRole('button', { name: /se connecter/i }));

    await waitFor(() => {
      expect(mockLoginWithCredentials).toHaveBeenCalledWith('admin', 'password123');
      expect(mockNavigate).toHaveBeenCalledWith('/catalog');
    });
  });

  it('invalid credentials shows error message', async () => {
    const user = userEvent.setup();
    const error = new Error('Credentials invalides');
    (error as any).code = 'INVALID_CREDENTIALS';
    (error as any).status = 401;
    mockLoginWithCredentials.mockRejectedValueOnce(error);

    renderLoginPage();

    await user.type(screen.getByPlaceholderText('Identifiant'), 'admin');
    await user.type(screen.getByPlaceholderText('Mot de passe'), 'wrong');
    await user.click(screen.getByRole('button', { name: /se connecter/i }));

    await waitFor(() => {
      expect(screen.getByText('Identifiant ou mot de passe invalide.')).toBeTruthy();
    });
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('LDAP unavailable shows error message', async () => {
    const user = userEvent.setup();
    const error = new Error('LDAP unavailable');
    (error as any).code = 'LDAP_UNAVAILABLE';
    (error as any).status = 503;
    mockLoginWithCredentials.mockRejectedValueOnce(error);

    renderLoginPage();

    await user.type(screen.getByPlaceholderText('Identifiant'), 'admin');
    await user.type(screen.getByPlaceholderText('Mot de passe'), 'pass');
    await user.click(screen.getByRole('button', { name: /se connecter/i }));

    await waitFor(() => {
      expect(screen.getByText("Le service d'authentification est temporairement indisponible. Réessayez plus tard.")).toBeTruthy();
    });
  });

  it('insufficient privileges shows error message', async () => {
    const user = userEvent.setup();
    const error = new Error('Insufficient privileges');
    (error as any).code = 'INSUFFICIENT_PRIVILEGES';
    (error as any).status = 403;
    mockLoginWithCredentials.mockRejectedValueOnce(error);

    renderLoginPage();

    await user.type(screen.getByPlaceholderText('Identifiant'), 'admin');
    await user.type(screen.getByPlaceholderText('Mot de passe'), 'pass');
    await user.click(screen.getByRole('button', { name: /se connecter/i }));

    await waitFor(() => {
      expect(screen.getByText('Votre compte ne dispose pas des privilèges requis pour accéder au portail.')).toBeTruthy();
    });
  });

  it('no profile shows error message', async () => {
    const user = userEvent.setup();
    const error = new Error('No profile');
    (error as any).code = 'NO_PROFILE';
    (error as any).status = 403;
    mockLoginWithCredentials.mockRejectedValueOnce(error);

    renderLoginPage();

    await user.type(screen.getByPlaceholderText('Identifiant'), 'admin');
    await user.type(screen.getByPlaceholderText('Mot de passe'), 'pass');
    await user.click(screen.getByRole('button', { name: /se connecter/i }));

    await waitFor(() => {
      expect(screen.getByText('Aucun profil associé à votre compte. Contactez un administrateur.')).toBeTruthy();
    });
  });

  it('rate limit exceeded shows error message', async () => {
    const user = userEvent.setup();
    const error = new Error('Too many requests');
    (error as any).code = 'RATE_LIMIT_EXCEEDED';
    (error as any).status = 429;
    mockLoginWithCredentials.mockRejectedValueOnce(error);

    renderLoginPage();

    await user.type(screen.getByPlaceholderText('Identifiant'), 'admin');
    await user.type(screen.getByPlaceholderText('Mot de passe'), 'pass');
    await user.click(screen.getByRole('button', { name: /se connecter/i }));

    await waitFor(() => {
      expect(screen.getByText('Trop de tentatives. Veuillez patienter avant de réessayer.')).toBeTruthy();
    });
  });

  it('SSO button hidden when SAML not in auth methods', () => {
    (import.meta.env as Record<string, unknown>).VITE_PORTAL_AUTH_METHODS = 'ldap';

    renderLoginPage();

    expect(screen.queryByText('Se connecter via SSO')).toBeNull();
  });

  it('SSO button visible when SAML in auth methods', () => {
    (import.meta.env as Record<string, unknown>).VITE_PORTAL_AUTH_METHODS = 'ldap,saml';

    renderLoginPage();

    expect(screen.getByText('Se connecter via SSO')).toBeTruthy();
  });

  it('loading state during login', async () => {
    const user = userEvent.setup();
    // Never resolve — keep loading
    mockLoginWithCredentials.mockReturnValueOnce(new Promise(() => {}));

    renderLoginPage();

    await user.type(screen.getByPlaceholderText('Identifiant'), 'admin');
    await user.type(screen.getByPlaceholderText('Mot de passe'), 'pass');
    await user.click(screen.getByRole('button', { name: /se connecter/i }));

    await waitFor(() => {
      const submitButton = screen.getByRole('button', { name: /se connecter/i });
      // Ant Design adds ant-btn-loading class and disabled attribute when loading
      expect(submitButton.closest('.ant-btn-loading')).toBeTruthy();
    });
  });

  it('SSO button calls login()', async () => {
    const user = userEvent.setup();
    (import.meta.env as Record<string, unknown>).VITE_PORTAL_AUTH_METHODS = 'ldap,saml';

    renderLoginPage();

    await user.click(screen.getByText('Se connecter via SSO'));
    expect(mockLogin).toHaveBeenCalled();
  });
});
