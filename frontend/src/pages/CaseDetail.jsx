import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Typography, Card, Row, Col, Tag, Button, Descriptions, Timeline, Table,
  Spin, Alert, Space, Divider, message, Image, InputNumber
} from 'antd';
import {
  ArrowLeftOutlined, StarOutlined, StarFilled,
  LinkOutlined, FileTextOutlined, PictureOutlined,
  LoadingOutlined, CheckCircleOutlined
} from '@ant-design/icons';
import { fetchCase, addToWatchlist, removeFromWatchlist, updateCase } from '../api/cases';
import { useAutoSave } from '../hooks/useAutoSave';
import NotesCard from '../components/NotesCard';
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

  // Bid ladder state
  const [ourInitialBid, setOurInitialBid] = useState(null);
  const [ourSecondBid, setOurSecondBid] = useState(null);
  const [ourMaxBid, setOurMaxBid] = useState(null);
  const [bidValidationError, setBidValidationError] = useState(null);

  // Team notes state
  const [teamNotes, setTeamNotes] = useState('');

  useEffect(() => {
    async function loadCase() {
      try {
        setLoading(true);
        const data = await fetchCase(id);
        setCaseData(data);

        // Initialize bid ladder state
        setOurInitialBid(data.our_initial_bid);
        setOurSecondBid(data.our_second_bid);
        setOurMaxBid(data.our_max_bid);

        // Initialize team notes
        setTeamNotes(data.team_notes || '');
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

  // Auto-save bid ladder
  const handleBidSave = useCallback(async (updates) => {
    try {
      // Validate bid ladder - FIX: Validate pairwise, not all-or-nothing
      const initial = updates.our_initial_bid ?? ourInitialBid;
      const second = updates.our_second_bid ?? ourSecondBid;
      const max = updates.our_max_bid ?? ourMaxBid;

      // Validate initial vs second (if both present)
      if (initial !== null && second !== null && initial > second) {
        const error = 'Initial bid must be ≤ 2nd bid';
        setBidValidationError(error);
        throw new Error(error);
      }

      // Validate second vs max (if both present)
      if (second !== null && max !== null && second > max) {
        const error = '2nd bid must be ≤ Max bid';
        setBidValidationError(error);
        throw new Error(error);
      }

      // Validate initial vs max (if both present, covers transitive case)
      if (initial !== null && max !== null && initial > max) {
        const error = 'Initial bid must be ≤ Max bid';
        setBidValidationError(error);
        throw new Error(error);
      }

      setBidValidationError(null);
      await updateCase(id, updates);
      // No need to update caseData - local state already has correct values
    } catch (err) {
      message.error('Failed to save bid ladder');
      throw err;
    }
  }, [id, ourInitialBid, ourSecondBid, ourMaxBid]);

  // Auto-save hooks for each bid field
  const { saveState: initialBidSaveState } = useAutoSave(
    (value) => handleBidSave({ our_initial_bid: value }),
    ourInitialBid
  );
  const { saveState: secondBidSaveState } = useAutoSave(
    (value) => handleBidSave({ our_second_bid: value }),
    ourSecondBid
  );
  const { saveState: maxBidSaveState } = useAutoSave(
    (value) => handleBidSave({ our_max_bid: value }),
    ourMaxBid
  );

  // Unified save state for the card (show if any field is saving/saved)
  const bidCardSaveState = initialBidSaveState === 'saving' ||
                           secondBidSaveState === 'saving' ||
                           maxBidSaveState === 'saving'
                           ? 'saving'
                           : initialBidSaveState === 'saved' ||
                             secondBidSaveState === 'saved' ||
                             maxBidSaveState === 'saved'
                           ? 'saved'
                           : 'idle';

  // Auto-save team notes
  const handleNotesSave = useCallback(async (updates) => {
    try {
      await updateCase(id, updates);
      // No need to update caseData - NotesCard manages its own state
    } catch (err) {
      message.error('Failed to save notes');
      throw err;
    }
  }, [id]);

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
              Bid Deadline: {dayjs(c.next_bid_deadline).format('MMM D')} ({daysUntilDeadline} days)
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

          {/* Bid Information - Moved from right column */}
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

            {/* Bid Ladder Editable */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Title level={5} style={{ margin: 0 }}>Your Bid Ladder</Title>
              <Space size={4}>
                {bidCardSaveState === 'saving' && (
                  <>
                    <LoadingOutlined style={{ color: '#1890ff', fontSize: 12 }} />
                    <Text type="secondary" style={{ fontSize: 12 }}>Saving...</Text>
                  </>
                )}
                {bidCardSaveState === 'saved' && (
                  <>
                    <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 12 }} />
                    <Text type="success" style={{ fontSize: 12 }}>Saved</Text>
                  </>
                )}
              </Space>
            </div>

            <div style={{ marginTop: 12 }}>
              <Space direction="vertical" style={{ width: '100%' }} size="small">
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>Our Initial Bid</Text>
                  <InputNumber
                    value={ourInitialBid}
                    onChange={setOurInitialBid}
                    formatter={value => `$${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                    parser={value => value.replace(/\$\s?|(,*)/g, '')}
                    style={{ width: '100%', marginTop: 4 }}
                    min={0}
                    step={100}
                    placeholder="Enter initial bid"
                  />
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>Our 2nd Bid</Text>
                  <InputNumber
                    value={ourSecondBid}
                    onChange={setOurSecondBid}
                    formatter={value => `$${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                    parser={value => value.replace(/\$\s?|(,*)/g, '')}
                    style={{ width: '100%', marginTop: 4 }}
                    min={0}
                    step={100}
                    placeholder="Enter 2nd bid"
                  />
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>Our Max Bid</Text>
                  <InputNumber
                    value={ourMaxBid}
                    onChange={setOurMaxBid}
                    formatter={value => `$${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                    parser={value => value.replace(/\$\s?|(,*)/g, '')}
                    style={{ width: '100%', marginTop: 4 }}
                    min={0}
                    step={100}
                    placeholder="Enter max bid"
                  />
                </div>
              </Space>

              {bidValidationError && (
                <Alert
                  type="error"
                  message={bidValidationError}
                  showIcon
                  style={{ marginTop: 12 }}
                />
              )}
            </div>
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

        {/* Right Column - Notes & Events */}
        <Col xs={24} lg={12}>
          {/* Team Notes */}
          <NotesCard
            initialNotes={teamNotes}
            onSave={handleNotesSave}
          />

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
