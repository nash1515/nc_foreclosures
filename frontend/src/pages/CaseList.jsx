import { Typography, Alert } from 'antd';

const { Title } = Typography;

function CaseList() {
  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>All Cases</Title>
      <Alert
        message="Coming Soon"
        description="Searchable table of all 1,724 cases will appear here."
        type="info"
        showIcon
      />
    </div>
  );
}

export default CaseList;
