/**
 * EndNode — Visual-only end node for the workflow builder (Story 16.7, AC1).
 *
 * Displays a grey "Fin" indicator. Has a single target handle at the top.
 * Excluded from backend conversion (isEndNode flag).
 */

import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { CheckCircleOutlined } from '@ant-design/icons';

const EndNode: React.FC<NodeProps> = () => {
  return (
    <div
      style={{
        border: '2px solid #8c8c8c',
        borderRadius: 8,
        padding: 12,
        background: '#f5f5f5',
        minWidth: 120,
        textAlign: 'center',
      }}
      role="img"
      aria-label="Nœud de fin"
    >
      <Handle
        type="target"
        position={Position.Top}
        id="input"
        style={{ background: '#8c8c8c' }}
        aria-label="Non modifiable - Entrée depuis dernière étape"
      />

      <CheckCircleOutlined style={{ fontSize: 24, color: '#8c8c8c' }} />
      <div style={{ fontWeight: 600, marginTop: 4, fontSize: 13 }}>Fin</div>
    </div>
  );
};

export default memo(EndNode);
