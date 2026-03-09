/**
 * ParametersEditor component for managing action parameters visually (Story 2.17, AC #1, #2, #3, #6).
 *
 * Features:
 * - List of parameters with "Ajouter un parametre" button (AC1)
 * - Inline form per parameter: name, type, required, default, description (AC2)
 * - Drag-and-drop reorder via @dnd-kit (AC3), same pattern as StepsEditor
 * - Delete (X) per parameter; inline validation: name required, name unique, type required (AC6)
 */

import type { FC, CSSProperties } from 'react';
import {
  Button,
  Input,
  Select,
  Space,
  Card,
  Typography,
  Form,
  theme,
  Switch,
  Tooltip,
} from 'antd';
import { PlusOutlined, DeleteOutlined, HolderOutlined, InfoCircleOutlined } from '@ant-design/icons';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { ParameterDefinition, ParameterSchemaType, InventorySourceType, InventorySchema } from '../../types/api';
import { useInventorySchema } from '../../hooks/useInventorySchema';

const { Text } = Typography;

const EMPTY_PARAMS: ParameterDefinition[] = [];

export interface ParametersEditorProps {
  value?: ParameterDefinition[];
  onChange?: (value: ParameterDefinition[]) => void;
}

const PARAM_TYPE_OPTIONS: { value: ParameterSchemaType; label: string }[] = [
  { value: 'string', label: 'Texte (string)' },
  { value: 'number', label: 'Nombre (number)' },
  { value: 'integer', label: 'Entier (integer)' },
  { value: 'boolean', label: 'Booleen (boolean)' },
  { value: 'date', label: 'Date (date)' },
  { value: 'date-time', label: 'Date-heure (date-time)' },
  { value: 'select', label: 'Liste (select)' },
];

/** Story 23.5: Source options for parameter value origin. */
const SOURCE_OPTIONS: { value: 'manual' | 'inventory'; label: string }[] = [
  { value: 'manual', label: 'Saisie manuelle' },
  { value: 'inventory', label: 'Inventaire' },
];

/** Story 23.5: Inventory entity type options. */
const INVENTORY_TYPE_OPTIONS: { value: InventorySourceType; label: string }[] = [
  { value: 'servers', label: 'Serveurs' },
  { value: 'instances', label: 'Instances' },
  { value: 'databases', label: 'Bases de données' },
];

/** Story 37.5: Allowed value columns per inventory type. Mirrors VALID_INVENTORY_VALUE_COLUMNS in catalog/serializers.py. */
const INVENTORY_VALUE_COLUMN_OPTIONS: Record<InventorySourceType, { value: string; label: string }[]> = {
  servers:   [{ value: 'name', label: 'name' }, { value: 'id', label: 'id' }, { value: 'environment', label: 'environment' }, { value: 'engine_type', label: 'engine_type' }],
  instances: [{ value: 'name', label: 'name' }, { value: 'id', label: 'id' }, { value: 'server_ref', label: 'server_ref' }, { value: 'db_ref', label: 'db_ref' }],
  databases: [{ value: 'name', label: 'name' }, { value: 'id', label: 'id' }],
};

interface SortableParamCardProps {
  param: ParameterDefinition;
  index: number;
  allParams: ParameterDefinition[];
  onParamChange: (index: number, field: keyof ParameterDefinition, fieldValue: unknown) => void;
  onRemove: (index: number) => void;
  inventorySchema: InventorySchema | null;  // Story 62.5
  inventorySchemaLoading: boolean;          // Story 62.5
}

