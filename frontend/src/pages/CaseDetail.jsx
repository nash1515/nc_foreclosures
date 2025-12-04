import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Typography, Card, Row, Col, Tag, Button, Descriptions, Timeline, Table,
  Spin, Alert, Space, Divider, message, Image
} from 'antd';
import {
  ArrowLeftOutlined, StarOutlined, StarFilled,
  LinkOutlined, FileTextOutlined, PictureOutlined
} from '@ant-design/icons';
import { fetchCase, addToWatchlist, removeFromWatchlist } from '../api/cases';
import dayjs from 'dayjs';

const { Title, Text } = Typography;

// Classification colors
const CLASSIFICATION_COLORS = {
  upcoming: 'blue',
  upset_bid: 'red',
  blocked: 'orange',
  closed_sold: 'green',
  closed_dismissed: 'default'
};

function CaseDetail() {
  const { id } = useParams();
  const [caseData, setCaseData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadCase() {
      try {
        setLoading(true);
        const data = await fetchCase(id);
        setCaseData(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadCase();
  }, [id]);

  const handleWatchlistToggle = async () => {
    if (!caseData) return;

    try {
      if (caseData.is_watchlisted) {
        await removeFromWatchlist(caseData.id);
        message.success('Removed from watchlist');
      } else {
        await addToWatchlist(caseData.id);
        message.success('Added to watchlist');
      }
      setCaseData(prev => ({ ...prev, is_watchlisted: !prev.is_watchlisted }));
    } catch (err) {
      message.error('Failed to update watchlist');
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '24px' }}>
        <Alert type="error" message={error} showIcon />
        <Link to="/cases" style={{ marginTop: 16, display: 'inline-block' }}>
          <Button icon={<ArrowLeftOutlined />}>Back to Cases</Button>
        </Link>
      </div>
    );
  }

  const c = caseData;
  const daysUntilDeadline = c.next_bid_deadline
    ? dayjs(c.next_bid_deadline).diff(dayjs(), 'day')
    : null;

  return (
    <div style={{ padding: '24px' }}>
      {/* Header */}
      <Space style={{ marginBottom: 16 }}>
        <Link to="/cases">
          <Button icon={<ArrowLeftOutlined />}>Back to Cases</Button>
        </Link>
        <Title level={4} style={{ margin: 0 }}>{c.case_number}</Title>
        <Button
          type={c.is_watchlisted ? 'primary' : 'default'}
          icon={c.is_watchlisted ? <StarFilled /> : <StarOutlined />}
          onClick={handleWatchlistToggle}
        >
          {c.is_watchlisted ? 'Watchlisted' : 'Add to Watchlist'}
        </Button>
      </Space>

      {/* Case Title and Status */}
      <Card style={{ marginBottom: 16 }}>
        <Title level={4} style={{ marginTop: 0 }}>{c.style || c.case_number}</Title>
        <Space>
          <Text type="secondary">{c.county_name} County</Text>
          <Text type="secondary">|</Text>
          <Text type="secondary">Filed: {c.file_date ? dayjs(c.file_date).format('MM/DD/YYYY') : '-'}</Text>
          <Text type="secondary">|</Text>
          <Text type="secondary">Status: {c.case_status || '-'}</Text>
        </Space>
        <div style={{ marginTop: 8 }}>
          <Tag color={CLASSIFICATION_COLORS[c.classification] || 'default'}>
            {c.classification?.replace('_', ' ').toUpperCase() || 'UNKNOWN'}
          </Tag>
          {daysUntilDeadline !== null && daysUntilDeadline >= 0 && (
            <Tag color={daysUntilDeadline <= 3 ? 'red' : 'orange'}>
              Deadline: {dayjs(c.next_bid_deadline).format('MMM D')} ({daysUntilDeadline} days)
            </Tag>
          )}
        </div>
      </Card>

      <Row gutter={16}>
        {/* Left Column - Property & Photo */}
        <Col xs={24} lg={12}>
          <Card title="Property" style={{ marginBottom: 16 }}>
            <Row gutter={16}>
              <Col span={c.photo_url ? 16 : 24}>
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="Address">
                    {c.property_address || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Legal Description">
                    <Text ellipsis={{ tooltip: c.legal_description }}>
                      {c.legal_description || '-'}
                    </Text>
                  </Descriptions.Item>
                </Descriptions>

                {/* Enrichment Links */}
                <Divider style={{ margin: '12px 0' }} />
                <Space wrap>
                  {c.case_url && (
                    <a href={c.case_url} target="_blank" rel="noopener noreferrer">
                      <Button size="small" icon={<LinkOutlined />}>
                        NC Courts Portal
                      </Button>
                    </a>
                  )}
                  <Button size="small" icon={<LinkOutlined />} disabled>
                    Zillow
                  </Button>
                  <Button size="small" icon={<LinkOutlined />} disabled>
                    Propwire
                  </Button>
                  <Button size="small" icon={<LinkOutlined />} disabled>
                    County Records
                  </Button>
                  <Button size="small" icon={<FileTextOutlined />} disabled>
                    Deed
                  </Button>
                </Space>
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Additional enrichment links coming in Phase 5
                  </Text>
                </div>
              </Col>
              {/* Photo placeholder */}
              <Col span={c.photo_url ? 8 : 0}>
                {c.photo_url ? (
                  <Image src={c.photo_url} alt="Property" style={{ maxWidth: '100%' }} />
                ) : (
                  <div style={{
                    width: 120, height: 90, background: '#f5f5f5',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    border: '1px dashed #d9d9d9', borderRadius: 4
                  }}>
                    <PictureOutlined style={{ fontSize: 24, color: '#bfbfbf' }} />
                  </div>
                )}
              </Col>
            </Row>
          </Card>

          {/* Parties */}
          <Card title="Parties" style={{ marginBottom: 16 }}>
            {c.parties && Object.keys(c.parties).length > 0 ? (
              <Descriptions column={1} size="small">
                {Object.entries(c.parties).map(([type, names]) => (
                  <Descriptions.Item key={type} label={type}>
                    {names.join(', ')}
                  </Descriptions.Item>
                ))}
              </Descriptions>
            ) : (
              <Text type="secondary">No parties on record</Text>
            )}
          </Card>

          {/* Upset Bidders */}
          {c.upset_bidders && c.upset_bidders.length > 0 && (
            <Card title="Upset Bidders" style={{ marginBottom: 16 }}>
              <Table
                dataSource={c.upset_bidders}
                rowKey={(r, i) => i}
                size="small"
                pagination={false}
                columns={[
                  { title: 'Date', dataIndex: 'date', render: d => d ? dayjs(d).format('MM/DD/YYYY') : '-' },
                  { title: 'Bidder', dataIndex: 'bidder' },
                  { title: 'Amount', dataIndex: 'amount', render: a => a ? `$${a.toLocaleString()}` : '-' }
                ]}
              />
            </Card>
          )}
        </Col>

        {/* Right Column - Bid Info & Events */}
        <Col xs={24} lg={12}>
          {/* Bid Information */}
          <Card title="Bid Information" style={{ marginBottom: 16 }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Current Bid">
                <Text strong style={{ fontSize: 16 }}>
                  {c.current_bid_amount ? `$${c.current_bid_amount.toLocaleString()}` : '-'}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label="Minimum Next Bid">
                {c.minimum_next_bid ? `$${c.minimum_next_bid.toLocaleString()}` : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Sale Date">
                {c.sale_date ? dayjs(c.sale_date).format('MM/DD/YYYY') : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Bid Deadline">
                {c.next_bid_deadline ? dayjs(c.next_bid_deadline).format('MM/DD/YYYY h:mm A') : '-'}
              </Descriptions.Item>
            </Descriptions>

            <Divider style={{ margin: '12px 0' }} />

            {/* Bid Ladder Display */}
            <Title level={5}>Your Bid Ladder</Title>
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="Initial Bid">
                <Text type="secondary">Not set</Text>
              </Descriptions.Item>
              <Descriptions.Item label="2nd Bid">
                <Text type="secondary">Not set</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Max Bid">
                <Text type="secondary">Not set</Text>
              </Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Bid ladder editing coming in Phase 3
              </Text>
            </div>
          </Card>

          {/* Attorney Info */}
          {(c.attorney_name || c.trustee_name) && (
            <Card title="Contacts" style={{ marginBottom: 16 }}>
              <Descriptions column={1} size="small">
                {c.trustee_name && (
                  <Descriptions.Item label="Trustee">{c.trustee_name}</Descriptions.Item>
                )}
                {c.attorney_name && (
                  <Descriptions.Item label="Attorney">{c.attorney_name}</Descriptions.Item>
                )}
                {c.attorney_phone && (
                  <Descriptions.Item label="Phone">{c.attorney_phone}</Descriptions.Item>
                )}
                {c.attorney_email && (
                  <Descriptions.Item label="Email">{c.attorney_email}</Descriptions.Item>
                )}
              </Descriptions>
            </Card>
          )}

          {/* Events Timeline */}
          <Card title="Events Timeline" style={{ marginBottom: 16 }}>
            {c.events && c.events.length > 0 ? (
              <Timeline
                items={c.events.slice(0, 10).map(event => ({
                  children: (
                    <div>
                      <Text strong>{event.date ? dayjs(event.date).format('MM/DD/YYYY') : 'No date'}</Text>
                      <br />
                      <Text>{event.type || event.description || 'Event'}</Text>
                      {event.filed_by && <Text type="secondary"> - {event.filed_by}</Text>}
                    </div>
                  )
                }))}
              />
            ) : (
              <Text type="secondary">No events on record</Text>
            )}
            {c.events && c.events.length > 10 && (
              <Text type="secondary">Showing 10 of {c.events.length} events</Text>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

export default CaseDetail;
