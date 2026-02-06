/**
 * CustomEdge — Interactive edge with selection highlight and context menu (Story 16.7, AC5).
 *
 * Click on an edge to select it (glow effect). A context menu button appears
 * at the midpoint with a "Supprimer la connexion" option.
 */

import React from 'react';
import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  useReactFlow,
  type EdgeProps,
} from '@xyflow/react';
import { Button, Dropdown } from 'antd';
import { DeleteOutlined, MoreOutlined } from '@ant-design/icons';

const CustomEdge: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  label,
  labelStyle,
  selected,
  markerEnd,
}) => {
  const { setEdges } = useReactFlow();

  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  const handleDelete = () => {
    setEdges((eds) => eds.filter((e) => e.id !== id));
  };

  const menuItems = [
    {
      key: 'delete',
      label: 'Supprimer la connexion',
      icon: <DeleteOutlined />,
      danger: true,
      onClick: handleDelete,
    },
  ];

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          ...style,
          strokeWidth: selected ? 3 : 2,
          filter: selected ? 'drop-shadow(0 0 4px currentColor)' : undefined,
        }}
        markerEnd={markerEnd}
      />
      {/* Edge label (succès/erreur) */}
      {label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY - 10}px)`,
              fontSize: 10,
              pointerEvents: 'none',
              ...(labelStyle as React.CSSProperties),
            }}
            className="nodrag nopan"
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
      {/* Context menu button when selected */}
      {selected && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY + 10}px)`,
              pointerEvents: 'all',
            }}
            className="nodrag nopan"
          >
            <Dropdown menu={{ items: menuItems }} trigger={['click']}>
              <Button
                size="small"
                icon={<MoreOutlined />}
                aria-label="Menu connexion"
                style={{
                  background: 'white',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
                  borderRadius: '50%',
                  width: 24,
                  height: 24,
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              />
            </Dropdown>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
};

export default CustomEdge;
