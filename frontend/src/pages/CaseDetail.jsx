import { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import {
  Typography, Card, Row, Col, Tag, Button, Descriptions, Timeline, Table,
  Spin, Alert, Space, Divider, message, InputNumber, Tooltip
} from 'antd';
import {
  ArrowLeftOutlined, StarOutlined, StarFilled,
  LinkOutlined, FileTextOutlined,
  LoadingOutlined, CheckCircleOutlined
} from '@ant-design/icons';
import { fetchCase, addToWatchlist, removeFromWatchlist, updateCase } from '../api/cases';
import { fetchAnalysis } from '../api/analysis';
import { useAutoSave } from '../hooks/useAutoSave';
import NotesCard from '../components/NotesCard';
import AIAnalysisSection from '../components/AIAnalysisSection';
import { formatZillowUrl, formatGoogleMapsUrl } from '../utils/urlHelpers';
import { ZillowIcon } from '../assets/ZillowIcon';
import { GoogleMapsIcon } from '../assets/GoogleMapsIcon';
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
  const [searchParams] = useSearchParams();
  const countyParam = searchParams.get('county');
  const interestParam = searchParams.get('interest');
  const [caseData, setCaseData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Bid ladder state
  const [ourInitialBid, setOurInitialBid] = useState(null);
  const [ourSecondBid, setOurSecondBid] = useState(null);
  const [ourMaxBid, setOurMaxBid] = useState(null);
  const [estimatedSalePrice, setEstimatedSalePrice] = useState(null);
  const [estimatedRehabCost, setEstimatedRehabCost] = useState(null);
  const [bidValidationError, setBidValidationError] = useState(null);

  // Team notes state
  const [teamNotes, setTeamNotes] = useState('');

  // Analysis state
  const [analysis, setAnalysis] = useState(null);

  // Interest status state
  const [interestStatus, setInterestStatus] = useState(null);
  const [interestError, setInterestError] = useState(null);
  const [interestSaving, setInterestSaving] = useState(false);

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
        setEstimatedSalePrice(data.estimated_sale_price);
        setEstimatedRehabCost(data.estimated_rehab_cost);

        // Initialize team notes
        setTeamNotes(data.team_notes || '');

        // Initialize interest status
        setInterestStatus(data.interest_status || null);

        // Fetch analysis data if case is upset_bid
        if (data.classification === 'upset_bid') {
          try {
            const analysisData = await fetchAnalysis(id);
            setAnalysis(analysisData);
          } catch (err) {
            // Analysis fetch failed or not available - that's ok
            console.error('Failed to fetch analysis:', err);
          }
        }
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
  const { saveState: estimatedSalePriceSaveState } = useAutoSave(
    (value) => handleBidSave({ estimated_sale_price: value }),
    estimatedSalePrice
  );
  const { saveState: estimatedRehabCostSaveState } = useAutoSave(
    (value) => handleBidSave({ estimated_rehab_cost: value }),
    estimatedRehabCost
  );

  // Unified save state for the card (show if any field is saving/saved)
  const bidCardSaveState = initialBidSaveState === 'saving' ||
                           secondBidSaveState === 'saving' ||
                           maxBidSaveState === 'saving' ||
                           estimatedSalePriceSaveState === 'saving' ||
                           estimatedRehabCostSaveState === 'saving'
                           ? 'saving'
                           : initialBidSaveState === 'saved' ||
                             secondBidSaveState === 'saved' ||
                             maxBidSaveState === 'saved' ||
                             estimatedSalePriceSaveState === 'saved' ||
                             estimatedRehabCostSaveState === 'saved'
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

  // Handle interest status change
  const handleInterestChange = async (newStatus) => {
    setInterestError(null);

    // If clicking the same status, clear it (toggle off)
    const statusToSet = newStatus === interestStatus ? '' : newStatus;

    setInterestSaving(true);
    try {
      // Include current bid ladder values to avoid race condition with auto-save
      const response = await fetch(`/api/cases/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          interest_status: statusToSet,
          estimated_sale_price: estimatedSalePrice,
          estimated_rehab_cost: estimatedRehabCost,
          our_initial_bid: ourInitialBid,
          our_second_bid: ourSecondBid,
          our_max_bid: ourMaxBid
        })
      });

      const data = await response.json();

      if (!response.ok) {
        setInterestError(data.error || 'Failed to update');
        return;
      }

      setInterestStatus(data.interest_status || null);
    } catch (err) {
      setInterestError('Network error');
    } finally {
      setInterestSaving(false);
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
        <Link to="/" style={{ marginTop: 16, display: 'inline-block' }}>
          <Button icon={<ArrowLeftOutlined />}>Back to Dashboard</Button>
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
        <Link to={(() => {
          const params = new URLSearchParams();
          if (countyParam) params.set('county', countyParam);
          if (interestParam) params.set('interest', interestParam);
          const qs = params.toString();
          return qs ? `/?${qs}` : '/';
        })()}>
          <Button icon={<ArrowLeftOutlined />}>Back to Dashboard</Button>
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

      {/* Case Title, Status, and Property Info */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={24}>
          <Col xs={24} lg={16}>
            <Title level={4} style={{ marginTop: 0, marginBottom: 4 }}>{c.property_address || 'No address on record'}</Title>
            <div>
              <Text type="secondary">{c.county_name} County</Text>
              {daysUntilDeadline !== null && daysUntilDeadline >= 0 && (
                <Text strong style={{ color: daysUntilDeadline <= 3 ? '#ff4d4f' : '#fa8c16', marginLeft: 8 }}>
                  Deadline: {dayjs(c.next_bid_deadline).format('MMM D')} ({daysUntilDeadline}d)
                </Text>
              )}
            </div>
            {c.legal_description && (
              <div style={{ marginTop: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Legal: {c.legal_description}
                </Text>
              </div>
            )}
          </Col>

          {/* Enrichment Links */}
          <Col xs={24} lg={8}>
            <div style={{ marginTop: { xs: 12, lg: 0 } }}>
              <Text type="secondary" style={{ fontSize: 12 }}>Quick Links</Text>
              <div style={{ marginTop: 8 }}>
                <Space wrap size="small">
                  {c.case_url && (
                    <a href={c.case_url} target="_blank" rel="noopener noreferrer">
                      <Button size="small" icon={<LinkOutlined />}>
                        NC Courts
                      </Button>
                    </a>
                  )}
                  <Tooltip title={
                    c.zillow_url
                      ? `Zillow${c.zillow_zestimate ? ` (Zestimate: $${c.zillow_zestimate.toLocaleString()})` : c.zillow_price ? ` ($${c.zillow_price.toLocaleString()} S)` : ''}`
                      : c.property_address
                        ? "Search on Zillow"
                        : "No address available"
                  }>
                    <Button
                      size="small"
                      icon={<ZillowIcon size={14} style={{ opacity: (c.zillow_url || c.property_address) ? 1 : 0.4 }} />}
                      disabled={!c.zillow_url && !c.property_address}
                      onClick={() => {
                        const url = c.zillow_url || (c.property_address && formatZillowUrl(c.property_address));
                        if (url) window.open(url, '_blank');
                      }}
                    >
                      Zillow
                    </Button>
                  </Tooltip>
                  <Tooltip title={c.property_address ? "View on Google Maps" : "No address available"}>
                    <Button
                      size="small"
                      icon={<GoogleMapsIcon size={14} style={{ opacity: c.property_address ? 1 : 0.4 }} />}
                      disabled={!c.property_address}
                      onClick={() => c.property_address && window.open(formatGoogleMapsUrl(c.property_address), '_blank')}
                    >
                      Maps
                    </Button>
                  </Tooltip>
                  {c.wake_re_url && (
                    <a href={c.wake_re_url} target="_blank" rel="noopener noreferrer">
                      <Button size="small" icon={<LinkOutlined />}>
                        Wake RE
                      </Button>
                    </a>
                  )}
                  {c.durham_re_url && (
                    <a href={c.durham_re_url} target="_blank" rel="noopener noreferrer">
                      <Button size="small" icon={<LinkOutlined />}>
                        Durham RE
                      </Button>
                    </a>
                  )}
                  {c.harnett_re_url && (
                    <a href={c.harnett_re_url} target="_blank" rel="noopener noreferrer">
                      <Button size="small" icon={<LinkOutlined />}>
                        Harnett RE
                      </Button>
                    </a>
                  )}
                  {c.lee_re_url && (
                    <a href={c.lee_re_url} target="_blank" rel="noopener noreferrer">
                      <Button size="small" icon={<LinkOutlined />}>
                        Lee RE
                      </Button>
                    </a>
                  )}
                  {c.orange_re_url && (
                    <a href={c.orange_re_url} target="_blank" rel="noopener noreferrer">
                      <Button size="small" icon={<LinkOutlined />}>
                        Orange RE
                      </Button>
                    </a>
                  )}
                  {c.chatham_re_url && (
                    <a href={c.chatham_re_url} target="_blank" rel="noopener noreferrer">
                      <Button size="small" icon={<LinkOutlined />}>
                        Chatham RE
                      </Button>
                    </a>
                  )}
                  <Button size="small" icon={<LinkOutlined />} disabled>Propwire</Button>
                  {c.deed_url ? (
                    <a href={c.deed_url} target="_blank" rel="noopener noreferrer">
                      <Button size="small" icon={<FileTextOutlined />}>
                        Deed
                      </Button>
                    </a>
                  ) : (
                    <Button size="small" icon={<FileTextOutlined />} disabled>Deed</Button>
                  )}
                </Space>
              </div>
            </div>
          </Col>
        </Row>
      </Card>

      {/* Row 1: Bid Information + Team Notes side by side */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={12}>
          {/* Bid Information */}
          <Card
            title="Bid Information"
            style={{ height: '100%' }}
            extra={
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
            }
          >
            <Row gutter={16}>
              {/* Column 1: Current Bid & Min Next */}
              <Col xs={8}>
                <div style={{ marginBottom: 12 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>Current Bid</Text>
                  <div>
                    <Text strong style={{ fontSize: 18 }}>
                      {c.current_bid_amount ? `$${c.current_bid_amount.toLocaleString()}` : '-'}
                    </Text>
                  </div>
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 11 }}>Min Next Bid</Text>
                  <div>
                    <Text strong>
                      {c.minimum_next_bid ? `$${c.minimum_next_bid.toLocaleString()}` : '-'}
                    </Text>
                  </div>
                </div>
              </Col>
              {/* Column 2: Estimated Sale Price & Profit */}
              <Col xs={8}>
                <div style={{ marginBottom: 8 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>Est. Sale Price</Text>
                  <InputNumber
                    value={estimatedSalePrice}
                    onChange={setEstimatedSalePrice}
                    formatter={value => `$${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                    parser={value => value.replace(/\$\s?|(,*)/g, '')}
                    style={{ width: '100%' }}
                    size="small"
                    min={0}
                    step={1000}
                    placeholder="Est. Sale Price"
                  />
                </div>
                <div style={{ marginBottom: 8 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>Est. Rehab Cost</Text>
                  <InputNumber
                    value={estimatedRehabCost}
                    onChange={setEstimatedRehabCost}
                    formatter={value => `$${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                    parser={value => value.replace(/\$\s?|(,*)/g, '')}
                    style={{ width: '100%' }}
                    size="small"
                    min={0}
                    step={1000}
                    placeholder="Est. Rehab Cost"
                  />
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 11 }}>Est. Profit</Text>
                  <div>
                    {estimatedSalePrice && ourMaxBid ? (() => {
                      const profit = estimatedSalePrice - ourMaxBid - (estimatedRehabCost || 0);
                      return (
                        <Text strong style={{
                          fontSize: 16,
                          color: profit >= 0 ? '#52c41a' : '#ff4d4f'
                        }}>
                          {profit >= 0 ? '+' : ''}
                          ${profit.toLocaleString()}
                        </Text>
                      );
                    })() : (
                      <Text type="secondary">-</Text>
                    )}
                  </div>
                </div>
              </Col>
              {/* Column 3: Your Bid Ladder */}
              <Col xs={8}>
                <div style={{ marginBottom: 8 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>Our Initial</Text>
                  <InputNumber
                    value={ourInitialBid}
                    onChange={setOurInitialBid}
                    formatter={value => `$${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                    parser={value => value.replace(/\$\s?|(,*)/g, '')}
                    style={{ width: '100%' }}
                    size="small"
                    min={0}
                    step={100}
                    placeholder="Initial"
                  />
                </div>
                <div style={{ marginBottom: 8 }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>Our 2nd</Text>
                  <InputNumber
                    value={ourSecondBid}
                    onChange={setOurSecondBid}
                    formatter={value => `$${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                    parser={value => value.replace(/\$\s?|(,*)/g, '')}
                    style={{ width: '100%' }}
                    size="small"
                    min={0}
                    step={100}
                    placeholder="2nd"
                  />
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 11 }}>Our Max</Text>
                  <InputNumber
                    value={ourMaxBid}
                    onChange={setOurMaxBid}
                    formatter={value => `$${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                    parser={value => value.replace(/\$\s?|(,*)/g, '')}
                    style={{ width: '100%' }}
                    size="small"
                    min={0}
                    step={100}
                    placeholder="Max"
                  />
                </div>
              </Col>
            </Row>
            {bidValidationError && (
              <Alert
                type="error"
                message={bidValidationError}
                showIcon
                style={{ marginTop: 12 }}
                size="small"
              />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          {/* Team Notes - matches height of Bid Information */}
          <NotesCard
            initialNotes={teamNotes}
            onSave={handleNotesSave}
            style={{ height: '100%' }}
            interestStatus={interestStatus}
            onInterestChange={handleInterestChange}
            interestSaving={interestSaving}
            interestError={interestError}
          />
        </Col>
      </Row>

      {/* AI Analysis Section - directly under Bid Info + Notes */}
      {caseData?.classification === 'upset_bid' && (
        <div style={{ marginBottom: 16 }}>
          <AIAnalysisSection
            caseId={id}
            initialAnalysis={analysis}
            onAnalysisUpdate={setAnalysis}
          />
        </div>
      )}

      {/* Row 2: Parties, Contacts, Events */}
      <Row gutter={16}>
        <Col xs={24} lg={12}>
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
            {/* AI Extracted Defendant */}
            {analysis?.defendant_name && (
              <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px dashed #d9d9d9' }}>
                <Text type="secondary">AI Extracted: </Text>
                <Tag color="purple">{analysis.defendant_name}</Tag>
              </div>
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

        <Col xs={24} lg={12}>
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