const SortableParamCard: FC<SortableParamCardProps> = ({
  param,
  index,
  allParams,
  onParamChange,
  onRemove,
  inventorySchema,
  inventorySchemaLoading,
}) => {
  const { token } = theme.useToken();
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: param.id ?? `param-${index}` });

  const duplicateName =
    param.name.trim() !== '' &&
    allParams.filter((p, i) => i !== index && (p.name || '').trim() === param.name.trim()).length > 0;

  const style: CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    marginBottom: 8,
  };

  return (
    <Card
      ref={setNodeRef}
      style={style}
      size="small"
      styles={{ body: { padding: '12px' } }}
    >
      <Space orientation="vertical" style={{ width: '100%' }} size="small">
        <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <HolderOutlined
              {...attributes}
              {...listeners}
              style={{
                cursor: isDragging ? 'grabbing' : 'grab',
                color: token.colorTextTertiary,
                touchAction: 'none',
              }}
              aria-label={`Glisser pour reordonner parametre ${index + 1}`}
            />
            <Text strong>Parametre {index + 1}</Text>
          </Space>
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => onRemove(index)}
            aria-label={`Supprimer parametre ${index + 1}`}
          />
        </Space>

        <Space wrap style={{ width: '100%' }} size="small">
          <Form.Item
            label="Nom"
            validateStatus={!param.name?.trim() ? 'error' : duplicateName ? 'error' : ''}
            help={
              !param.name?.trim()
                ? 'Nom requis'
                : duplicateName
                  ? 'Nom unique requis'
                  : ''
            }
            style={{ marginBottom: 0 }}
          >
            <Input
              value={param.name}
              onChange={(e) => onParamChange(index, 'name', e.target.value)}
              placeholder="Ex: pdb_name"
              style={{ width: 180 }}
              aria-label={`Nom parametre ${index + 1}`}
            />
          </Form.Item>

          <Form.Item label="Type" style={{ marginBottom: 0 }}>
            <Select
              value={param.type}
              onChange={(v) => onParamChange(index, 'type', v)}
              options={PARAM_TYPE_OPTIONS}
              style={{ width: 180 }}
              aria-label={`Type parametre ${index + 1}`}
            />
          </Form.Item>

          <Form.Item label="Requis" style={{ marginBottom: 0 }}>
            <Switch
              checked={param.required}
              onChange={(v) => onParamChange(index, 'required', v)}
              aria-label={`Parametre ${index + 1} requis`}
            />
          </Form.Item>

          <Form.Item label="Valeur par defaut" style={{ marginBottom: 0 }}>
            <Input
              value={param.default ?? ''}
              onChange={(e) => onParamChange(index, 'default', e.target.value || undefined)}
              placeholder="Optionnel"
              style={{ width: 160 }}
              aria-label={`Valeur par defaut parametre ${index + 1}`}
            />
          </Form.Item>
        </Space>

        <Form.Item label="Description" style={{ marginBottom: 0 }}>
          <Input
            value={param.description ?? ''}
            onChange={(e) => onParamChange(index, 'description', e.target.value || undefined)}
            placeholder="Description optionnelle"
            style={{ width: '100%' }}
            aria-label={`Description parametre ${index + 1}`}
          />
        </Form.Item>

        {param.type === 'select' && (
          <Form.Item label="Options (enum)" style={{ marginBottom: 0 }}>
            <Select
              mode="tags"
              value={param.enum ?? []}
              onChange={(v) => onParamChange(index, 'enum', v)}
              placeholder="Saisir une option puis Entree"
              style={{ minWidth: 200 }}
              tokenSeparators={[',']}
              aria-label={`Options liste parametre ${index + 1}`}
            />
          </Form.Item>
        )}

        {/* Story 23.5: Source and inventory_type fields */}
        <Space wrap style={{ width: '100%' }} size="small">
          <Form.Item
            label={
              <span>
                Source{' '}
                <Tooltip title="La source détermine comment la valeur sera fournie : saisie manuelle ou sélection depuis l'inventaire">
                  <InfoCircleOutlined style={{ color: 'rgba(0,0,0,0.45)' }} />
                </Tooltip>
              </span>
            }
            style={{ marginBottom: 0 }}
          >
            <Select
              value={param.source ?? 'manual'}
              onChange={(v) => onParamChange(index, 'source', v)}
              options={SOURCE_OPTIONS}
              style={{ width: 180 }}
              placeholder="Choisir la source"
              aria-label={`Source parametre ${index + 1}`}
            />
          </Form.Item>

          {(param.source === 'inventory') && (
            <Form.Item
              label={
                <span>
                  Type d&apos;inventaire{' '}
                  <Tooltip title="Serveurs : liste des serveurs filtrés par environnement. Instances : liste des instances liées au serveur sélectionné. Bases de données : liste des bases de données liées au serveur sélectionné.">
                    <InfoCircleOutlined style={{ color: 'rgba(0,0,0,0.45)' }} />
                  </Tooltip>
                </span>
              }
              validateStatus={param.source === 'inventory' && !param.inventory_type ? 'error' : ''}
              help={param.source === 'inventory' && !param.inventory_type ? "Le type d'inventaire est requis quand la source est 'Inventaire'" : ''}
              style={{ marginBottom: 0 }}
            >
              <Select
                value={param.inventory_type}
                onChange={(v) => onParamChange(index, 'inventory_type', v)}
                options={INVENTORY_TYPE_OPTIONS}
                style={{ width: 200 }}
                placeholder="Choisir le type d'entite"
                aria-label={`Type inventaire parametre ${index + 1}`}
              />
            </Form.Item>
          )}

          {(param.source === 'inventory' && param.inventory_type) && (
            <Form.Item
              label={
                <span>
                  Colonne valeur{' '}
                  <Tooltip title="Colonne de l'entité inventaire utilisée comme valeur et libellé du paramètre (défaut : name → id/name selon comportement actuel).">
                    <InfoCircleOutlined style={{ color: 'rgba(0,0,0,0.45)' }} />
                  </Tooltip>
                </span>
              }
              style={{ marginBottom: 0 }}
            >
              <Select
                value={param.inventory_value_column}
                onChange={(v) => onParamChange(index, 'inventory_value_column', v || undefined)}
                options={
                  (inventorySchema && param.inventory_type && inventorySchema[param.inventory_type])
                    ? inventorySchema[param.inventory_type].map((col) => ({ value: col, label: col }))
                    : (INVENTORY_VALUE_COLUMN_OPTIONS[param.inventory_type] ?? [])
                }
                loading={inventorySchemaLoading}
                style={{ width: 180 }}
                allowClear
                placeholder="Par défaut (name)"
                aria-label={`Colonne valeur parametre ${index + 1}`}
              />
            </Form.Item>
          )}
        </Space>
      </Space>
    </Card>
  );
};

