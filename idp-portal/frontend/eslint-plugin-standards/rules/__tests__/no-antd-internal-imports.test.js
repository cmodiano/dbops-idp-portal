import { RuleTester } from 'eslint';
import tseslint from 'typescript-eslint';
import rule from '../no-antd-internal-imports.js';

const ruleTester = new RuleTester({
  languageOptions: {
    ecmaVersion: 2020,
    sourceType: 'module',
    parser: tseslint.parser,
  },
});

ruleTester.run('no-antd-internal-imports', rule, {
  valid: [
    // Public API imports are OK
    { code: "import { Table } from 'antd'" },
    { code: "import type { TableProps } from 'antd'" },
    { code: "import { Button, Form, Input } from 'antd'" },
    // Other packages are fine
    { code: "import { something } from 'antd-icons'" },
    { code: "import React from 'react'" },
    // Default import from antd
    { code: "import antd from 'antd'" },
  ],
  invalid: [
    {
      code: "import type { ColumnsType } from 'antd/es/table'",
      errors: [{ messageId: 'noInternalImports' }],
    },
    {
      code: "import type { SorterResult } from 'antd/es/table/interface'",
      errors: [{ messageId: 'noInternalImports' }],
    },
    {
      code: "import { internalUtils } from 'antd/es/utils'",
      errors: [{ messageId: 'noInternalImports' }],
    },
    {
      code: "import type { DefaultOptionType } from 'antd/es/select'",
      errors: [{ messageId: 'noInternalImports' }],
    },
    {
      code: "import { something } from 'antd/es/deep/nested/path'",
      errors: [{ messageId: 'noInternalImports' }],
    },
  ],
});
