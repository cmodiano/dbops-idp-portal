import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router';
import { AuthProvider } from '../../contexts/AuthContext';
import { ProtectedRoute } from './ProtectedRoute';

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('redirects to /login when not authenticated', async () => {
    // Refresh fails → not authenticated
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<span>Login Page</span>} />
            <Route
              path="/protected"
              element={
                <ProtectedRoute>
                  <span>Secret Content</span>
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Login Page')).toBeTruthy();
    });
    expect(screen.queryByText('Secret Content')).toBeNull();
  });

  it('renders children when authenticated', async () => {
    // Refresh succeeds → authenticated
    global.fetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: { access_token: 'valid-token', token_type: 'bearer' } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: { id: 1, username: 'marc', display_name: 'Marc', profile: 'dbops' } }),
      });

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<span>Login Page</span>} />
            <Route
              path="/protected"
              element={
                <ProtectedRoute>
                  <span>Secret Content</span>
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText('Secret Content')).toBeTruthy();
    });
    expect(screen.queryByText('Login Page')).toBeNull();
  });
});
