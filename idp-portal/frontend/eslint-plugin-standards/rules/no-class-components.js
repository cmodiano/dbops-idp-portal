/**
 * @fileoverview Disallow React class components.
 * Use function components with hooks instead.
 * @see FRONTEND-STANDARDS.md Section 1
 */

const REACT_COMPONENT_NAMES = new Set([
  'Component',
  'PureComponent',
]);

/** @type {import('eslint').Rule.RuleModule} */
export default {
  meta: {
    type: 'problem',
    docs: {
      description: 'Disallow React class components — use function components with hooks',
      recommended: true,
    },
    messages: {
      noClassComponents:
        "Class component '{{ name }}' is not allowed. Use a function component with hooks instead. See FRONTEND-STANDARDS.md Section 1.",
    },
    schema: [],
  },
  create(context) {
    return {
      ClassDeclaration(node) {
        if (isReactClassComponent(node)) {
          context.report({
            node,
            messageId: 'noClassComponents',
            data: { name: node.id ? node.id.name : '<anonymous>' },
          });
        }
      },
      ClassExpression(node) {
        if (isReactClassComponent(node)) {
          context.report({
            node,
            messageId: 'noClassComponents',
            data: { name: node.id ? node.id.name : '<anonymous>' },
          });
        }
      },
    };
  },
};

/**
 * Checks if a class node extends React.Component or React.PureComponent.
 */
function isReactClassComponent(node) {
  const superClass = node.superClass;
  if (!superClass) return false;

  // class Foo extends Component
  if (superClass.type === 'Identifier' && REACT_COMPONENT_NAMES.has(superClass.name)) {
    return true;
  }

  // class Foo extends React.Component
  if (
    superClass.type === 'MemberExpression' &&
    superClass.object.type === 'Identifier' &&
    superClass.object.name === 'React' &&
    superClass.property.type === 'Identifier' &&
    REACT_COMPONENT_NAMES.has(superClass.property.name)
  ) {
    return true;
  }

  return false;
}
