import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Form, Input, Button, Alert, Card, Typography, Divider, Flex } from 'antd';
import { UserOutlined, LockOutlined, LoginOutlined } from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';

const { Title } = Typography;

const ERROR_MESSAGES: Record<string, string> = {
  INVALID_CREDENTIALS: 'Identifiant ou mot de passe invalide.',
  INSUFFICIENT_PRIVILEGES: 'Votre compte ne dispose pas des privilèges requis pour accéder au portail.',
  NO_PROFILE: 'Aucun profil associé à votre compte. Contactez un administrateur.',
  LDAP_UNAVAILABLE: "Le service d'authentification est temporairement indisponible. Réessayez plus tard.",
  RATE_LIMIT_EXCEEDED: 'Trop de tentatives. Veuillez patienter avant de réessayer.',
};

export default function LoginPage() {
  const { login, loginWithCredentials } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const authMethods = (import.meta.env.VITE_PORTAL_AUTH_METHODS || 'ldap').split(',').map((m: string) => m.trim());
  const showSamlButton = authMethods.includes('saml');

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    setErrorMessage(null);
    try {
      await loginWithCredentials(values.username, values.password);
      navigate('/catalog');
    } catch (err: unknown) {
      const error = err as { code?: string; message?: string };
      const code = error.code ?? 'UNKNOWN';
      setErrorMessage(ERROR_MESSAGES[code] ?? `Erreur inattendue : ${error.message ?? 'Veuillez réessayer.'}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Flex justify="center" align="center" style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <Card style={{ width: 400, boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
        <Flex vertical align="center" gap={8} style={{ marginBottom: 24 }}>
          <LoginOutlined style={{ fontSize: 40, color: '#00874E' }} />
          <Title level={3} style={{ margin: 0 }}>IDP Portal</Title>
        </Flex>

        {errorMessage && (
          <Alert
            type="error"
            title={errorMessage}
            closable
            onClose={() => setErrorMessage(null)}
            style={{ marginBottom: 16 }}
          />
        )}

        <Form
          name="login"
          onFinish={onFinish}
          layout="vertical"
          requiredMark={false}
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: "Veuillez entrer votre identifiant." }]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="Identifiant"
              size="large"
              autoComplete="username"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: 'Veuillez entrer votre mot de passe.' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="Mot de passe"
              size="large"
              autoComplete="current-password"
            />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              size="large"
              style={{ background: '#00874E', borderColor: '#00874E' }}
            >
              Se connecter
            </Button>
          </Form.Item>
        </Form>

        {showSamlButton && (
          <>
            <Divider plain>ou</Divider>
            <Button
              block
              size="large"
              icon={<LoginOutlined />}
              onClick={login}
            >
              Se connecter via SSO
            </Button>
          </>
        )}
      </Card>
    </Flex>
  );
}
