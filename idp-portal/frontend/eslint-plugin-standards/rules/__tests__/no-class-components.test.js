import { RuleTester } from 'eslint';
import rule from '../no-class-components.js';

const ruleTester = new RuleTester({
  languageOptions: { ecmaVersion: 2020, sourceType: 'module' },
});

ruleTester.run('no-class-components', rule, {
  valid: [
    // Function components
    { code: 'function MyComponent() { return null; }' },
    { code: 'const MyComponent = () => null;' },
    { code: 'const MyComponent = function() { return null; };' },
    // Regular classes (not React components)
    { code: 'class MyService { getData() {} }' },
    { code: 'class ApiClient extends BaseClient {}' },
    // Arrow function with hooks
    { code: 'const MyComponent = () => { const [state, setState] = useState(0); return null; };' },
  ],
  invalid: [
    {
      code: 'class MyComponent extends React.Component { render() { return null; } }',
      errors: [{ messageId: 'noClassComponents', data: { name: 'MyComponent' } }],
    },
    {
      code: 'class MyComponent extends React.PureComponent { render() { return null; } }',
      errors: [{ messageId: 'noClassComponents', data: { name: 'MyComponent' } }],
    },
    {
      code: 'class MyComponent extends Component { render() { return null; } }',
      errors: [{ messageId: 'noClassComponents', data: { name: 'MyComponent' } }],
    },
    {
      code: 'class MyComponent extends PureComponent { render() { return null; } }',
      errors: [{ messageId: 'noClassComponents', data: { name: 'MyComponent' } }],
    },
    // Class expression
    {
      code: 'const Comp = class extends React.Component { render() { return null; } }',
      errors: [{ messageId: 'noClassComponents', data: { name: '<anonymous>' } }],
    },
  ],
});
