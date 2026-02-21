import { Card } from 'antd';
import { EnginesAdminTable } from '../../components/admin/EnginesAdminTable';

export function EnginesAdminPanel() {
  return (
    <Card styles={{ header: { borderBottom: 'none', paddingBottom: 0 }, body: { paddingTop: 16 } }}>
      <EnginesAdminTable />
    </Card>
  );
}
