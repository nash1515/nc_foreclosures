import { useState, useEffect } from 'react';
import { Card, Typography, Tag, Table, Button, Space, Alert, Spin, Empty, Descriptions, List, message } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined,
  DollarOutlined,
  WarningOutlined,
  FileTextOutlined
} from '@ant-design/icons';
import { fetchAnalysis, resolveDiscrepancy, rerunAnalysis } from '../api/analysis';

const { Title, Text, Paragraph } = Typography;

const SEVERITY_COLORS = {
  high: 'red',
  medium: 'orange',
  low: 'blue'
};

const CATEGORY_ICONS = {
  procedural: <FileTextOutlined />,
  financial: <DollarOutlined />,
  property: <WarningOutlined />
};

function AIAnalysisSection({ caseId, initialAnalysis = null, onAnalysisUpdate = null }) {
  const [analysis, setAnalysis] = useState(initialAnalysis);
  const [loading, setLoading] = useState(initialAnalysis === null);
  const [resolving, setResolving] = useState(null);

  useEffect(() => {
    // Only fetch if we don't have initial data
    if (initialAnalysis === null) {
      loadAnalysis();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  useEffect(() => {
    // Update local state if parent passes new analysis data
    if (initialAnalysis !== null) {
      setAnalysis(initialAnalysis);
      setLoading(false);
    }
  }, [initialAnalysis]);

  const loadAnalysis = async () => {
    setLoading(true);
    try {
      const data = await fetchAnalysis(caseId);
      setAnalysis(data);
      // Notify parent of the update
      if (onAnalysisUpdate) {
        onAnalysisUpdate(data);
      }
    } catch (err) {
      message.error('Failed to load analysis');
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async (index, action) => {
    setResolving(index);
    try {
      await resolveDiscrepancy(caseId, index, action);
      message.success(action === 'accept' ? 'Value updated' : 'Kept current value');
      loadAnalysis();
    } catch (err) {
      message.error(err.message);
    } finally {
      setResolving(null);
    }
  };

  const handleRerun = async () => {
    try {
      await rerunAnalysis(caseId);
      message.success('Analysis queued for rerun');
      loadAnalysis();
    } catch (err) {
      message.error('Failed to rerun analysis');
    }
  };

  if (loading) {
    return <Card title="AI Analysis"><Spin /></Card>;
  }

  if (!analysis) {
    return (
      <Card title="AI Analysis">
        <Empty description="No AI analysis available for this case" />
      </Card>
    );
  }

  if (analysis.status === 'pending') {
    return (
      <Card title="AI Analysis">
        <Alert
          message="Analysis Pending"
          description="This case is queued for AI analysis. Check back soon."
          type="info"
          showIcon
        />
      </Card>
    );
  }

  if (analysis.status === 'processing') {
    return (
      <Card title="AI Analysis">
        <Alert
          message="Analysis In Progress"
          description="AI is currently analyzing this case..."
          type="info"
          showIcon
          icon={<Spin size="small" />}
        />
      </Card>
    );
  }

  if (analysis.status === 'failed') {
    return (
      <Card
        title="AI Analysis"
        extra={<Button icon={<ReloadOutlined />} onClick={handleRerun}>Retry</Button>}
      >
        <Alert
          message="Analysis Failed"
          description={analysis.error_message || 'Unknown error'}
          type="error"
          showIcon
        />
      </Card>
    );
  }

  // Completed analysis
  const pendingDiscrepancies = (analysis.discrepancies || []).filter(d => d.status === 'pending');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Summary Card */}
      <Card
        title="Case Summary"
        size="small"
        extra={
          <Space>
            <Text type="secondary">Cost: ${((analysis.cost_cents || 0) / 100).toFixed(2)}</Text>
            <Button icon={<ReloadOutlined />} size="small" onClick={handleRerun}>Rerun</Button>
          </Space>
        }
      >
        <Paragraph>{analysis.summary || 'No summary available'}</Paragraph>
      </Card>

      {/* Financials Card */}
      <Card title="Financial Analysis" size="small">
        {analysis.financials ? (
          <>
            <Descriptions column={2} size="small">
              {analysis.financials.mortgage_amount && (
                <Descriptions.Item label="Mortgage Amount">
                  ${analysis.financials.mortgage_amount.toLocaleString()}
                </Descriptions.Item>
              )}
              {analysis.financials.lender && (
                <Descriptions.Item label="Lender">
                  {analysis.financials.lender}
                </Descriptions.Item>
              )}
              {analysis.financials.default_amount && (
                <Descriptions.Item label="Default Amount">
                  ${analysis.financials.default_amount.toLocaleString()}
                </Descriptions.Item>
              )}
            </Descriptions>

            {analysis.financials.liens?.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Text strong>Liens Found:</Text>
                <List
                  size="small"
                  dataSource={analysis.financials.liens}
                  renderItem={lien => (
                    <List.Item>
                      <Tag color="orange">{lien.type}</Tag>
                      {lien.holder}
                      {lien.amount && `: $${lien.amount.toLocaleString()}`}
                      {lien.notes && <Text type="secondary"> - {lien.notes}</Text>}
                    </List.Item>
                  )}
                />
              </div>
            )}

            {analysis.financials.gaps?.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Text type="secondary">Information Not Found:</Text>
                <div style={{ marginTop: 4 }}>
                  {analysis.financials.gaps.map((gap, i) => (
                    <Tag key={i} color="default">{gap}</Tag>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <Text type="secondary">No financial information extracted</Text>
        )}
      </Card>

      {/* Red Flags Card */}
      <Card
        title={
          <Space>
            Red Flags
            {analysis.red_flags?.length > 0 && (
              <Tag color="red">{analysis.red_flags.length}</Tag>
            )}
          </Space>
        }
        size="small"
      >
        {analysis.red_flags?.length > 0 ? (
          <List
            size="small"
            dataSource={analysis.red_flags}
            renderItem={flag => (
              <List.Item>
                <Space>
                  {CATEGORY_ICONS[flag.category]}
                  <Tag color={SEVERITY_COLORS[flag.severity]}>{flag.severity}</Tag>
                  <Text>{flag.description}</Text>
                  {flag.source_document && (
                    <Text type="secondary">({flag.source_document})</Text>
                  )}
                </Space>
              </List.Item>
            )}
          />
        ) : (
          <Text type="success"><CheckCircleOutlined /> No red flags identified</Text>
        )}
      </Card>

      {/* Discrepancies Card */}
      {pendingDiscrepancies.length > 0 && (
        <Card
          title={
            <Space>
              <ExclamationCircleOutlined style={{ color: '#faad14' }} />
              Data Discrepancies
              <Tag color="orange">{pendingDiscrepancies.length} pending</Tag>
            </Space>
          }
          size="small"
        >
          <Table
            size="small"
            pagination={false}
            dataSource={analysis.discrepancies.map((d, i) => ({ ...d, index: i }))}
            columns={[
              {
                title: 'Field',
                dataIndex: 'field',
                key: 'field',
                render: field => field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
              },
              {
                title: 'Current Value',
                dataIndex: 'db_value',
                key: 'db_value',
                render: val => val || <Text type="secondary">Not set</Text>
              },
              {
                title: 'AI Found',
                dataIndex: 'ai_value',
                key: 'ai_value'
              },
              {
                title: 'Status',
                dataIndex: 'status',
                key: 'status',
                render: status => {
                  if (status === 'pending') return <Tag color="orange">Pending</Tag>;
                  if (status === 'accepted') return <Tag color="green">Accepted</Tag>;
                  return <Tag color="default">Rejected</Tag>;
                }
              },
              {
                title: 'Action',
                key: 'action',
                render: (_, record) => {
                  if (record.status !== 'pending') return null;
                  return (
                    <Space>
                      <Button
                        size="small"
                        type="primary"
                        loading={resolving === record.index}
                        onClick={() => handleResolve(record.index, 'accept')}
                      >
                        Accept AI
                      </Button>
                      <Button
                        size="small"
                        loading={resolving === record.index}
                        onClick={() => handleResolve(record.index, 'reject')}
                      >
                        Keep Current
                      </Button>
                    </Space>
                  );
                }
              }
            ]}
          />
        </Card>
      )}
    </div>
  );
}

export default AIAnalysisSection;
