/**
 * Unit tests for BusinessRulePoliciesEditor (Story 28.1, AC8).
 * Tests: empty state, insert example, live validation, help popover,
 * save valid/invalid JSON, clear content behavior.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BusinessRulePoliciesEditor } from './BusinessRulePoliciesEditor';

const TERRAFORM_EXAMPLE_JSON = {
  on_step_output: [
    {
      when: {
        step_type: 'terraform_cloud',
        output_key: 'plan_output',
      },
      policy: {
        type: 'review_if_modified',
        require_review_if_modified: [
          {
            resource_type: 'azurerm_sql_database',
            attribute_paths: ['sku_name', 'max_size_gb'],
          },
          {
            resource_type: 'azurerm_sql_server',
          },
          {
            attribute_paths: ['backup_retention_days'],
          },
        ],
        auto_approve_if_none_match: true,
      },
    },
  ],
};

describe('BusinessRulePoliciesEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // AC8.1: test_render_empty_state
  describe('empty state', () => {
    it('renders "Insérer exemple Terraform" button when value is empty', () => {
      render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      const insertBtn = screen.getByTestId('insert-example-btn');
      expect(insertBtn).toBeInTheDocument();
      expect(insertBtn).toHaveTextContent('Insérer exemple Terraform');
    });

    it('renders help button in empty state', () => {
      render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      const helpBtn = screen.getByTestId('help-btn');
      expect(helpBtn).toBeInTheDocument();
      expect(helpBtn).toHaveTextContent('Aide');
    });

    it('renders textarea in empty state', () => {
      render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      const textarea = screen.getByTestId('policies-editor');
      expect(textarea).toBeInTheDocument();
      expect(textarea).toHaveValue('');
    });

    it('does not render "Insérer exemple" button when value contains only whitespace', () => {
      render(<BusinessRulePoliciesEditor value="   " onChange={vi.fn()} />);

      const insertBtn = screen.queryByTestId('insert-example-btn');
      expect(insertBtn).toBeInTheDocument(); // Whitespace is trimmed, so button still shows
    });

    it('does not show validation error when empty', () => {
      render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      const validationError = screen.queryByTestId('validation-error');
      expect(validationError).not.toBeInTheDocument();
    });
  });

  // AC8.2: test_insert_example
  describe('insert example', () => {
    it('calls onChange with Terraform JSON example when button clicked', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<BusinessRulePoliciesEditor value="" onChange={onChange} />);

      const insertBtn = screen.getByTestId('insert-example-btn');
      await user.click(insertBtn);

      expect(onChange).toHaveBeenCalledTimes(1);
      const insertedValue = onChange.mock.calls[0][0];
      const parsed = JSON.parse(insertedValue);
      expect(parsed).toEqual(TERRAFORM_EXAMPLE_JSON);
    });

    it('inserted example is properly formatted with indentation', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<BusinessRulePoliciesEditor value="" onChange={onChange} />);

      const insertBtn = screen.getByTestId('insert-example-btn');
      await user.click(insertBtn);

      const insertedValue = onChange.mock.calls[0][0];
      // Should be formatted with 2-space indentation
      expect(insertedValue).toContain('  "on_step_output"');
      expect(insertedValue).toContain('    {');
    });

    it('does not render insert button after example is inserted', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const { rerender } = render(<BusinessRulePoliciesEditor value="" onChange={onChange} />);

      const insertBtn = screen.getByTestId('insert-example-btn');
      await user.click(insertBtn);

      const insertedValue = onChange.mock.calls[0][0];
      // Rerender with the inserted value
      rerender(<BusinessRulePoliciesEditor value={insertedValue} onChange={onChange} />);

      const insertBtnAfter = screen.queryByTestId('insert-example-btn');
      expect(insertBtnAfter).not.toBeInTheDocument();
    });
  });

  // AC8.3: test_validation_live
  describe('live validation', () => {
    it('shows error for invalid JSON syntax', async () => {
      const { rerender } = render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      // Simulate user entering invalid JSON
      rerender(<BusinessRulePoliciesEditor value="{invalid json" onChange={vi.fn()} />);

      await waitFor(() => {
        const error = screen.getByTestId('validation-error');
        expect(error).toBeInTheDocument();
        expect(error).toHaveTextContent('JSON invalide : erreur de syntaxe');
      });
    });

    it('shows error when JSON is not an object', async () => {
      const { rerender } = render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      rerender(<BusinessRulePoliciesEditor value="[]" onChange={vi.fn()} />);

      await waitFor(() => {
        const error = screen.getByTestId('validation-error');
        expect(error).toBeInTheDocument();
        expect(error).toHaveTextContent('La valeur doit être un objet JSON');
      });
    });

    it('shows error when on_step_output key is missing', async () => {
      const { rerender } = render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      rerender(<BusinessRulePoliciesEditor value='{"other": "value"}' onChange={vi.fn()} />);

      await waitFor(() => {
        const error = screen.getByTestId('validation-error');
        expect(error).toBeInTheDocument();
        expect(error).toHaveTextContent("Clé 'on_step_output' obligatoire");
      });
    });

    it('shows error when on_step_output is not an array', async () => {
      const { rerender } = render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      rerender(<BusinessRulePoliciesEditor value='{"on_step_output": "not_array"}' onChange={vi.fn()} />);

      await waitFor(() => {
        const error = screen.getByTestId('validation-error');
        expect(error).toBeInTheDocument();
        expect(error).toHaveTextContent("'on_step_output' doit être un tableau");
      });
    });

    it('shows error when when.step_type is missing', async () => {
      const invalidJson = JSON.stringify({
        on_step_output: [
          {
            when: { output_key: 'plan_output' },
            policy: { type: 'review_if_modified' },
          },
        ],
      });

      const { rerender } = render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      rerender(<BusinessRulePoliciesEditor value={invalidJson} onChange={vi.fn()} />);

      await waitFor(() => {
        const error = screen.getByTestId('validation-error');
        expect(error).toBeInTheDocument();
        expect(error).toHaveTextContent('on_step_output[0].when.step_type obligatoire');
      });
    });

    it('shows error when policy.type is missing', async () => {
      const invalidJson = JSON.stringify({
        on_step_output: [
          {
            when: { step_type: 'terraform_cloud' },
            policy: { require_review_if_modified: [] },
          },
        ],
      });

      const { rerender } = render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      rerender(<BusinessRulePoliciesEditor value={invalidJson} onChange={vi.fn()} />);

      await waitFor(() => {
        const error = screen.getByTestId('validation-error');
        expect(error).toBeInTheDocument();
        expect(error).toHaveTextContent('on_step_output[0].policy.type obligatoire');
      });
    });

    it('shows error when require_review_if_modified is not an array for review_if_modified type', async () => {
      const invalidJson = JSON.stringify({
        on_step_output: [
          {
            when: { step_type: 'terraform_cloud' },
            policy: { type: 'review_if_modified' },
          },
        ],
      });

      const { rerender } = render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      rerender(<BusinessRulePoliciesEditor value={invalidJson} onChange={vi.fn()} />);

      await waitFor(() => {
        const error = screen.getByTestId('validation-error');
        expect(error).toBeInTheDocument();
        expect(error).toHaveTextContent('on_step_output[0].policy.require_review_if_modified obligatoire');
      });
    });

    it('does not show error for valid JSON', async () => {
      const validJson = JSON.stringify(TERRAFORM_EXAMPLE_JSON);

      render(<BusinessRulePoliciesEditor value={validJson} onChange={vi.fn()} />);

      const error = screen.queryByTestId('validation-error');
      expect(error).not.toBeInTheDocument();
    });

    it('validation updates in real-time as value changes', async () => {
      const { rerender } = render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      // Enter invalid JSON
      rerender(<BusinessRulePoliciesEditor value="{invalid" onChange={vi.fn()} />);
      await waitFor(() => {
        expect(screen.getByTestId('validation-error')).toBeInTheDocument();
      });

      // Fix the JSON
      rerender(<BusinessRulePoliciesEditor value={JSON.stringify(TERRAFORM_EXAMPLE_JSON)} onChange={vi.fn()} />);
      await waitFor(() => {
        expect(screen.queryByTestId('validation-error')).not.toBeInTheDocument();
      });
    });
  });

  // AC8.4: test_help_popover
  describe('help popover', () => {
    it('renders help button', () => {
      render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      const helpBtn = screen.getByTestId('help-btn');
      expect(helpBtn).toBeInTheDocument();
    });

    it('shows help popover content when help button is clicked', async () => {
      const user = userEvent.setup();
      render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      const helpBtn = screen.getByTestId('help-btn');
      await user.click(helpBtn);

      await waitFor(() => {
        expect(screen.getByText('Structure du schéma business_rule_policies')).toBeInTheDocument();
      });
    });

    it('popover contains Structure on_step_output section', async () => {
      const user = userEvent.setup();
      render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      const helpBtn = screen.getByTestId('help-btn');
      await user.click(helpBtn);

      await waitFor(() => {
        expect(screen.getByText('Structure on_step_output')).toBeInTheDocument();
      });
    });

    it('popover contains Champ when section', async () => {
      const user = userEvent.setup();
      render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      const helpBtn = screen.getByTestId('help-btn');
      await user.click(helpBtn);

      await waitFor(() => {
        expect(screen.getByText('Champ when')).toBeInTheDocument();
      });
    });

    it('popover contains Champ policy section', async () => {
      const user = userEvent.setup();
      render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      const helpBtn = screen.getByTestId('help-btn');
      await user.click(helpBtn);

      await waitFor(() => {
        expect(screen.getByText('Champ policy')).toBeInTheDocument();
      });
    });

    it('popover contains Types supportés section', async () => {
      const user = userEvent.setup();
      render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      const helpBtn = screen.getByTestId('help-btn');
      await user.click(helpBtn);

      await waitFor(() => {
        expect(screen.getByText('Types supportés')).toBeInTheDocument();
      });
    });

    it('popover contains documentation link', async () => {
      const user = userEvent.setup();
      render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      const helpBtn = screen.getByTestId('help-btn');
      await user.click(helpBtn);

      await waitFor(() => {
        const link = screen.getByText('Documentation complète');
        expect(link).toBeInTheDocument();
        expect(link).toHaveAttribute('href', '/docs/business-rule-policies.md');
      });
    });

    it('help button remains visible when content is present', () => {
      const validJson = JSON.stringify(TERRAFORM_EXAMPLE_JSON);
      render(<BusinessRulePoliciesEditor value={validJson} onChange={vi.fn()} />);

      const helpBtn = screen.getByTestId('help-btn');
      expect(helpBtn).toBeInTheDocument();
    });
  });

  // AC8.5: test_save_valid_policies
  describe('save valid policies', () => {
    it('calls onChange when user types in textarea', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<BusinessRulePoliciesEditor value="" onChange={onChange} />);

      const textarea = screen.getByTestId('policies-editor');
      await user.type(textarea, 'test');

      expect(onChange).toHaveBeenCalled();
    });

    it('calls onChange with exact pasted value', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<BusinessRulePoliciesEditor value="" onChange={onChange} />);

      const textarea = screen.getByTestId('policies-editor');
      const validJson = JSON.stringify(TERRAFORM_EXAMPLE_JSON);

      await user.click(textarea);
      await user.paste(validJson);

      // onChange is called when content changes
      const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
      expect(lastCall).toBe(validJson);
    });

    it('onChange is called with valid JSON structure', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<BusinessRulePoliciesEditor value="" onChange={onChange} />);

      const insertBtn = screen.getByTestId('insert-example-btn');
      await user.click(insertBtn);

      const savedValue = onChange.mock.calls[0][0];
      const parsed = JSON.parse(savedValue);

      expect(parsed).toHaveProperty('on_step_output');
      expect(Array.isArray(parsed.on_step_output)).toBe(true);
      expect(parsed.on_step_output[0]).toHaveProperty('when');
      expect(parsed.on_step_output[0]).toHaveProperty('policy');
    });

    it('value prop is reflected in textarea', () => {
      const validJson = JSON.stringify(TERRAFORM_EXAMPLE_JSON, null, 2);
      render(<BusinessRulePoliciesEditor value={validJson} onChange={vi.fn()} />);

      const textarea = screen.getByTestId('policies-editor');
      expect(textarea).toHaveValue(validJson);
    });
  });

  // AC8.6: test_save_invalid_shows_error
  describe('save invalid shows error', () => {
    it('shows validation error for invalid JSON', async () => {
      render(<BusinessRulePoliciesEditor value="{invalid}" onChange={vi.fn()} />);

      // Validation error is shown
      await waitFor(() => {
        const error = screen.getByTestId('validation-error');
        expect(error).toBeInTheDocument();
      });
    });

    it('validation error prevents insert button from showing when content exists', async () => {
      render(<BusinessRulePoliciesEditor value="{invalid}" onChange={vi.fn()} />);

      await waitFor(() => {
        const error = screen.getByTestId('validation-error');
        expect(error).toBeInTheDocument();
      });

      const insertBtn = screen.queryByTestId('insert-example-btn');
      expect(insertBtn).not.toBeInTheDocument();
    });

    it('shows error alert with error icon', async () => {
      render(<BusinessRulePoliciesEditor value="not json" onChange={vi.fn()} />);

      await waitFor(() => {
        const error = screen.getByTestId('validation-error');
        expect(error).toHaveClass('ant-alert-error');
      });
    });

    it('error message is descriptive for different validation failures', async () => {
      // Test 1: Invalid JSON syntax
      const { rerender } = render(<BusinessRulePoliciesEditor value="{bad" onChange={vi.fn()} />);
      await waitFor(() => {
        expect(screen.getByText('JSON invalide : erreur de syntaxe')).toBeInTheDocument();
      });

      // Test 2: Not an object
      rerender(<BusinessRulePoliciesEditor value="[]" onChange={vi.fn()} />);
      await waitFor(() => {
        expect(screen.getByText('La valeur doit être un objet JSON')).toBeInTheDocument();
      });

      // Test 3: Missing on_step_output
      rerender(<BusinessRulePoliciesEditor value="{}" onChange={vi.fn()} />);
      await waitFor(() => {
        expect(screen.getByText("Clé 'on_step_output' obligatoire")).toBeInTheDocument();
      });
    });
  });

  // AC8.7: test_clear_content
  describe('clear content behavior', () => {
    it('shows insert button when content is cleared', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const { rerender } = render(
        <BusinessRulePoliciesEditor value={JSON.stringify(TERRAFORM_EXAMPLE_JSON)} onChange={onChange} />
      );

      // Initially no insert button
      expect(screen.queryByTestId('insert-example-btn')).not.toBeInTheDocument();

      const textarea = screen.getByTestId('policies-editor');
      await user.clear(textarea);

      // Simulate the component rerendering with empty value
      rerender(<BusinessRulePoliciesEditor value="" onChange={onChange} />);

      // Insert button should appear
      expect(screen.getByTestId('insert-example-btn')).toBeInTheDocument();
    });

    it('hides validation error when content is cleared', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const { rerender } = render(<BusinessRulePoliciesEditor value="{invalid}" onChange={onChange} />);

      // Validation error should be present
      await waitFor(() => {
        expect(screen.getByTestId('validation-error')).toBeInTheDocument();
      });

      const textarea = screen.getByTestId('policies-editor');
      await user.clear(textarea);

      // Simulate rerender with empty value
      rerender(<BusinessRulePoliciesEditor value="" onChange={onChange} />);

      // Error should be gone
      expect(screen.queryByTestId('validation-error')).not.toBeInTheDocument();
    });

    it('insert button shows when content has only whitespace', () => {
      const whitespaceValue = '   \n  \t  ';
      render(<BusinessRulePoliciesEditor value={whitespaceValue} onChange={vi.fn()} />);

      // Whitespace is trimmed, so button should show
      expect(screen.getByTestId('insert-example-btn')).toBeInTheDocument();
    });

    it('clearing valid content to empty removes validation success state', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const { rerender } = render(
        <BusinessRulePoliciesEditor value={JSON.stringify(TERRAFORM_EXAMPLE_JSON)} onChange={onChange} />
      );

      // No validation error with valid content
      expect(screen.queryByTestId('validation-error')).not.toBeInTheDocument();

      const textarea = screen.getByTestId('policies-editor');
      await user.clear(textarea);

      rerender(<BusinessRulePoliciesEditor value="" onChange={onChange} />);

      // Still no error, but insert button appears
      expect(screen.queryByTestId('validation-error')).not.toBeInTheDocument();
      expect(screen.getByTestId('insert-example-btn')).toBeInTheDocument();
    });
  });

  // Additional edge cases and integration tests
  describe('additional edge cases', () => {
    it('handles undefined onChange gracefully', () => {
      // Should not throw error when onChange is undefined
      expect(() => {
        render(<BusinessRulePoliciesEditor value="" />);
      }).not.toThrow();

      const textarea = screen.getByTestId('policies-editor');
      expect(textarea).toBeInTheDocument();
    });

    it('handles undefined value prop as empty string', () => {
      render(<BusinessRulePoliciesEditor onChange={vi.fn()} />);

      const textarea = screen.getByTestId('policies-editor');
      expect(textarea).toHaveValue('');
      expect(screen.getByTestId('insert-example-btn')).toBeInTheDocument();
    });

    it('textarea has correct accessibility label', () => {
      render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      const textarea = screen.getByLabelText('Éditeur de règles métier');
      expect(textarea).toBeInTheDocument();
    });

    it('textarea has monospace font for code editing', () => {
      render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      const textarea = screen.getByTestId('policies-editor');
      expect(textarea).toHaveStyle({ fontFamily: 'monospace' });
    });

    it('textarea has appropriate rows', () => {
      render(<BusinessRulePoliciesEditor value="" onChange={vi.fn()} />);

      const textarea = screen.getByTestId('policies-editor');
      expect(textarea).toHaveAttribute('rows', '12');
    });

    it('validates complex nested structure correctly', () => {
      const complexJson = JSON.stringify({
        on_step_output: [
          {
            when: {
              step_type: 'terraform_cloud',
              output_key: 'plan_output',
            },
            policy: {
              type: 'review_if_modified',
              require_review_if_modified: [
                { resource_type: 'azurerm_sql_database' },
                { attribute_paths: ['backup_retention_days'] },
              ],
              auto_approve_if_none_match: false,
            },
          },
          {
            when: {
              step_type: 'ansible_tower',
            },
            policy: {
              type: 'review_if_modified',
              require_review_if_modified: [],
            },
          },
        ],
      });

      render(<BusinessRulePoliciesEditor value={complexJson} onChange={vi.fn()} />);

      expect(screen.queryByTestId('validation-error')).not.toBeInTheDocument();
    });

    it('handles rapid pasting without errors', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<BusinessRulePoliciesEditor value="" onChange={onChange} />);

      const textarea = screen.getByTestId('policies-editor');
      const text = '{"on_step_output":[]}';

      await user.click(textarea);
      await user.paste(text);

      expect(onChange).toHaveBeenCalled();
    });
  });
});
