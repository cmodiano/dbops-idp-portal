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

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Select, Badge, Alert, Spin, Empty } from 'antd';
import type { SelectProps } from 'antd';

import { apiFetchRaw } from '../../services/api_client';
import { useDebounce } from '../../hooks/useDebounce';
import { getEnvironmentLabel, getEnvironmentColor, sortEnvironments } from '../../utils/environmentHelpers';

/** Target from inventory API */
export interface Target {
  name: string;
  environment: string;
  target_type: string;
  metadata: Record<string, unknown> | null;
}

/** Response from GET /api/v1/inventory/targets */
interface TargetsResponse {
  items: Target[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

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
  inputRef?: React.Ref<HTMLElement>;
}

/**
 * Fetch targets from inventory API.
 *
 * @param search Optional search query
 * @returns Promise with targets response
 */
async function fetchTargets(search?: string): Promise<TargetsResponse> {
  const params = new URLSearchParams();
  params.set('page', '1');
  params.set('page_size', '100'); // Load enough for dropdown
  if (search) {
    params.set('search', search);
  }

  // Inventory API returns { items, total, page, ... } directly (no data wrapper)
  return apiFetchRaw<TargetsResponse>(`/inventory/targets?${params.toString()}`);
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
  const [targets, setTargets] = useState<Target[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchValue, setSearchValue] = useState('');
  const debouncedSearch = useDebounce(searchValue.trim(), 300);

  // Load targets: initial load and when server-side search term changes
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchTargets(debouncedSearch || undefined)
      .then((response) => {
        if (!cancelled) {
          setTargets(response?.items ?? []);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message || 'Erreur lors du chargement des cibles');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [debouncedSearch]);

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
                  ({target.environment})
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
        message="Erreur"
        description={error}
        style={{ marginBottom: 16 }}
      />
    );
  }

  return (
    <Select
      ref={inputRef as React.Ref<any>}
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
