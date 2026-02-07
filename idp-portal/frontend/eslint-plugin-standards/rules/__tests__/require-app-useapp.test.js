import { RuleTester } from 'eslint';
import tseslint from 'typescript-eslint';
import rule from '../require-app-useapp.js';

const ruleTester = new RuleTester({
  languageOptions: {
    ecmaVersion: 2020,
    sourceType: 'module',
    parser: tseslint.parser,
  },
});

ruleTester.run('require-app-useapp', rule, {
  valid: [
    // Regular antd component imports are OK
    { code: "import { Button, Table, Form } from 'antd'" },
    { code: "import { App } from 'antd'" },
    // Modal is OK (UI component, not imperative API)
    { code: "import { Modal } from 'antd'" },
    // Other packages
    { code: "import { message } from 'some-other-package'" },
    { code: "import { notification } from '@custom/lib'" },
    // Type imports
    { code: "import type { TableProps } from 'antd'" },
    // App import alongside other components
    { code: "import { App, Button, Space } from 'antd'" },
  ],
  invalid: [
    {
      code: "import { message } from 'antd'",
      errors: [{ messageId: 'requireAppUseApp' }],
    },
    {
      code: "import { notification } from 'antd'",
      errors: [{ messageId: 'requireAppUseApp' }],
    },
    {
      code: "import { Button, message } from 'antd'",
      errors: [{ messageId: 'requireAppUseApp' }],
    },
    {
      code: "import { message, notification } from 'antd'",
      errors: [
        { messageId: 'requireAppUseApp' },
        { messageId: 'requireAppUseApp' },
      ],
    },
    {
      code: "import { Button, notification, Table } from 'antd'",
      errors: [{ messageId: 'requireAppUseApp' }],
    },
  ],
});
