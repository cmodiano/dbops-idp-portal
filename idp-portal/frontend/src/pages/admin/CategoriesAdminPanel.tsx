import { Card } from 'antd';
import { CategoriesAdminTable } from '../../components/admin/CategoriesAdminTable';

export function CategoriesAdminPanel() {
  return (
    <Card styles={{ header: { borderBottom: 'none', paddingBottom: 0 }, body: { paddingTop: 16 } }}>
      <CategoriesAdminTable />
    </Card>
  );
}
