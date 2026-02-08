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
    // Modal JSX component import is OK (only imperative API is forbidden)
    { code: "import { Modal } from 'antd'" },
    // Other packages
    { code: "import { message } from 'some-other-package'" },
    { code: "import { notification } from '@custom/lib'" },
    // Type imports
    { code: "import type { TableProps } from 'antd'" },
    // App import alongside other components
    { code: "import { App, Button, Space } from 'antd'" },
    // Modal imported from antd but not used imperatively is OK
    { code: "import { Modal } from 'antd'; const m = Modal" },
    // App.useApp() modal usage is the correct pattern
    { code: "const { modal } = App.useApp(); modal.confirm({ title: 'OK' })" },
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
    // Modal imperative API must go through App.useApp()
    {
      code: "import { Modal } from 'antd'; Modal.confirm({ title: 'Delete?' })",
      errors: [{ messageId: 'requireModalUseApp' }],
    },
    {
      code: "import { Modal } from 'antd'; Modal.error({ title: 'Error' })",
      errors: [{ messageId: 'requireModalUseApp' }],
    },
    {
      code: "import { Modal } from 'antd'; Modal.info({ title: 'Info' })",
      errors: [{ messageId: 'requireModalUseApp' }],
    },
    // Combined: message import + Modal imperative
    {
      code: "import { message, Modal } from 'antd'; Modal.confirm({ title: 'OK' })",
      errors: [
        { messageId: 'requireAppUseApp' },
        { messageId: 'requireModalUseApp' },
      ],
    },
  ],
});
