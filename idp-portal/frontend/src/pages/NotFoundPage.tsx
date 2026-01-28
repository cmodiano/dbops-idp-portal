import { Result, Button } from 'antd';
import { useNavigate } from 'react-router';

export default function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <Result
      status="404"
      title="404"
      subTitle="Page non trouvee."
      extra={
        <Button type="primary" onClick={() => navigate('/catalog')}>
          Retour au catalogue
        </Button>
      }
    />
  );
}
