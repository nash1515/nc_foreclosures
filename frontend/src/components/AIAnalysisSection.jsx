import { useState, useEffect } from 'react';
import { Card, Typography, Tag, Table, Button, Space, Alert, Spin, Empty, Descriptions, List, message, Collapse, Row, Col } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined,
  DollarOutlined,
  WarningOutlined,
  FileTextOutlined,
  TeamOutlined,
  AuditOutlined,
  BulbOutlined
} from '@ant-design/icons';
import { fetchAnalysis, resolveDiscrepancy, rerunAnalysis } from '../api/analysis';

const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;

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
  const comp = analysis.comprehensive_analysis || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header with cost and rerun button */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 12 }}>
        <Text type="secondary">Cost: ${((analysis.cost_cents || 0) / 100).toFixed(2)}</Text>
        <Button icon={<ReloadOutlined />} size="small" onClick={handleRerun}>Rerun Analysis</Button>
      </div>

      {/* I. Executive Summary */}
      <Card
        title={
          <Space>
            <FileTextOutlined />
            I. Executive Summary
          </Space>
        }
        size="small"
      >
        <Paragraph style={{ marginBottom: 0, fontSize: '14px', lineHeight: 1.8 }}>
          {comp.executive_summary || analysis.summary || 'No summary available'}
        </Paragraph>
      </Card>

      {/* II. Parties Analysis - Two Column Layout */}
      {comp.parties_analysis && (
        <Card
          title={
            <Space>
              <TeamOutlined />
              II. Analysis of Parties
            </Space>
          }
          size="small"
        >
          <Row gutter={24}>
            {/* Plaintiff Column */}
            <Col span={12}>
              {comp.parties_analysis.plaintiff && (
                <div>
                  <Title level={5} style={{ marginBottom: 8 }}>
                    <Tag color="blue">Plaintiff</Tag>
                    {comp.parties_analysis.plaintiff.identity}
                  </Title>
                  {comp.parties_analysis.plaintiff.actions_taken?.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text strong>Actions Taken:</Text>
                      <ul style={{ margin: '4px 0', paddingLeft: 20 }}>
                        {comp.parties_analysis.plaintiff.actions_taken.map((action, i) => (
                          <li key={i}><Text>{action}</Text></li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {comp.parties_analysis.plaintiff.strategy_assessment && (
                    <div style={{ background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
                      <Text type="secondary" italic>
                        {comp.parties_analysis.plaintiff.strategy_assessment}
                      </Text>
                    </div>
                  )}
                </div>
              )}
            </Col>

            {/* Defendant Column */}
            <Col span={12}>
              {comp.parties_analysis.defendant && (
                <div>
                  <Title level={5} style={{ marginBottom: 8 }}>
                    <Tag color="red">Defendant</Tag>
                    {comp.parties_analysis.defendant.identity}
                  </Title>
                  {comp.parties_analysis.defendant.actions_taken?.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text strong>Actions Taken:</Text>
                      <ul style={{ margin: '4px 0', paddingLeft: 20 }}>
                        {comp.parties_analysis.defendant.actions_taken.map((action, i) => (
                          <li key={i}><Text>{action}</Text></li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {comp.parties_analysis.defendant.strategy_assessment && (
                    <div style={{ background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
                      <Text type="secondary" italic>
                        {comp.parties_analysis.defendant.strategy_assessment}
                      </Text>
                    </div>
                  )}
                </div>
              )}
            </Col>
          </Row>
        </Card>
      )}

      {/* III. Legal & Procedural Analysis */}
      {comp.legal_procedural_analysis && (
        <Card
          title={
            <Space>
              <AuditOutlined />
              III. Legal & Procedural Analysis
            </Space>
          }
          size="small"
        >
          {/* Key Legal Issues */}
          {comp.legal_procedural_analysis.key_legal_issues?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <Text strong>Key Legal Issues:</Text>
              <List
                size="small"
                dataSource={comp.legal_procedural_analysis.key_legal_issues}
                renderItem={issue => (
                  <List.Item>
                    <div>
                      <Text>{issue.issue}</Text>
                      {issue.resolution && <div><Text type="secondary">Resolution: {issue.resolution}</Text></div>}
                      {issue.applicable_statute && (
                        <Tag color="purple" style={{ marginTop: 4 }}>{issue.applicable_statute}</Tag>
                      )}
                    </div>
                  </List.Item>
                )}
              />
            </div>
          )}

          {/* Procedural Compliance */}
          {comp.legal_procedural_analysis.procedural_compliance && (
            <div style={{ marginBottom: 16 }}>
              <Text strong>Procedural Compliance:</Text>
              <Descriptions column={1} size="small" style={{ marginTop: 8 }}>
                {comp.legal_procedural_analysis.procedural_compliance.notice_requirements && (
                  <Descriptions.Item label="Notice Requirements">
                    {comp.legal_procedural_analysis.procedural_compliance.notice_requirements}
                  </Descriptions.Item>
                )}
                {comp.legal_procedural_analysis.procedural_compliance.posting_publication && (
                  <Descriptions.Item label="Posting/Publication">
                    {comp.legal_procedural_analysis.procedural_compliance.posting_publication}
                  </Descriptions.Item>
                )}
                {comp.legal_procedural_analysis.procedural_compliance.sale_procedure && (
                  <Descriptions.Item label="Sale Procedure">
                    {comp.legal_procedural_analysis.procedural_compliance.sale_procedure}
                  </Descriptions.Item>
                )}
              </Descriptions>
              {comp.legal_procedural_analysis.procedural_compliance.irregularities_noted?.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <Text type="warning">Irregularities Noted:</Text>
                  <ul style={{ margin: '4px 0', paddingLeft: 20 }}>
                    {comp.legal_procedural_analysis.procedural_compliance.irregularities_noted.map((item, i) => (
                      <li key={i}><Text type="warning">{item}</Text></li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Rulings and Orders */}
          {comp.legal_procedural_analysis.rulings_and_orders?.length > 0 && (
            <div>
              <Text strong>Rulings & Orders:</Text>
              <List
                size="small"
                dataSource={comp.legal_procedural_analysis.rulings_and_orders}
                renderItem={ruling => (
                  <List.Item>
                    <div>
                      <Text strong>{ruling.date}:</Text> {ruling.ruling}
                      {ruling.impact && <div><Text type="secondary">Impact: {ruling.impact}</Text></div>}
                    </div>
                  </List.Item>
                )}
              />
            </div>
          )}
        </Card>
      )}

      {/* IV. Conclusion & Key Takeaways */}
      {comp.conclusion_and_takeaways && (
        <Card
          title={
            <Space>
              <BulbOutlined />
              IV. Conclusion & Key Takeaways
            </Space>
          }
          size="small"
        >
          {comp.conclusion_and_takeaways.case_outcome && (
            <div style={{ marginBottom: 16 }}>
              <Text strong>Case Outcome:</Text>
              <Paragraph style={{ marginTop: 4 }}>{comp.conclusion_and_takeaways.case_outcome}</Paragraph>
            </div>
          )}

          {comp.conclusion_and_takeaways.key_takeaways?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <Text strong>Key Takeaways:</Text>
              <ul style={{ margin: '8px 0', paddingLeft: 20 }}>
                {comp.conclusion_and_takeaways.key_takeaways.map((takeaway, i) => (
                  <li key={i} style={{ marginBottom: 4 }}><Text>{takeaway}</Text></li>
                ))}
              </ul>
            </div>
          )}

          {comp.conclusion_and_takeaways.investment_considerations && (
            <Alert
              message="Investment Considerations"
              description={comp.conclusion_and_takeaways.investment_considerations}
              type="info"
              showIcon
              icon={<DollarOutlined />}
            />
          )}
        </Card>
      )}

      {/* Financials Card - Collapsible */}
      <Collapse ghost>
        <Panel
          header={
            <Space>
              <DollarOutlined />
              Financial Details
            </Space>
          }
          key="financials"
        >
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
                {analysis.financials.total_debt && (
                  <Descriptions.Item label="Total Debt">
                    ${analysis.financials.total_debt.toLocaleString()}
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
                        {lien.priority && <Tag size="small">{lien.priority}</Tag>}
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
        </Panel>
      </Collapse>

      {/* Red Flags Card */}
      <Card
        title={
          <Space>
            <WarningOutlined style={{ color: analysis.red_flags?.length > 0 ? '#ff4d4f' : '#52c41a' }} />
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
                <div style={{ width: '100%' }}>
                  <Space>
                    {CATEGORY_ICONS[flag.category]}
                    <Tag color={SEVERITY_COLORS[flag.severity]}>{flag.severity}</Tag>
                    <Text>{flag.description}</Text>
                  </Space>
                  {flag.investment_impact && (
                    <div style={{ marginTop: 4, paddingLeft: 24 }}>
                      <Text type="secondary" italic>Impact: {flag.investment_impact}</Text>
                    </div>
                  )}
                  {flag.source_document && (
                    <div style={{ paddingLeft: 24 }}>
                      <Tag size="small" color="default">{flag.source_document}</Tag>
                    </div>
                  )}
                </div>
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
