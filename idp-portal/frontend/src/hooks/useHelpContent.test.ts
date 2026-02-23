import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useHelpContent } from './useHelpContent';
import * as helpService from '../services/help_service';

vi.mock('../services/help_service', () => ({
  getHelpContent: vi.fn(),
}));

describe('useHelpContent', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('returns loading state initially', () => {
    vi.mocked(helpService.getHelpContent).mockImplementation(
      () => new Promise(() => {})
    );

    const { result } = renderHook(() => useHelpContent('test-topic'));

    expect(result.current.loading).toBe(true);
    expect(result.current.content).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('returns content after loading', async () => {
    const mockContent = {
      topic_id: 'test-topic',
      short: 'Short text',
      markdown: '# Help',
    };
    vi.mocked(helpService.getHelpContent).mockResolvedValue(mockContent);

    const { result } = renderHook(() => useHelpContent('test-topic'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.content).toEqual(mockContent);
    expect(result.current.error).toBeNull();
  });

  it('handles errors silently', async () => {
    vi.mocked(helpService.getHelpContent).mockRejectedValue(
      new Error('Failed')
    );

    const { result } = renderHook(() => useHelpContent('bad-topic'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.content).toBeNull();
    expect(result.current.error).toBe('Failed');
  });

  it('reloads when topicId changes', async () => {
    const content1 = {
      topic_id: 'topic-1',
      short: 'First',
      markdown: '# First',
    };
    const content2 = {
      topic_id: 'topic-2',
      short: 'Second',
      markdown: '# Second',
    };
    vi.mocked(helpService.getHelpContent)
      .mockResolvedValueOnce(content1)
      .mockResolvedValueOnce(content2);

    const { result, rerender } = renderHook(
      ({ topicId }) => useHelpContent(topicId),
      { initialProps: { topicId: 'topic-1' } }
    );

    await waitFor(() => {
      expect(result.current.content).toEqual(content1);
    });

    rerender({ topicId: 'topic-2' });

    await waitFor(() => {
      expect(result.current.content).toEqual(content2);
    });
  });
});
