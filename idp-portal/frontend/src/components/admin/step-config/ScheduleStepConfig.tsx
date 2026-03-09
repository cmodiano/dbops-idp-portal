/**
 * ScheduleStepConfig — Configuration pour les steps de type schedule_execution (Story 57.16).
 *
 * Affiche : sélection de l'action cible, source de date (parameter/fixed_offset/recurring),
 * champs conditionnels selon la source, inherit_parameters, inherit_targets, parameter_mapping.
 */
import type { FC } from 'react';
import { Input, Select, Switch, Typography, Divider } from 'antd';
import type { WorkflowStepNodeData } from '../WorkflowStepNode';
import { KeyValueEditor } from './KeyValueEditor';
import type { ScheduleStepConfig as ScheduleStepConfigType } from '../../../types/api/catalog';

const { Text } = Typography;

export interface ScheduleStepConfigProps {
  data: WorkflowStepNodeData;
  onUpdate: (updates: Partial<WorkflowStepNodeData>) => void;
  disabled?: boolean;
}

const SCHEDULE_SOURCE_OPTIONS = [
  { value: 'parameter', label: 'Paramètre utilisateur (date choisie au lancement)' },
  { value: 'fixed_offset', label: 'Offset fixe (relatif à maintenant)' },
  { value: 'recurring', label: 'Pattern récurrent' },
];

const RECURRING_PATTERN_TYPE_OPTIONS = [
  { value: 'daily', label: 'Quotidien' },
  { value: 'weekly', label: 'Hebdomadaire' },
  { value: 'cron', label: 'Cron expression' },
];

/** Format accepté par le backend: +Nd, +Nh, +Nw, +Nm (ex: +3d, +6h, +1w, +30m) */
const FIXED_OFFSET_PATTERN = /^[+-]\d+[dhwm]$/;

/** Helper pour mettre à jour schedule_config partiellement */
function updateScheduleConfig(
  current: ScheduleStepConfigType | null | undefined,
  patch: Partial<ScheduleStepConfigType>,
): ScheduleStepConfigType {
  const base: ScheduleStepConfigType = current ?? { schedule_source: 'parameter' };
  return { ...base, ...patch };
}

