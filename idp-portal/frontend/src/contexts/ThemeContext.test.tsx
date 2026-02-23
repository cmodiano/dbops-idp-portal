import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ThemeProvider, useTheme } from './ThemeContext';

// Helper component to expose ThemeContext values
function ThemeDisplay() {
  const { mode, effectiveMode, toggleTheme, setMode } = useTheme();
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <span data-testid="effectiveMode">{effectiveMode}</span>
      <button data-testid="toggle" onClick={toggleTheme}>Toggle</button>
      <button data-testid="setLight" onClick={() => setMode('light')}>Light</button>
      <button data-testid="setDark" onClick={() => setMode('dark')}>Dark</button>
      <button data-testid="setSystem" onClick={() => setMode('system')}>System</button>
    </div>
  );
}

describe('ThemeProvider', () => {
  let mockMatchMedia: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    localStorage.clear();

    // Mock matchMedia - default to light system preference
    mockMatchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('dark') ? false : true,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    window.matchMedia = mockMatchMedia as unknown as typeof window.matchMedia;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders children', () => {
    render(
      <ThemeProvider>
        <span>child</span>
      </ThemeProvider>
    );
    expect(screen.getByText('child')).toBeTruthy();
  });

  it('provides default values when no localStorage', () => {
    render(
      <ThemeProvider>
        <ThemeDisplay />
      </ThemeProvider>
    );

    expect(screen.getByTestId('mode').textContent).toBe('system');
    expect(screen.getByTestId('effectiveMode').textContent).toBe('light');
  });

  it('toggle changes theme (AC #1)', async () => {
    const user = userEvent.setup();

    render(
      <ThemeProvider>
        <ThemeDisplay />
      </ThemeProvider>
    );

    expect(screen.getByTestId('effectiveMode').textContent).toBe('light');

    await user.click(screen.getByTestId('toggle'));

    expect(screen.getByTestId('effectiveMode').textContent).toBe('dark');
    expect(screen.getByTestId('mode').textContent).toBe('dark');
  });

  it('persists preference to localStorage (AC #2)', async () => {
    const user = userEvent.setup();

    render(
      <ThemeProvider>
        <ThemeDisplay />
      </ThemeProvider>
    );

    await user.click(screen.getByTestId('setDark'));

    expect(localStorage.getItem('idp-portal-theme')).toBe('dark');
  });

  it('restores preference from localStorage (AC #2)', () => {
    localStorage.setItem('idp-portal-theme', 'dark');

    render(
      <ThemeProvider>
        <ThemeDisplay />
      </ThemeProvider>
    );

    expect(screen.getByTestId('mode').textContent).toBe('dark');
    expect(screen.getByTestId('effectiveMode').textContent).toBe('dark');
  });

  it('setMode works for all modes', async () => {
    const user = userEvent.setup();

    render(
      <ThemeProvider>
        <ThemeDisplay />
      </ThemeProvider>
    );

    await user.click(screen.getByTestId('setDark'));
    expect(screen.getByTestId('mode').textContent).toBe('dark');

    await user.click(screen.getByTestId('setLight'));
    expect(screen.getByTestId('mode').textContent).toBe('light');

    await user.click(screen.getByTestId('setSystem'));
    expect(screen.getByTestId('mode').textContent).toBe('system');
  });
});

describe('useTheme outside provider', () => {
  it('throws error when used outside ThemeProvider', () => {
    // Suppress console.error for this test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    function InvalidComponent() {
      useTheme();
      return null;
    }

    expect(() => render(<InvalidComponent />)).toThrow(
      'useTheme must be used within a ThemeProvider'
    );

    consoleSpy.mockRestore();
  });
});
