import { Typography, Alert } from 'antd';

const { Title } = Typography;

function Dashboard() {
  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>Upset Bid Dashboard</Title>
      <Alert
        message="Coming Soon"
        description="Active upset bid cases will appear here, sorted by deadline."
        type="info"
        showIcon
      />
    </div>
  );
}

export default Dashboard;
