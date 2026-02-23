import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { ErrorBoundary } from './ErrorBoundary';

// Mock logger
vi.mock('../services/logger', () => ({
  default: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

import logger from '../services/logger';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Component that throws on demand
function ThrowError({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error('Test error');
  }
  return <div>No error</div>;
}

describe('ErrorBoundary', () => {
  // Suppress React's console.error noise from error boundaries
  const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

  afterEach(() => {
    consoleErrorSpy.mockClear();
    vi.clearAllMocks();
  });

  afterAll(() => {
    consoleErrorSpy.mockRestore();
  });

  it('renders children when no error occurs (AC #1)', () => {
    render(
      <MemoryRouter>
        <ErrorBoundary>
          <ThrowError shouldThrow={false} />
        </ErrorBoundary>
      </MemoryRouter>,
    );
    expect(screen.getByText('No error')).toBeInTheDocument();
  });

  it('catches error and renders fallback UI (AC #1, #2)', () => {
    render(
      <MemoryRouter>
        <ErrorBoundary>
          <ThrowError shouldThrow={true} />
        </ErrorBoundary>
      </MemoryRouter>,
    );
    expect(screen.getByText('Une erreur est survenue')).toBeInTheDocument();
    expect(screen.getByText(/une erreur inattendue/i)).toBeInTheDocument();
  });

  it('logs error with logger.error() including stack and componentStack (AC #3)', () => {
    render(
      <MemoryRouter>
        <ErrorBoundary>
          <ThrowError shouldThrow={true} />
        </ErrorBoundary>
      </MemoryRouter>,
    );
    expect(logger.error).toHaveBeenCalledWith(
      'React Error Boundary caught error',
      expect.objectContaining({
        message: 'Test error',
        stack: expect.any(String),
        componentStack: expect.any(String),
      }),
    );
  });

  it('shows reload and home buttons (AC #4)', () => {
    render(
      <MemoryRouter>
        <ErrorBoundary>
          <ThrowError shouldThrow={true} />
        </ErrorBoundary>
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /Recharger la page/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retour à l'accueil/i })).toBeInTheDocument();
  });

  it('reloads page when "Recharger la page" button is clicked (AC #4)', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <ErrorBoundary>
          <ThrowError shouldThrow={true} />
        </ErrorBoundary>
      </MemoryRouter>,
    );

    await user.click(screen.getByRole('button', { name: /Recharger la page/i }));
    // Note: navigate(0) triggers a soft refresh via React Router
    expect(mockNavigate).toHaveBeenCalledWith(0);
  });

  it('navigates to home when "Retour à l\'accueil" button is clicked (AC #4)', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <ErrorBoundary>
          <ThrowError shouldThrow={true} />
        </ErrorBoundary>
      </MemoryRouter>,
    );

    await user.click(screen.getByRole('button', { name: /Retour à l'accueil/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/');
  });

  it('supports custom fallback render prop (AC #1)', () => {
    const customFallback = (error: Error, resetError: () => void) => (
      <div>
        <span>Custom: {error.message}</span>
        <button onClick={resetError}>Reset</button>
      </div>
    );

    render(
      <MemoryRouter>
        <ErrorBoundary fallback={customFallback}>
          <ThrowError shouldThrow={true} />
        </ErrorBoundary>
      </MemoryRouter>,
    );

    expect(screen.getByText('Custom: Test error')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reset/i })).toBeInTheDocument();
  });

  it('shows technical error details in development mode', () => {
    const originalEnv = import.meta.env.MODE;
    (import.meta.env as Record<string, unknown>).MODE = 'development';

    render(
      <MemoryRouter>
        <ErrorBoundary>
          <ThrowError shouldThrow={true} />
        </ErrorBoundary>
      </MemoryRouter>,
    );

    expect(screen.getByText(/Détails techniques/i)).toBeInTheDocument();
    expect(screen.getByText(/Test error/i)).toBeInTheDocument();

    (import.meta.env as Record<string, unknown>).MODE = originalEnv;
  });

  it('includes correlation_id in error logs', () => {
    render(
      <MemoryRouter>
        <ErrorBoundary>
          <ThrowError shouldThrow={true} />
        </ErrorBoundary>
      </MemoryRouter>,
    );

    expect(logger.error).toHaveBeenCalledWith(
      'React Error Boundary caught error',
      expect.objectContaining({
        message: 'Test error',
        correlation_id: expect.any(String),
      }),
    );
  });
});
