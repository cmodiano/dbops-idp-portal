/**
 * Tests for ActionDrawerPreview — Markdown component renderer coverage (Story 55.6).
 * Covers lines 253-307 (h1-h6, p, code inline/block, table, th, td renderers).
 * Uses a separate vi.mock for react-markdown that captures and invokes the components prop.
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { ThemeProvider } from '../../contexts/ThemeContext';
import type { ActionPreviewData } from '../../types/api';

// Capture the components prop from Markdown for direct invocation
let capturedComponents: Record<string, (props: Record<string, unknown>) => React.ReactNode> | null = null;

vi.mock('react-markdown', () => ({
  __esModule: true,
  default: function MockMarkdown({
    children,
    components: comps,
  }: {
    children: string;
    components?: Record<string, (props: Record<string, unknown>) => React.ReactNode>;
  }) {
    capturedComponents = comps ?? null;
    return React.createElement('div', { 'data-testid': 'markdown-content' }, children);
  },
}));

// Also mock remark-gfm and rehype-sanitize (side-effect-only plugins)
vi.mock('remark-gfm', () => ({ default: () => {} }));
vi.mock('rehype-sanitize', () => ({ default: () => {} }));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn().mockReturnValue({
    isAuthenticated: true,
    isBusinessProfile: false,
    isLoading: false,
    user: null,
    accessToken: null,
    login: vi.fn(),
    logout: vi.fn(),
    refreshToken: vi.fn(),
    hasTab: vi.fn().mockReturnValue(true),
  }),
}));

// Import AFTER mocking
import { ActionDrawerPreview } from './ActionDrawerPreview';

const mockActionWithDoc: ActionPreviewData = {
  name: 'Test Action',
  description: 'Test description.',
  engine: 'Oracle',
  platform: 'AAP',
  impact_level: 'low',
  parameters_schema: {},
  tags: [],
  documentation_md: '# Documentation\n\nSome content.',
};

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe('ActionDrawerPreview — Markdown renderer coverage (lignes 253-307)', () => {
  beforeEach(() => {
    capturedComponents = null;
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('dark') ? false : true,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
  });

  it('renders ActionDrawerPreview with documentation and captures Markdown components', async () => {
    renderWithTheme(<ActionDrawerPreview action={mockActionWithDoc} />);

    // Wait for Suspense to resolve and Markdown to be rendered
    await waitFor(() => {
      expect(capturedComponents).not.toBeNull();
    }, { timeout: 5000 });

    expect(capturedComponents).toBeDefined();
  });

  it('h1 renderer — renvoie Title level 3 (ligne 253)', async () => {
    renderWithTheme(<ActionDrawerPreview action={mockActionWithDoc} />);
    await waitFor(() => expect(capturedComponents).not.toBeNull());

    const { container } = render(
      <ThemeProvider>
        {capturedComponents!.h1({ children: 'Titre H1' }) as React.ReactElement}
      </ThemeProvider>
    );
    expect(container.textContent).toContain('Titre H1');
  });

  it('h2 renderer — renvoie Title level 4 (ligne 254)', async () => {
    renderWithTheme(<ActionDrawerPreview action={mockActionWithDoc} />);
    await waitFor(() => expect(capturedComponents).not.toBeNull());

    const { container } = render(
      <ThemeProvider>
        {capturedComponents!.h2({ children: 'Titre H2' }) as React.ReactElement}
      </ThemeProvider>
    );
    expect(container.textContent).toContain('Titre H2');
  });

  it('h3 renderer — renvoie Title level 5 (ligne 255)', async () => {
    renderWithTheme(<ActionDrawerPreview action={mockActionWithDoc} />);
    await waitFor(() => expect(capturedComponents).not.toBeNull());

    const { container } = render(
      <ThemeProvider>
        {capturedComponents!.h3({ children: 'Titre H3' }) as React.ReactElement}
      </ThemeProvider>
    );
    expect(container.textContent).toContain('Titre H3');
  });

  it('h4 renderer — renvoie Text strong (ligne 256)', async () => {
    renderWithTheme(<ActionDrawerPreview action={mockActionWithDoc} />);
    await waitFor(() => expect(capturedComponents).not.toBeNull());

    const { container } = render(
      <ThemeProvider>
        {capturedComponents!.h4({ children: 'Titre H4' }) as React.ReactElement}
      </ThemeProvider>
    );
    expect(container.textContent).toContain('Titre H4');
  });

  it('h5 renderer — renvoie Text strong (ligne 257)', async () => {
    renderWithTheme(<ActionDrawerPreview action={mockActionWithDoc} />);
    await waitFor(() => expect(capturedComponents).not.toBeNull());

    const { container } = render(
      <ThemeProvider>
        {capturedComponents!.h5({ children: 'Titre H5' }) as React.ReactElement}
      </ThemeProvider>
    );
    expect(container.textContent).toContain('Titre H5');
  });

  it('h6 renderer — renvoie Text strong (ligne 258)', async () => {
    renderWithTheme(<ActionDrawerPreview action={mockActionWithDoc} />);
    await waitFor(() => expect(capturedComponents).not.toBeNull());

    const { container } = render(
      <ThemeProvider>
        {capturedComponents!.h6({ children: 'Titre H6' }) as React.ReactElement}
      </ThemeProvider>
    );
    expect(container.textContent).toContain('Titre H6');
  });

  it('p renderer — renvoie Paragraph (ligne 260)', async () => {
    renderWithTheme(<ActionDrawerPreview action={mockActionWithDoc} />);
    await waitFor(() => expect(capturedComponents).not.toBeNull());

    const { container } = render(
      <ThemeProvider>
        {capturedComponents!.p({ children: 'Paragraphe de test' }) as React.ReactElement}
      </ThemeProvider>
    );
    expect(container.textContent).toContain('Paragraphe de test');
  });

  it('code renderer inline — renvoie Text code quand className est absent (lignes 263-265)', async () => {
    renderWithTheme(<ActionDrawerPreview action={mockActionWithDoc} />);
    await waitFor(() => expect(capturedComponents).not.toBeNull());

    // className undefined → isInline = true → returns <Text code>
    const { container } = render(
      <ThemeProvider>
        {capturedComponents!.code({ children: 'inline code', className: undefined }) as React.ReactElement}
      </ThemeProvider>
    );
    expect(container.textContent).toContain('inline code');
    // Should render as code element (antd Text code)
    const codeEl = container.querySelector('code');
    expect(codeEl).not.toBeNull();
  });

  it('code renderer block — renvoie pre+code quand className est présent (lignes 267-280)', async () => {
    renderWithTheme(<ActionDrawerPreview action={mockActionWithDoc} />);
    await waitFor(() => expect(capturedComponents).not.toBeNull());

    // className present → isInline = false → returns <pre><code>
    const { container } = render(
      <ThemeProvider>
        {capturedComponents!.code({
          children: 'const x = 1;',
          className: 'language-javascript',
        }) as React.ReactElement}
      </ThemeProvider>
    );
    expect(container.textContent).toContain('const x = 1;');
    const preEl = container.querySelector('pre');
    expect(preEl).not.toBeNull();
  });

  it('table renderer — renvoie table stylisée (lignes 283-293)', async () => {
    renderWithTheme(<ActionDrawerPreview action={mockActionWithDoc} />);
    await waitFor(() => expect(capturedComponents).not.toBeNull());

    const { container } = render(
      <ThemeProvider>
        {capturedComponents!.table({ children: React.createElement('tbody') }) as React.ReactElement}
      </ThemeProvider>
    );
    const tableEl = container.querySelector('table');
    expect(tableEl).not.toBeNull();
    expect(tableEl?.style.width).toBe('100%');
  });

  it('th renderer — renvoie th avec styles (lignes 294-305)', async () => {
    renderWithTheme(<ActionDrawerPreview action={mockActionWithDoc} />);
    await waitFor(() => expect(capturedComponents).not.toBeNull());

    const { container } = render(
      <ThemeProvider>
        {capturedComponents!.th({ children: 'Colonne' }) as React.ReactElement}
      </ThemeProvider>
    );
    const thEl = container.querySelector('th');
    expect(thEl).not.toBeNull();
    expect(thEl?.textContent).toContain('Colonne');
  });

  it('td renderer — renvoie td avec styles (lignes 306-314)', async () => {
    renderWithTheme(<ActionDrawerPreview action={mockActionWithDoc} />);
    await waitFor(() => expect(capturedComponents).not.toBeNull());

    const { container } = render(
      <ThemeProvider>
        {capturedComponents!.td({ children: 'Valeur' }) as React.ReactElement}
      </ThemeProvider>
    );
    const tdEl = container.querySelector('td');
    expect(tdEl).not.toBeNull();
    expect(tdEl?.textContent).toContain('Valeur');
  });

  it('tous les renderers couverts — vérification de présence dans components', async () => {
    renderWithTheme(<ActionDrawerPreview action={mockActionWithDoc} />);
    await waitFor(() => expect(capturedComponents).not.toBeNull());

    // Verify all expected renderers are defined
    const expectedRenderers = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'code', 'table', 'th', 'td'];
    for (const key of expectedRenderers) {
      expect(capturedComponents![key], `renderer "${key}" doit être défini`).toBeDefined();
      expect(typeof capturedComponents![key]).toBe('function');
    }
  });

  it('invoke all renderers in one act for full branch coverage', async () => {
    renderWithTheme(<ActionDrawerPreview action={mockActionWithDoc} />);
    await waitFor(() => expect(capturedComponents).not.toBeNull());

    const comps = capturedComponents!;

    // Render all renderers to ensure line coverage
    act(() => {
      render(
        <ThemeProvider>
          <div>
            {comps.h1({ children: 'H1' }) as React.ReactElement}
            {comps.h2({ children: 'H2' }) as React.ReactElement}
            {comps.h3({ children: 'H3' }) as React.ReactElement}
            {comps.h4({ children: 'H4' }) as React.ReactElement}
            {comps.h5({ children: 'H5' }) as React.ReactElement}
            {comps.h6({ children: 'H6' }) as React.ReactElement}
            {comps.p({ children: 'Para' }) as React.ReactElement}
            {comps.code({ children: 'inline', className: undefined }) as React.ReactElement}
            {comps.code({ children: 'block', className: 'language-bash' }) as React.ReactElement}
            {comps.table({ children: React.createElement('tbody') }) as React.ReactElement}
            {comps.th({ children: 'TH' }) as React.ReactElement}
            {comps.td({ children: 'TD' }) as React.ReactElement}
          </div>
        </ThemeProvider>
      );
    });

    // All renderers executed without error
    expect(screen.getAllByText('H1').length).toBeGreaterThan(0);
    expect(screen.getAllByText('H2').length).toBeGreaterThan(0);
  });
});
