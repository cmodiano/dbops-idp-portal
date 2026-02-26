import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '../../contexts/ThemeContext';
import { TagCloud } from './TagCloud';
import type { CatalogTagWithCount } from '../../services/catalog_service';

const mockTags: CatalogTagWithCount[] = [
  { name: 'oracle', action_count: 5 },
  { name: 'patching', action_count: 3 },
  { name: 'provisioning', action_count: 8 },
  { name: 'monitoring', action_count: 2 },
];

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe('TagCloud', () => {
  beforeEach(() => {
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

  it('renders all tags with their counts (AC1, AC6)', () => {
    renderWithTheme(<TagCloud tags={mockTags} selectedTags={[]} onSelectionChange={() => {}} />);

    expect(screen.getByText('oracle (5)')).toBeInTheDocument();
    expect(screen.getByText('patching (3)')).toBeInTheDocument();
    expect(screen.getByText('provisioning (8)')).toBeInTheDocument();
    expect(screen.getByText('monitoring (2)')).toBeInTheDocument();
  });

  it('renders tags in an accessible group with keyboard focus (AC6)', () => {
    renderWithTheme(<TagCloud tags={mockTags} selectedTags={[]} onSelectionChange={() => {}} />);

    const group = screen.getByRole('group', { name: 'Filtres par tags' });
    expect(group).toBeInTheDocument();
    // Each tag is focusable (tabIndex=0) for keyboard accessibility
    const focusableTags = group.querySelectorAll('[tabindex="0"]');
    expect(focusableTags.length).toBe(4);
  });

  it('toggles tag selection on click (AC2)', () => {
    const handleChange = vi.fn();
    renderWithTheme(<TagCloud tags={mockTags} selectedTags={[]} onSelectionChange={handleChange} />);

    fireEvent.click(screen.getByText('oracle (5)'));

    expect(handleChange).toHaveBeenCalledWith(['oracle']);
  });

  it('adds tag to existing selection (multi-select AND) (AC3)', () => {
    const handleChange = vi.fn();
    renderWithTheme(<TagCloud tags={mockTags} selectedTags={['oracle']} onSelectionChange={handleChange} />);

    fireEvent.click(screen.getByText('patching (3)'));

    expect(handleChange).toHaveBeenCalledWith(['oracle', 'patching']);
  });

  it('removes tag from selection when clicked again (AC4)', () => {
    const handleChange = vi.fn();
    renderWithTheme(<TagCloud tags={mockTags} selectedTags={['oracle', 'patching']} onSelectionChange={handleChange} />);

    fireEvent.click(screen.getByText('oracle (5)'));

    expect(handleChange).toHaveBeenCalledWith(['patching']);
  });

  it('shows reset button only when tags are selected (AC5)', () => {
    const { rerender } = renderWithTheme(
      <TagCloud tags={mockTags} selectedTags={[]} onSelectionChange={() => {}} />
    );

    expect(screen.queryByRole('button', { name: 'Réinitialiser les filtres par tags' })).not.toBeInTheDocument();

    rerender(<ThemeProvider><TagCloud tags={mockTags} selectedTags={['oracle']} onSelectionChange={() => {}} /></ThemeProvider>);

    expect(screen.getByRole('button', { name: 'Réinitialiser les filtres par tags' })).toBeInTheDocument();
  });

  it('calls onSelectionChange with empty array when reset is clicked (AC5)', () => {
    const handleChange = vi.fn();
    renderWithTheme(<TagCloud tags={mockTags} selectedTags={['oracle', 'patching']} onSelectionChange={handleChange} />);

    fireEvent.click(screen.getByRole('button', { name: 'Réinitialiser les filtres par tags' }));

    expect(handleChange).toHaveBeenCalledWith([]);
  });

  it('applies distinct style to selected tags (AC6)', () => {
    renderWithTheme(<TagCloud tags={mockTags} selectedTags={['oracle']} onSelectionChange={() => {}} />);

    // Selected tag should have checked style (Ant Design Tag.CheckableTag)
    // The class is on the outer CheckableTag span element
    const oracleTag = screen.getByText('oracle (5)').closest('.ant-tag-checkable');
    expect(oracleTag).toHaveClass('ant-tag-checkable-checked');
  });

  it('renders empty state when no tags provided', () => {
    renderWithTheme(<TagCloud tags={[]} selectedTags={[]} onSelectionChange={() => {}} />);

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('is keyboard accessible - toggles on Enter key', () => {
    const handleChange = vi.fn();
    renderWithTheme(<TagCloud tags={mockTags} selectedTags={[]} onSelectionChange={handleChange} />);

    const tagButton = screen.getByText('oracle (5)').closest('span')!;
    fireEvent.keyDown(tagButton, { key: 'Enter' });

    expect(handleChange).toHaveBeenCalledWith(['oracle']);
  });

  it('is keyboard accessible - toggles on Space key', () => {
    const handleChange = vi.fn();
    renderWithTheme(<TagCloud tags={mockTags} selectedTags={[]} onSelectionChange={handleChange} />);

    const tagButton = screen.getByText('oracle (5)').closest('span')!;
    fireEvent.keyDown(tagButton, { key: ' ' });

    expect(handleChange).toHaveBeenCalledWith(['oracle']);
  });

  describe('Story 46.2 — taille minimale 44px (WCAG 2.5.5)', () => {
    it('chaque CheckableTag a un style minHeight >= 44px', () => {
      renderWithTheme(<TagCloud tags={mockTags} selectedTags={[]} onSelectionChange={() => {}} />);

      const checkableTags = document.querySelectorAll('.ant-tag-checkable');
      expect(checkableTags.length).toBeGreaterThan(0);
      checkableTags.forEach((tag) => {
        const el = tag as HTMLElement;
        const minHeight = parseInt(el.style.minHeight);
        expect(minHeight).toBeGreaterThanOrEqual(44);
      });
    });

    // Régression: vérifie que le clic sur un tag appelle onChange (comportement déjà couvert par "toggles tag selection on click (AC2)")
    it('les tags existants restent sélectionnables (onChange appelé au clic)', () => {
      const handleChange = vi.fn();
      renderWithTheme(<TagCloud tags={mockTags} selectedTags={[]} onSelectionChange={handleChange} />);

      fireEvent.click(screen.getByText('oracle (5)'));
      expect(handleChange).toHaveBeenCalledWith(['oracle']);
    });

    it('le bouton réinitialiser respecte la hauteur minimale 44px', () => {
      renderWithTheme(<TagCloud tags={mockTags} selectedTags={['oracle']} onSelectionChange={() => {}} />);

      const resetBtn = screen.getByRole('button', { name: 'Réinitialiser les filtres par tags' });
      const minHeight = parseInt(resetBtn.style.minHeight || '0', 10);
      expect(minHeight).toBeGreaterThanOrEqual(44);
    });
  });
});
