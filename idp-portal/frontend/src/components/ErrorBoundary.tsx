import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Result, Button } from 'antd';
import { useNavigate } from 'react-router';
import logger from '../services/logger';

/* eslint-disable standards/no-class-components */
// Error Boundaries in React require class components - there is no hooks-based alternative
// See: https://react.dev/reference/react/Component#catching-rendering-errors-with-an-error-boundary

/* eslint-disable react-refresh/only-export-components */
// This file legitimately exports both ErrorBoundary (class) and ErrorFallback (function component)

/* eslint-disable react-hooks/error-boundaries */
// The try/catch around JSX in ErrorFallback is intentional as a fallback-of-fallback pattern
// to ensure we always show something if the error UI itself fails

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error, resetError: () => void) => ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * ErrorBoundary - Capture les erreurs de rendu React et affiche un fallback UI.
 *
 * @example
 * ```tsx
 * <ErrorBoundary>
 *   <MyComponent />
 * </ErrorBoundary>
 * ```
 *
 * @example Custom fallback
 * ```tsx
 * <ErrorBoundary fallback={(error, resetError) => <div onClick={resetError}>{error.message}</div>}>
 *   <MyComponent />
 * </ErrorBoundary>
 * ```
 *
 * Story 22.10, AC #1-#6
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    try {
      logger.error('React Error Boundary caught error', {
        message: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
        correlation_id: crypto.randomUUID(),
      });
    } catch (loggerError) {
      // Fallback if logger fails
      // eslint-disable-next-line no-console
      console.error('[ErrorBoundary] Logger failed, falling back to console:', error, errorInfo, loggerError);
    }
  }

  resetError = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback && this.state.error) {
        return this.props.fallback(this.state.error, this.resetError);
      }

      return <ErrorFallback error={this.state.error} resetError={this.resetError} />;
    }

    return this.props.children;
  }
}

interface ErrorFallbackProps {
  error: Error | null;
  resetError: () => void;
}

function ErrorFallback({ error, resetError }: ErrorFallbackProps) {
  const navigate = useNavigate();

  const handleReload = (): void => {
    resetError();
    navigate(0); // Soft refresh via React Router instead of hard reload
  };

  const handleGoHome = (): void => {
    navigate('/'); // Navigate first, unmount will clean up state
  };

  try {
    return (
      <Result
        status="error"
        title="Une erreur est survenue"
        subTitle={
          <span id="error-message">
            Nous sommes désolés, une erreur inattendue s'est produite. Vous pouvez recharger la page ou retourner à
            l'accueil.
            {import.meta.env.MODE === 'development' && error && (
              <div style={{ marginTop: 16, fontSize: 12, color: '#666' }}>
                <strong>Détails techniques (dev uniquement):</strong> {error.message}
              </div>
            )}
          </span>
        }
        extra={[
          <Button type="primary" key="reload" onClick={handleReload} aria-describedby="error-message">
            Recharger la page
          </Button>,
          <Button key="home" onClick={handleGoHome} aria-describedby="error-message">
            Retour à l'accueil
          </Button>,
        ]}
      />
    );
  /* v8 ignore start */
  } catch (fallbackError) {
    // Ultimate fallback if ErrorFallback itself throws
    // eslint-disable-next-line no-console
    console.error('[ErrorFallback] Fallback UI failed:', fallbackError);
    return (
      <div style={{ padding: 24, textAlign: 'center', fontFamily: 'sans-serif' }}>
        <h1>Une erreur est survenue</h1>
        <p>Veuillez recharger la page.</p>
        <button onClick={() => window.location.reload()}>Recharger</button>
      </div>
    );
  }
  /* v8 ignore stop */
}
