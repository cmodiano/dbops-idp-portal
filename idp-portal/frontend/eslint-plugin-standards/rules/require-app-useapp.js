/**
 * @fileoverview Disallow direct imports of message, notification, or Modal from 'antd'.
 * Use App.useApp() hook instead: const { message, notification, modal } = App.useApp().
 * @see FRONTEND-STANDARDS.md Section 4
 */

const FORBIDDEN_SPECIFIERS = new Set(['message', 'notification']);

/** @type {import('eslint').Rule.RuleModule} */
export default {
  meta: {
    type: 'problem',
    docs: {
      description:
        'Require App.useApp() for message, notification, and modal instead of direct antd imports',
      recommended: true,
    },
    messages: {
      requireAppUseApp:
        "Do not import '{{ name }}' directly from 'antd'. Use App.useApp() instead: const { {{ name }} } = App.useApp(). See FRONTEND-STANDARDS.md Section 4.",
    },
    schema: [],
  },
  create(context) {
    return {
      ImportDeclaration(node) {
        const source = node.source.value;
        if (source !== 'antd') return;

        for (const specifier of node.specifiers) {
          if (specifier.type !== 'ImportSpecifier') continue;
          const imported = specifier.imported.name;

          if (FORBIDDEN_SPECIFIERS.has(imported)) {
            context.report({
              node: specifier,
              messageId: 'requireAppUseApp',
              data: { name: imported },
            });
          }
        }
      },
    };
  },
};
