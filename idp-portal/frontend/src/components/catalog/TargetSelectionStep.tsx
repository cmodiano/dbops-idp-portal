/**
 * TargetSelectionStep - Step 1 of the execution wizard.
 * Story 17.2, Task 4.1.
 *
 * Handles target selection (list, pattern, manual) or environment selection (fallback).
 */

import { memo, useMemo, useRef } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import {
  Form,
  Select,
  Input,
  Alert,
  Badge,
  Radio,
  Typography,
} from 'antd';
import { WarningOutlined, LoadingOutlined } from '@ant-design/icons';
import type { CatalogActionDetail } from '../../services/catalog_service';
import type { ExecutionEnvironment, InventoryItem } from '../../types/api';
import { ImpactIndicator } from '../shared/ImpactIndicator';
import { TargetSelector, type Target } from './TargetSelector';
import { getEnvironmentLabel, isProductionEnvironment } from '../../utils/environmentHelpers';

const { Text } = Typography;

/**
 * Check if environment ID is allowed (case-insensitive).
 * Story 21.5: Optimizes repeated toUpperCase() calls in filtering logic.
 */
function isEnvironmentAllowed(envId: string, allowedEnvironments: string[]): boolean {
  return allowedEnvironments.includes(envId) || allowedEnvironments.includes(envId.toUpperCase());
}

export interface TargetSelectionStepProps {
  action: CatalogActionDetail;
  allowedEnvironments: string[];
  selectedTargets: Target[];
  onTargetsChange: (targets: Target[]) => void;
  targetInputMode: 'list' | 'pattern' | 'manual';
  onTargetInputModeChange: (mode: 'list' | 'pattern' | 'manual') => void;
  targetPattern: string;
  onTargetPatternChange: (pattern: string) => void;
  manualTargetInput: string;
  onManualTargetInputChange: (input: string) => void;
  selectedEnvironment: ExecutionEnvironment | null;
  onEnvironmentChange: (env: ExecutionEnvironment) => void;
  derivedEnvironment: ExecutionEnvironment | null;
  hasMixedEnvironments: boolean;
  currentImpact: import('../../types/api').ImpactLevel | null;
  environmentsCache: InventoryItem[] | null;
  inventoryWarnings: Record<string, boolean>;
  resolvedPatternTargets: Array<{ name: string; environment: string }>;
  patternResolving: boolean;
}

import { STEP_DESCRIPTIONS_SIMPLIFIED } from '../../utils/stepDescriptions';

