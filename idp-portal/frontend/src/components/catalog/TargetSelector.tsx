/**
 * TargetSelector - Select one or multiple targets from inventory (Story 13.2, Task 1).
 *
 * Features:
 * - Fetches targets from GET /api/v1/inventory/targets (RBAC filtered)
 * - Supports single or multiple selection mode
 * - Groups targets by environment in dropdown
 * - Displays environment as sub-label for each target
 * - Server-side search: refetches with search param on debounced input (code-review fix)
 * - Derives environment from selected targets
 */

import { useCallback, useMemo, useState } from 'react';
import { Select, Badge, Alert, Spin, Empty } from 'antd';
import type { SelectProps, RefSelectProps } from 'antd';

import { useTargetsPaginated } from '../../hooks/useTargetInventory';
import type { InventoryTarget } from '../../hooks/useTargetInventory';
import { useDebounce } from '../../hooks/useDebounce';
import { getEnvironmentLabel, getEnvironmentColor, sortEnvironments } from '../../utils/environmentHelpers';

/** Target from inventory API */
export type Target = InventoryTarget;

export interface TargetSelectorProps {
  /** Whether to allow multiple target selection */
  multiple?: boolean;
  /** Currently selected targets */
  value: Target[];
  /** Callback when selection changes */
  onChange: (targets: Target[]) => void;
  /** Whether the selector is disabled */
  disabled?: boolean;
  /** Placeholder text */
  placeholder?: string;
  /** Accessible label */
  ariaLabel?: string;
  /** Ref to focus element */
  inputRef?: React.Ref<RefSelectProps>;
}

export function TargetSelector({
  multiple = false,
  value,
  onChange,
  disabled = false,
  placeholder = 'Selectionnez une cible',
  ariaLabel = 'Selection de cible',
  inputRef,
}: TargetSelectorProps) {
  const [searchValue, setSearchValue] = useState('');
  const debouncedSearch = useDebounce(searchValue.trim(), 300);
  const { targets, loading, error } = useTargetsPaginated(debouncedSearch || undefined);

  // Group targets by environment for dropdown display
  const groupedOptions = useMemo((): NonNullable<SelectProps['options']> => {
    // Group by environment
    const groups: Record<string, Target[]> = {};
    for (const target of targets) {
      const env = target.environment || 'unknown';
      if (!groups[env]) {
        groups[env] = [];
      }
      groups[env].push(target);
    }

    // Convert to Ant Design options with groups
    const orderedEnvs = sortEnvironments(Object.keys(groups));

    return orderedEnvs.map((env) => ({
      label: (
        <span style={{ fontWeight: 600 }}>
          {getEnvironmentLabel(env)}
        </span>
      ),
      options: groups[env].map((target) => ({
        value: target.name,
        label: (
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>{target.name}</span>
            <Badge
              status={getEnvironmentColor(target.environment)}
              text={
                <span style={{ fontSize: 11, color: '#8c8c8c' }}>
                  ({getEnvironmentLabel(target.environment ?? '')})
                </span>
              }
            />
          </span>
        ),
        // Store full target object for retrieval
        target,
      })),
    }));
  }, [targets]);

  // Handle selection change (resolve names from current targets or from existing value when not in list)
  const handleChange = useCallback(
    (selectedValues: string | string[]) => {
      const values = Array.isArray(selectedValues) ? selectedValues : [selectedValues].filter(Boolean);
      const selectedTargets: Target[] = [];

      for (const name of values) {
        const target = targets.find((t) => t.name === name) ?? value.find((t) => t.name === name);
        if (target) {
          selectedTargets.push(target);
        }
      }

      onChange(selectedTargets);
    },
    [targets, value, onChange]
  );

  // Handle search (server-side via debounced effect above; no client-side filter)
  const handleSearch = useCallback((searchText: string) => {
    setSearchValue(searchText);
  }, []);

  // Get current selected values for the Select
  const selectedValues = useMemo(() => {
    return value.map((t) => t.name);
  }, [value]);

  if (error) {
    return (
      <Alert
        type="error"
        showIcon
        title="Erreur"
        description={error}
        style={{ marginBottom: 16 }}
      />
    );
  }

  return (
    <Select<string | string[]>
      ref={inputRef}
      mode={multiple ? 'multiple' : undefined}
      value={multiple ? selectedValues : selectedValues[0]}
      onChange={handleChange}
      onSearch={handleSearch}
      searchValue={searchValue}
      placeholder={placeholder}
      aria-label={ariaLabel}
      disabled={disabled}
      loading={loading}
      showSearch
      filterOption={false}
      options={groupedOptions}
      style={{ width: '100%' }}
      notFoundContent={
        loading ? (
          <Spin size="small" />
        ) : targets.length === 0 ? (
          <Empty
            description="Aucune cible disponible"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        ) : null
      }
      listHeight={300}
      virtual
      maxTagCount="responsive"
    />
  );
}

export default TargetSelector;
