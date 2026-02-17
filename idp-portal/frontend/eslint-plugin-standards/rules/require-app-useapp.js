/**
 * @fileoverview Disallow direct imports of message, notification from 'antd'
 * and imperative usage of Modal (Modal.confirm, Modal.error, etc.).
 * Use App.useApp() hook instead: const { message, notification, modal } = App.useApp().
 * @see FRONTEND-STANDARDS.md Section 4
 */

const FORBIDDEN_IMPORT_SPECIFIERS = new Set(['message', 'notification']);
const MODAL_IMPERATIVE_METHODS = new Set(['confirm', 'info', 'success', 'error', 'warning', 'destroyAll']);

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
      requireModalUseApp:
        "Do not use 'Modal.{{ method }}()' directly. Use App.useApp() instead: const { modal } = App.useApp(); modal.{{ method }}(). See FRONTEND-STANDARDS.md Section 4.",
    },
    schema: [],
  },
  create(context) {
    const modalImportedFromAntd = new Set();

    return {
      ImportDeclaration(node) {
        const source = node.source.value;
        if (source !== 'antd') return;

        for (const specifier of node.specifiers) {
          if (specifier.type !== 'ImportSpecifier') continue;
          const imported = specifier.imported.name;

          if (FORBIDDEN_IMPORT_SPECIFIERS.has(imported)) {
            context.report({
              node: specifier,
              messageId: 'requireAppUseApp',
              data: { name: imported },
            });
          }

          if (imported === 'Modal') {
            modalImportedFromAntd.add(specifier.local.name);
          }
        }
      },

      MemberExpression(node) {
        if (
          node.object.type === 'Identifier' &&
          modalImportedFromAntd.has(node.object.name) &&
          node.property.type === 'Identifier' &&
          MODAL_IMPERATIVE_METHODS.has(node.property.name)
        ) {
          context.report({
            node,
            messageId: 'requireModalUseApp',
            data: { method: node.property.name },
          });
        }
      },
    };
  },
};