export const ParametersEditor: FC<ParametersEditorProps> = ({ value = EMPTY_PARAMS, onChange }) => {
  const { schema: inventorySchema, loading: inventorySchemaLoading } = useInventorySchema(); // Story 62.5
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleAdd = () => {
    const newParam: ParameterDefinition = {
      id: `param-new-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      name: '',
      type: 'string',
      required: false,
    };
    onChange?.([...value, newParam]);
  };

  const handleRemove = (index: number) => {
    onChange?.(value.filter((_, i) => i !== index));
  };

  const handleParamChange = (index: number, field: keyof ParameterDefinition, fieldValue: unknown) => {
    const next = [...value];
    const current = { ...next[index] };
    if (field === 'enum') {
      current.enum = Array.isArray(fieldValue) ? fieldValue : [];
    } else if (field === 'source') {
      current.source = fieldValue as ParameterDefinition['source'];
      // Story 23.5: Reset inventory_type when source changes to manual
      if (fieldValue === 'manual') {
        current.inventory_type = undefined;
        current.inventory_value_column = undefined; // Story 37.5
      }
    } else if (field === 'inventory_type') {
      // Story 37.5: Reset inventory_value_column when inventory_type changes (valid columns differ per type)
      current.inventory_type = fieldValue as ParameterDefinition['inventory_type'];
      current.inventory_value_column = undefined;
    } else {
      (current as Record<string, unknown>)[field] = fieldValue;
    }
    next[index] = current;
    onChange?.(next);
  };

  const sortableIds = value.map((p, i) => p.id ?? `param-${i}`);

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIndex = value.findIndex((_, i) => sortableIds[i] === active.id);
      const newIndex = value.findIndex((_, i) => sortableIds[i] === over.id);
      if (oldIndex >= 0 && newIndex >= 0) {
        onChange?.(arrayMove(value, oldIndex, newIndex));
      }
    }
  };

  return (
    <div>
      <Space orientation="vertical" style={{ width: '100%' }}>
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={sortableIds} strategy={verticalListSortingStrategy}>
            {value.map((param, index) => (
              <SortableParamCard
                key={param.id ?? sortableIds[index]}
                param={param}
                index={index}
                allParams={value}
                onParamChange={handleParamChange}
                onRemove={handleRemove}
                inventorySchema={inventorySchema}
                inventorySchemaLoading={inventorySchemaLoading}
              />
            ))}
          </SortableContext>
        </DndContext>

        {value.length === 0 && (
          <Text type="secondary">Aucun parametre. Ajoutez un parametre pour definir le schema.</Text>
        )}

        <Button type="dashed" onClick={handleAdd} icon={<PlusOutlined />} block>
          Ajouter un parametre
        </Button>
      </Space>
    </div>
  );
};

export default ParametersEditor;
