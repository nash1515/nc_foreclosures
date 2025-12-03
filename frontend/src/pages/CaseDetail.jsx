import { Typography, Alert } from 'antd';
import { useParams } from 'react-router-dom';

const { Title } = Typography;

function CaseDetail() {
  const { id } = useParams();

  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>Case Detail: {id}</Title>
      <Alert
        message="Coming Soon"
        description="Full case information, bid ladder, and notes will appear here."
        type="info"
        showIcon
      />
    </div>
  );
}

export default CaseDetail;
