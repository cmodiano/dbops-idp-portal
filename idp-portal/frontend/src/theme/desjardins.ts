import type { ThemeConfig } from 'antd';

export const desjardinsTheme: ThemeConfig = {
  token: {
    colorPrimary: '#00874E',
    colorBgLayout: '#FAFBFC',
    borderRadius: 6,
    fontFamily:
      "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
  },
  components: {
    Tabs: {
      inkBarColor: '#00874E',
      itemSelectedColor: '#00874E',
      itemColor: '#6B7280',
      itemHoverColor: '#1A1A2E',
    },
  },
};
