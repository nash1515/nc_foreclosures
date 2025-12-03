import { Typography, Alert } from 'antd';

const { Title } = Typography;

function Settings() {
  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>Settings</Title>
      <Alert
        message="Coming Soon"
        description="Scheduler configuration will appear here."
        type="info"
        showIcon
      />
    </div>
  );
}

export default Settings;
