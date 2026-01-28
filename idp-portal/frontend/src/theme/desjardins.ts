import type { ThemeConfig } from 'antd';

/**
 * Desjardins theme configuration for Ant Design 6.
 * 
 * AC #3: Configures primary color (#00874E), bordures, and spacings
 * according to UX design specification.
 * 
 * Design tokens:
 * - Primary color: #00874E (Desjardins green)
 * - Background: #FAFBFC (light gray)
 * - Border: #E5E7EB (light gray, 1px)
 * - Spacing: 8px base unit (xs=4px, sm=8px, md=16px, lg=24px, xl=32px, 2xl=48px)
 * - Border radius: 6px (modern, not childish)
 */
export const desjardinsTheme: ThemeConfig = {
  token: {
    // Colors (AC #3)
    colorPrimary: '#00874E',
    colorBgLayout: '#FAFBFC',
    
    // Borders (AC #3)
    borderRadius: 6, // 6px - modern without being childish
    colorBorder: '#E5E7EB', // Light gray borders
    colorBorderSecondary: '#F3F4F6', // Lighter borders for subtle separators
    lineWidth: 1, // 1px fine borders
    
    // Spacings (AC #3) - base unit 8px
    paddingXS: 4, // xs: 4px
    paddingSM: 8, // sm: 8px
    padding: 16, // md: 16px (default)
    paddingMD: 16, // md: 16px
    paddingLG: 24, // lg: 24px
    paddingXL: 32, // xl: 32px
    paddingXXL: 48, // 2xl: 48px
    marginXS: 4,
    marginSM: 8,
    margin: 16,
    marginMD: 16,
    marginLG: 24,
    marginXL: 32,
    marginXXL: 48,
    
    // Typography
    fontFamily:
      "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
    fontSize: 14, // Body text
    fontSizeSM: 12, // Small text
    fontSizeLG: 16, // Subsection
    fontSizeXL: 18, // Section title
    fontSizeHeading1: 24, // Page title
    lineHeight: 1.5, // Body line-height
  },
  components: {
    Tabs: {
      inkBarColor: '#00874E',
      itemSelectedColor: '#00874E',
      itemColor: '#6B7280',
      itemHoverColor: '#1A1A2E',
    },
    Card: {
      borderRadius: 8, // Cards have slightly more rounded corners (8px)
      paddingLG: 24, // Card padding matches lg spacing
    },
    Button: {
      borderRadius: 6,
      controlHeight: 36, // Minimum 36px height for accessibility
    },
  },
};
