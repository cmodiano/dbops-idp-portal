/**
 * @fileoverview Disallow deprecated props on Ant Design components.
 *
 * Tracks antd imports and flags deprecated JSX props on those components.
 *
 * Currently enforced:
 *   - Alert:  `message` → use `title` instead (deprecated in antd v5)
 *   - Drawer: `width` → use `styles.wrapper.width` (deprecated in antd v5)
 *   - Space:  `direction` → use `orientation` instead (deprecated in antd v5)
 *
 * @see FRONTEND-STANDARDS.md
 */

/**
 * Map of antd component name → deprecated prop → replacement info.
 * Add new entries here as antd deprecates more props.
 */
const DEPRECATED_PROPS = {
  Alert: {
    message: {
      message:
        '[antd] `message` on <Alert> is deprecated. Use `title` instead (antd v5+). ' +
        'See https://ant.design/components/alert#api',
    },
  },
  Drawer: {
    width: {
      message:
        '[antd] `width` on <Drawer> is deprecated. Use `styles.wrapper.width` instead (antd v5+). ' +
        'See https://ant.design/components/drawer#api',
    },
  },
  Space: {
    direction: {
      message:
        '[antd] `direction` on <Space> is deprecated. Use `orientation` instead (antd v5+). ' +
        'See https://ant.design/components/space#api',
    },
  },
};

/** @type {import('eslint').Rule.RuleModule} */
export default {
  meta: {
    type: 'suggestion',
    docs: {
      description: 'Disallow deprecated props on Ant Design components',
      recommended: true,
    },
    messages: {
      deprecatedProp: '{{ message }}',
    },
    schema: [],
  },

  create(context) {
    /** localName → antd component name (e.g. "MyDrawer" → "Drawer") */
    const antdImports = new Map();

    return {
      ImportDeclaration(node) {
        if (node.source.value !== 'antd') return;
        for (const specifier of node.specifiers) {
          if (specifier.type !== 'ImportSpecifier') continue;
          const imported = specifier.imported.name;
          if (DEPRECATED_PROPS[imported]) {
            antdImports.set(specifier.local.name, imported);
          }
        }
      },

      JSXOpeningElement(node) {
        const componentName =
          node.name.type === 'JSXIdentifier' ? node.name.name : null;
        if (!componentName) return;

        const antdName = antdImports.get(componentName);
        if (!antdName) return;

        const deprecated = DEPRECATED_PROPS[antdName];

        for (const attr of node.attributes) {
          if (attr.type !== 'JSXAttribute') continue;
          const propName =
            attr.name.type === 'JSXIdentifier' ? attr.name.name : null;
          if (!propName) continue;

          const deprecation = deprecated[propName];
          if (deprecation) {
            context.report({
              node: attr,
              messageId: 'deprecatedProp',
              data: { message: deprecation.message },
            });
          }
        }
      },
    };
  },
};
