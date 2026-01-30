/**
 * ParametersEditor component for managing action parameters visually (Story 2.17, AC #1, #2, #3, #6).
 *
 * Features:
 * - List of parameters with "Ajouter un parametre" button (AC1)
 * - Inline form per parameter: name, type, required, default, description (AC2)
 * - Drag-and-drop reorder via @dnd-kit (AC3), same pattern as StepsEditor
 * - Delete (X) per parameter; inline validation: name required, name unique, type required (AC6)
 */

import React from 'react';
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
} from 'antd';
import { PlusOutlined, DeleteOutlined, HolderOutlined } from '@ant-design/icons';
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
import type { ParameterDefinition, ParameterSchemaType } from '../../types/api';

const { Text } = Typography;

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

interface SortableParamCardProps {
  param: ParameterDefinition;
  index: number;
  allParams: ParameterDefinition[];
  onParamChange: (index: number, field: keyof ParameterDefinition, fieldValue: unknown) => void;
  onRemove: (index: number) => void;
}

const SortableParamCard: React.FC<SortableParamCardProps> = ({
  param,
  index,
  allParams,
  onParamChange,
  onRemove,
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

  const style: React.CSSProperties = {
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
      <Space direction="vertical" style={{ width: '100%' }} size="small">
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
      </Space>
    </Card>
  );
};

export const ParametersEditor: React.FC<ParametersEditorProps> = ({ value = [], onChange }) => {
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
      <Space direction="vertical" style={{ width: '100%' }}>
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
