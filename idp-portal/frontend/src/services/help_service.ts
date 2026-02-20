import { apiFetchRaw } from './api_client';

export interface HelpContent {
  topic_id: string;
  short: string;
  markdown: string;
}

const CACHE_DURATION_MS = 10 * 60 * 1000; // 10 minutes

function getCacheKey(topicId: string): string {
  return `help_${topicId}`;
}

export async function getHelpContent(topicId: string): Promise<HelpContent> {
  const cacheKey = getCacheKey(topicId);
  const cached = sessionStorage.getItem(cacheKey);
  if (cached) {
    try {
      const { data, timestamp } = JSON.parse(cached) as {
        data: HelpContent;
        timestamp: number;
      };
      if (Date.now() - timestamp < CACHE_DURATION_MS) {
        return data;
      }
    } catch {
      /* ignore invalid cache */
    }
  }

  try {
    const raw = await apiFetchRaw<{ topic_id?: string; short?: string; markdown?: string }>(
      `help/${topicId}/`
    );
    const data: HelpContent = {
      topic_id: raw.topic_id ?? topicId,
      short: raw.short ?? '',
      markdown: raw.markdown ?? '',
    };
    sessionStorage.setItem(
      cacheKey,
      JSON.stringify({ data, timestamp: Date.now() })
    );
    return data;
  } catch {
    return { topic_id: topicId, short: '', markdown: '' };
  }
}
