import { Button, Result } from 'antd';
import { LoginOutlined } from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';

export default function LoginPage() {
  const { login } = useAuth();

  return (
    <Result
      icon={<LoginOutlined style={{ color: '#00874E' }} />}
      title="IDP Portal"
      subTitle="Connectez-vous avec votre compte d'entreprise pour acceder au portail."
      extra={
        <Button type="primary" size="large" icon={<LoginOutlined />} onClick={login}>
          Se connecter via SSO
        </Button>
      }
    />
  );
}
