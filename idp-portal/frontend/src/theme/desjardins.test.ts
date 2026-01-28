import { describe, it, expect } from 'vitest';
import { desjardinsTheme } from './desjardins';

describe('desjardinsTheme', () => {
  it('sets primary color to #00874E (AC #3)', () => {
    expect(desjardinsTheme.token?.colorPrimary).toBe('#00874E');
  });

  it('sets background layout to #FAFBFC (AC #4)', () => {
    expect(desjardinsTheme.token?.colorBgLayout).toBe('#FAFBFC');
  });

  it('defines border radius token', () => {
    expect(desjardinsTheme.token?.borderRadius).toBeDefined();
  });

  it('configures Tabs component tokens for role-based navigation', () => {
    const tabs = (desjardinsTheme.components as Record<string, unknown>)?.Tabs as Record<string, unknown>;
    expect(tabs).toBeDefined();
    expect(tabs.inkBarColor).toBe('#00874E');
    expect(tabs.itemSelectedColor).toBe('#00874E');
    expect(tabs.itemColor).toBe('#6B7280');
    expect(tabs.itemHoverColor).toBe('#1A1A2E');
  });
});
