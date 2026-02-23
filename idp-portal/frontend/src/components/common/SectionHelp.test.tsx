import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SectionHelp from './SectionHelp';
import * as useHelpContentModule from '../../hooks/useHelpContent';

vi.mock('../../hooks/useHelpContent', () => ({
  useHelpContent: vi.fn(),
}));

// Mock react-markdown to avoid ESM issues in test
vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => <div data-testid="markdown">{children}</div>,
}));

vi.mock('remark-gfm', () => ({
  default: () => {},
}));

vi.mock('rehype-sanitize', () => ({
  default: () => {},
}));

describe('SectionHelp', () => {
  const mockContent = {
    topic_id: 'test-topic',
    short: 'Texte court aide',
    markdown: '# Aide détaillée\n\nContenu complet.',
  };

  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('shows spinner while loading', () => {
    vi.mocked(useHelpContentModule.useHelpContent).mockReturnValue({
      content: null,
      loading: true,
      error: null,
    });

    // Ant Design Spin renders a div with class ant-spin-spinning
    const { container } = render(<SectionHelp topicId="test-topic" />);
    expect(container.querySelector('.ant-spin')).toBeTruthy();
  });

  it('renders help icon with aria-label', async () => {
    vi.mocked(useHelpContentModule.useHelpContent).mockReturnValue({
      content: mockContent,
      loading: false,
      error: null,
    });

    render(<SectionHelp topicId="test-topic" />);

    const icon = screen.getByLabelText('Aide pour cette section');
    expect(icon).toBeInTheDocument();
  });

  it('shows tooltip with short text on hover', async () => {
    vi.mocked(useHelpContentModule.useHelpContent).mockReturnValue({
      content: mockContent,
      loading: false,
      error: null,
    });

    render(<SectionHelp topicId="test-topic" mode="tooltip" />);

    const icon = screen.getByLabelText('Aide pour cette section');
    const user = userEvent.setup();
    await user.hover(icon);

    await waitFor(() => {
      expect(screen.getByText('Texte court aide')).toBeInTheDocument();
    });
  });

  it('shows popover with markdown on click', async () => {
    vi.mocked(useHelpContentModule.useHelpContent).mockReturnValue({
      content: mockContent,
      loading: false,
      error: null,
    });

    render(<SectionHelp topicId="test-topic" mode="popover" />);

    const icon = screen.getByLabelText('Aide pour cette section');
    const user = userEvent.setup();
    await user.click(icon);

    await waitFor(() => {
      expect(screen.getByTestId('markdown')).toBeInTheDocument();
    });
    // The markdown content is rendered as text node with newlines
    expect(screen.getByTestId('markdown').textContent).toContain('Aide détaillée');
  });

  it('opens popover on click in default mode (both)', async () => {
    vi.mocked(useHelpContentModule.useHelpContent).mockReturnValue({
      content: mockContent,
      loading: false,
      error: null,
    });

    render(<SectionHelp topicId="test-topic" />);

    const icon = screen.getByLabelText('Aide pour cette section');
    const user = userEvent.setup();

    await user.click(icon);

    await waitFor(() => {
      expect(screen.getByTestId('markdown')).toBeInTheDocument();
    });
    expect(screen.getByTestId('markdown').textContent).toContain('Aide détaillée');
  });

  it('renders without crash when content is empty', () => {
    vi.mocked(useHelpContentModule.useHelpContent).mockReturnValue({
      content: { topic_id: 'test', short: '', markdown: '' },
      loading: false,
      error: null,
    });

    render(<SectionHelp topicId="test" />);

    const icon = screen.getByLabelText('Aide pour cette section');
    expect(icon).toBeInTheDocument();
  });

  it('renders without crash on error', () => {
    vi.mocked(useHelpContentModule.useHelpContent).mockReturnValue({
      content: null,
      loading: false,
      error: 'Network error',
    });

    // Should not throw — the component renders the icon anyway
    render(<SectionHelp topicId="broken" />);

    const icon = screen.getByLabelText('Aide pour cette section');
    expect(icon).toBeInTheDocument();
  });
});
