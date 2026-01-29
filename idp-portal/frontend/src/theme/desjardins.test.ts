import { describe, it, expect } from 'vitest';
import { lightTheme, darkTheme, desjardinsTheme } from './desjardins';

describe('desjardins themes', () => {
  describe('lightTheme', () => {
    it('sets primary color to #00874E (AC #7)', () => {
      expect(lightTheme.token?.colorPrimary).toBe('#00874E');
    });

    it('sets light background colors (AC #4, #5)', () => {
      expect(lightTheme.token?.colorBgBase).toBe('#f4f6f8');
      expect(lightTheme.token?.colorBgContainer).toBe('#FFFFFF');
      expect(lightTheme.token?.colorBgLayout).toBe('#f4f6f8');
    });

    it('sets light text colors', () => {
      expect(lightTheme.token?.colorText).toBe('#1a1a2e');
      expect(lightTheme.token?.colorTextSecondary).toBe('#5c5c6d');
    });

    it('defines border radius token', () => {
      expect(lightTheme.token?.borderRadius).toBe(6);
      expect(lightTheme.token?.borderRadiusLG).toBe(8);
    });

    it('configures Tabs component tokens', () => {
      const tabs = (lightTheme.components as Record<string, unknown>)?.Tabs as Record<string, unknown>;
      expect(tabs).toBeDefined();
      expect(tabs.inkBarColor).toBe('#00874E');
      expect(tabs.itemSelectedColor).toBe('#00874E');
    });

    it('uses defaultAlgorithm', () => {
      expect(lightTheme.algorithm).toBeDefined();
    });
  });

  describe('darkTheme', () => {
    it('sets primary color to #00874E (AC #7 - preserved in dark)', () => {
      expect(darkTheme.token?.colorPrimary).toBe('#00874E');
    });

    it('sets dark background colors (AC #4, #5)', () => {
      expect(darkTheme.token?.colorBgBase).toBe('#0f0f14');
      expect(darkTheme.token?.colorBgContainer).toBe('#1a1a24');
      expect(darkTheme.token?.colorBgLayout).toBe('#0f0f14');
    });

    it('sets dark text colors', () => {
      expect(darkTheme.token?.colorText).toBe('#f0f0f2');
      expect(darkTheme.token?.colorTextSecondary).toBe('#a8a8b3');
    });

    it('uses same border radius as light theme (AC #4)', () => {
      expect(darkTheme.token?.borderRadius).toBe(lightTheme.token?.borderRadius);
      expect(darkTheme.token?.borderRadiusLG).toBe(lightTheme.token?.borderRadiusLG);
    });

    it('configures same Tabs component tokens as light', () => {
      const darkTabs = (darkTheme.components as Record<string, unknown>)?.Tabs as Record<string, unknown>;
      const lightTabs = (lightTheme.components as Record<string, unknown>)?.Tabs as Record<string, unknown>;
      expect(darkTabs.inkBarColor).toBe(lightTabs.inkBarColor);
      expect(darkTabs.itemSelectedColor).toBe(lightTabs.itemSelectedColor);
    });

    it('uses darkAlgorithm', () => {
      expect(darkTheme.algorithm).toBeDefined();
    });
  });

  describe('desjardinsTheme (deprecated)', () => {
    it('is an alias for lightTheme', () => {
      expect(desjardinsTheme).toBe(lightTheme);
    });
  });
});