export const TargetSelectionStep = memo(function TargetSelectionStep({
  action,
  allowedEnvironments,
  selectedTargets,
  onTargetsChange,
  targetInputMode,
  onTargetInputModeChange,
  targetPattern,
  onTargetPatternChange,
  manualTargetInput,
  onManualTargetInputChange,
  selectedEnvironment,
  onEnvironmentChange,
  derivedEnvironment,
  hasMixedEnvironments,
  currentImpact,
  environmentsCache,
  inventoryWarnings,
  resolvedPatternTargets,
  patternResolving,
}: TargetSelectionStepProps) {
  const firstFieldRef = useRef<HTMLElement | null>(null);
  const { isBusinessProfile } = useAuth();
  const requiresTarget = action?.requires_target !== false;

  const manualTargetCount = useMemo(() => {
    return manualTargetInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean).length;
  }, [manualTargetInput]);

  return (
    <div>
      {isBusinessProfile && (
        <Alert
          type="info"
          showIcon
          description={STEP_DESCRIPTIONS_SIMPLIFIED[0]}
          style={{ marginBottom: 16 }}
        />
      )}

      {requiresTarget ? (
        <>
          <Form.Item
            label={isBusinessProfile ? 'Mode de selection' : 'Comment choisir les cibles?'}
            required
          >
            <Radio.Group
              value={targetInputMode}
              onChange={(e) => onTargetInputModeChange(e.target.value)}
              optionType="button"
              buttonStyle="solid"
            >
              <Radio.Button value="list">Liste</Radio.Button>
              <Radio.Button value="pattern">Pattern</Radio.Button>
              <Radio.Button value="manual">Saisie manuelle</Radio.Button>
            </Radio.Group>
          </Form.Item>

          {targetInputMode === 'list' && (
            <Form.Item
              label="Cible(s)"
              required
              tooltip={isBusinessProfile ? undefined : 'Selectionnez une ou plusieurs cibles dans la liste.'}
            >
              <TargetSelector
                inputRef={firstFieldRef as React.Ref<HTMLElement>}
                multiple
                value={selectedTargets}
                onChange={onTargetsChange}
                placeholder="Selectionnez une ou plusieurs cibles"
                ariaLabel="Selection de cibles"
              />
            </Form.Item>
          )}

          {targetInputMode === 'pattern' && (
            <Form.Item
              label="Pattern"
              required
              tooltip="Utilisez * pour tout correspondre et ? pour un caractere (ex: srv-dev-*, assurance-*)"
            >
              <Input
                ref={firstFieldRef as React.Ref<HTMLInputElement>}
                value={targetPattern}
                onChange={(e) => onTargetPatternChange(e.target.value)}
                placeholder="ex: srv-dev-* ou assurance-*"
                aria-label="Pattern de cibles"
                suffix={patternResolving ? <LoadingOutlined spin /> : null}
              />
              {targetPattern && !patternResolving && (
                <Text type="secondary" style={{ fontSize: 12, marginTop: 4, display: 'block' }}>
                  {resolvedPatternTargets.length} cible(s) correspondante(s)
                  {resolvedPatternTargets.length > 0 && `: ${resolvedPatternTargets.map((t) => t.name).slice(0, 5).join(', ')}${resolvedPatternTargets.length > 5 ? '...' : ''}`}
                </Text>
              )}
            </Form.Item>
          )}

          {targetInputMode === 'manual' && (
            <Form.Item
              label="Cibles (séparees par des virgules)"
              required
              tooltip="Entrez les noms des cibles, separes par des virgules (ex: srv-01, srv-02, srv-03)"
            >
              <Input.TextArea
                ref={firstFieldRef as React.Ref<HTMLTextAreaElement>}
                value={manualTargetInput}
                onChange={(e) => onManualTargetInputChange(e.target.value)}
                placeholder="ex: srv-dev-01, srv-dev-02, srv-dev-03"
                aria-label="Liste des cibles"
                rows={3}
              />
              {manualTargetInput && (
                <Text type="secondary" style={{ fontSize: 12, marginTop: 4, display: 'block' }}>
                  {manualTargetCount} cible(s) detectee(s)
                </Text>
              )}
            </Form.Item>
          )}

          {hasMixedEnvironments && (
            <Alert
              type="warning"
              showIcon
              icon={<WarningOutlined />}
              message="Attention"
              description="Les cibles selectionnees appartiennent a des environnements differents. Cela peut causer des problemes."
              style={{ marginBottom: 16 }}
            />
          )}

          {derivedEnvironment && (
            <Alert
              type="info"
              showIcon
              description={`Environnement derive : ${getEnvironmentLabel(derivedEnvironment)}`}
              style={{ marginBottom: 16 }}
            />
          )}
        </>
      ) : (
        <>
          <Form.Item
            label={isBusinessProfile ? 'Environnement' : 'Environnement cible'}
            required
            tooltip={isBusinessProfile ? undefined : 'Selectionnez l\'environnement sur lequel executer l\'action.'}
          >
            <Select
              ref={(ref) => {
                firstFieldRef.current = ref as unknown as HTMLElement;
              }}
              value={selectedEnvironment ?? undefined}
              onChange={onEnvironmentChange}
              placeholder={
                environmentsCache === null
                  ? 'Chargement...'
                  : environmentsCache.length === 0
                    ? 'Aucun environnement disponible'
                    : 'Selectionnez un environnement'
              }
              aria-label="Environnement cible"
              style={{ width: '100%' }}
              loading={environmentsCache === null}
              disabled={environmentsCache !== null && environmentsCache.filter((env) => isEnvironmentAllowed(env.id, allowedEnvironments)).length === 0}
              options={
                environmentsCache && environmentsCache.length > 0
                  ? environmentsCache
                      .filter((env) => isEnvironmentAllowed(env.id, allowedEnvironments))
                      .map((env) => ({
                        value: env.id,
                        label: env.name,
                        disabled: false,
                      }))
                  : []
              }
            />
          </Form.Item>

          {inventoryWarnings.environments && (
            <Badge
              status="warning"
              text="Données inventaire temporairement indisponibles — dernières valeurs en cache"
              style={{
                marginBottom: 8,
                fontSize: '12px',
                color: '#faad14',
                display: 'block',
              }}
            />
          )}

          {allowedEnvironments.length === 1 && selectedEnvironment && (
            <Alert
              type="success"
              showIcon
              description="Environnement selectionne automatiquement car c'est le seul disponible pour vous."
              style={{ marginBottom: 16 }}
            />
          )}
        </>
      )}

      {derivedEnvironment && isProductionEnvironment(derivedEnvironment) && (
        <Alert
          message="Avertissement - Environnement Production"
          description="Vous etes sur le point d'executer une action en production. Verifiez attentivement les parametres."
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          style={{ marginBottom: 16 }}
        />
      )}

      {currentImpact !== null && (
        <div style={{ marginTop: 16 }}>
          <Text strong>Niveau d'impact: </Text>
          <ImpactIndicator level={currentImpact} />
        </div>
      )}
    </div>
  );
});
