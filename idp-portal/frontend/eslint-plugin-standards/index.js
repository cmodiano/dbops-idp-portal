import noAntdInternalImports from './rules/no-antd-internal-imports.js';
import requireAppUseapp from './rules/require-app-useapp.js';
import noClassComponents from './rules/no-class-components.js';
import noAntdDeprecatedProps from './rules/no-antd-deprecated-props.js';

export default {
  rules: {
    'no-antd-internal-imports': noAntdInternalImports,
    'require-app-useapp': requireAppUseapp,
    'no-class-components': noClassComponents,
    'no-antd-deprecated-props': noAntdDeprecatedProps,
  },
};
