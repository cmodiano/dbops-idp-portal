/**
 * @fileoverview Disallow internal Ant Design imports from 'antd/es/*'.
 * Use public API imports from 'antd' instead.
 * @see FRONTEND-STANDARDS.md Section 3
 */

/** @type {import('eslint').Rule.RuleModule} */
export default {
  meta: {
    type: 'problem',
    docs: {
      description: 'Disallow internal Ant Design imports from antd/es/*',
      recommended: true,
    },
    messages: {
      noInternalImports:
        "Do not import from '{{ source }}'. Use the public API: import { ... } from 'antd'. See FRONTEND-STANDARDS.md Section 3.",
    },
    schema: [],
  },
  create(context) {
    return {
      ImportDeclaration(node) {
        const source = node.source.value;
        if (typeof source === 'string' && source.startsWith('antd/es')) {
          context.report({
            node: node.source,
            messageId: 'noInternalImports',
            data: { source },
          });
        }
      },
    };
  },
};
