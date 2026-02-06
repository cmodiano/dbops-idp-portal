/**
 * StartNode — Visual-only start node for the workflow builder (Story 16.7, AC1).
 *
 * Displays a green "Départ" indicator. Has a single source handle at the bottom.
 * Excluded from backend conversion (isStartNode flag).
 */

import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { PlayCircleOutlined } from '@ant-design/icons';

const StartNode: React.FC<NodeProps> = () => {
  return (
    <div
      style={{
        border: '2px solid #52c41a',
        borderRadius: 8,
        padding: 12,
        background: '#f6ffed',
        minWidth: 120,
        textAlign: 'center',
      }}
      role="img"
      aria-label="Nœud de départ"
    >
      <PlayCircleOutlined style={{ fontSize: 24, color: '#52c41a' }} />
      <div style={{ fontWeight: 600, marginTop: 4, fontSize: 13 }}>Départ</div>

      <Handle
        type="source"
        position={Position.Bottom}
        id="output"
        style={{ background: '#52c41a' }}
        aria-label="Non modifiable - Sortie vers première étape"
      />
    </div>
  );
};

export default memo(StartNode);