export const ScheduleStepConfig: FC<ScheduleStepConfigProps> = ({
  data,
  onUpdate,
  disabled = false,
}) => {
  const config = data.schedule_config ?? null;
  const scheduleSource = config?.schedule_source ?? 'parameter';

  const handleConfigUpdate = (patch: Partial<ScheduleStepConfigType>) => {
    onUpdate({ schedule_config: updateScheduleConfig(config, patch) });
  };

  return (
    <div data-testid="schedule-step-config">

      {/* Action cible (referenced_action_id) */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          ID de l'action cible <Text type="danger">*</Text>
        </Text>
        <Input
          size="small"
          value={data.action_id != null ? String(data.action_id) : ''}
          onChange={(e) => {
            const val = e.target.value;
            onUpdate({ action_id: val ? Number(val) : null });
          }}
          placeholder="ID numérique de l'action à planifier"
          disabled={disabled}
          aria-label="ID de l'action cible"
          type="number"
        />
      </div>

      <Divider style={{ margin: '8px 0' }} />

      {/* Source de la date */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          Source de la date <Text type="danger">*</Text>
        </Text>
        <Select
          style={{ width: '100%' }}
          size="small"
          value={scheduleSource}
          onChange={(value) =>
            handleConfigUpdate({
              schedule_source: value,
              // Reset champs conditionnels lors du changement de source
              schedule_parameter_name: value !== 'parameter' ? undefined : config?.schedule_parameter_name,
              fixed_offset: value !== 'fixed_offset' ? undefined : config?.fixed_offset,
              recurring_pattern: value !== 'recurring' ? undefined : config?.recurring_pattern,
            })
          }
          placeholder="Sélectionner la source"
          disabled={disabled}
          aria-label="Source de la date de planification"
          options={SCHEDULE_SOURCE_OPTIONS}
        />
      </div>

      {/* Champs conditionnels selon schedule_source */}

      {/* Mode: parameter */}
      {scheduleSource === 'parameter' && (
        <div style={{ marginBottom: 12 }}>
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
            Nom du paramètre de date <Text type="danger">*</Text>
          </Text>
          <Input
            size="small"
            value={config?.schedule_parameter_name ?? ''}
            onChange={(e) =>
              handleConfigUpdate({ schedule_parameter_name: e.target.value || undefined })
            }
            placeholder="ex: maintenance_scheduled_at"
            disabled={disabled}
            aria-label="Nom du paramètre de date"
          />
          <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
            Paramètre rempli par l'utilisateur au lancement du workflow (format ISO 8601)
          </Text>
        </div>
      )}

      {/* Mode: fixed_offset */}
      {scheduleSource === 'fixed_offset' && (
        <div style={{ marginBottom: 12 }}>
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
            Délai relatif (offset) <Text type="danger">*</Text>
          </Text>
          <Input
            size="small"
            value={config?.fixed_offset ?? ''}
            onChange={(e) =>
              handleConfigUpdate({ fixed_offset: e.target.value || undefined })
            }
            placeholder="ex: +3d, +6h, +1w, +30m"
            disabled={disabled}
            aria-label="Offset fixe"
            status={config?.fixed_offset && !FIXED_OFFSET_PATTERN.test(config.fixed_offset) ? 'error' : undefined}
          />
          {config?.fixed_offset && !FIXED_OFFSET_PATTERN.test(config.fixed_offset) && (
            <Text type="danger" style={{ fontSize: 11, marginTop: 4, display: 'block' }} role="alert">
              Format invalide — attendu : +Nd, +Nh, +Nw, +Nm (ex: +3d, +6h)
            </Text>
          )}
          <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
            Formats : +Nd (jours), +Nh (heures), +Nw (semaines), +Nm (minutes)
          </Text>
        </div>
      )}

      {/* Mode: recurring */}
      {scheduleSource === 'recurring' && (
        <div style={{ marginBottom: 12 }}>
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
            Type de pattern récurrent <Text type="danger">*</Text>
          </Text>
          <Select
            style={{ width: '100%' }}
            size="small"
            value={config?.recurring_pattern?.pattern_type ?? undefined}
            onChange={(value) =>
              handleConfigUpdate({
                recurring_pattern: {
                  pattern_type: value,
                  pattern_config: config?.recurring_pattern?.pattern_config ?? {},
                },
              })
            }
            placeholder="Sélectionner le type de récurrence"
            disabled={disabled}
            aria-label="Type de pattern récurrent"
            options={RECURRING_PATTERN_TYPE_OPTIONS}
          />
        </div>
      )}

      <Divider style={{ margin: '8px 0' }} />

      {/* inherit_parameters */}
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Switch
          checked={config?.inherit_parameters ?? false}
          onChange={(checked) => handleConfigUpdate({ inherit_parameters: checked || undefined })} // false → undefined (backend default=false)
          disabled={disabled}
          size="small"
          aria-label="Hériter les paramètres"
        />
        <Text type="secondary" style={{ fontSize: 12 }}>
          Hériter les paramètres de l'exécution courante
        </Text>
      </div>

      {/* inherit_targets */}
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Switch
          checked={config?.inherit_targets ?? false}
          onChange={(checked) => handleConfigUpdate({ inherit_targets: checked || undefined })} // false → undefined (backend default=false)
          disabled={disabled}
          size="small"
          aria-label="Hériter les targets"
        />
        <Text type="secondary" style={{ fontSize: 12 }}>
          Hériter les targets (serveurs/instances) de l'exécution courante
        </Text>
      </div>

      <Divider style={{ margin: '8px 0' }} />

      {/* parameter_mapping */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          Mapping de paramètres (optionnel)
        </Text>
        <KeyValueEditor
          value={config?.parameter_mapping ?? {}}
          onChange={(mapping) =>
            handleConfigUpdate({ parameter_mapping: Object.keys(mapping).length > 0 ? mapping : undefined })
          }
          disabled={disabled}
          keyPlaceholder="Param cible"
          valuePlaceholder="Valeur ou JSONPath ($.steps.X.output.Y)"
        />
        <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
          Valeur statique ou JSONPath : $.steps.&lt;step_id&gt;.output.&lt;champ&gt;
        </Text>
      </div>
    </div>
  );
};

export default ScheduleStepConfig;
