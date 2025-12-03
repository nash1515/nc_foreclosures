import { Button, Card, Typography, Space } from 'antd';
import { GoogleOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

function Login() {
  const handleGoogleLogin = () => {
    window.location.href = '/api/auth/login';
  };

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: '#f0f2f5'
    }}>
      <Card style={{ width: 400, textAlign: 'center' }}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Title level={2}>NC Foreclosures</Title>
          <Text type="secondary">Sign in to access the dashboard</Text>
          <Button
            type="primary"
            icon={<GoogleOutlined />}
            size="large"
            onClick={handleGoogleLogin}
            style={{ width: '100%' }}
          >
            Sign in with Google
          </Button>
        </Space>
      </Card>
    </div>
  );
}

export default Login;
