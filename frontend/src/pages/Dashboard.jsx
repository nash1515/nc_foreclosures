import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Typography, Card, Row, Col, Table, Tag, Statistic,
  Spin, Alert, Space, Button, Tooltip, Tabs, Radio
} from 'antd';
import {
  DollarOutlined, ClockCircleOutlined, HomeOutlined,
  WarningOutlined, CheckCircleOutlined, ExclamationCircleOutlined,
  StarOutlined, StarFilled, FileTextOutlined, CloseCircleOutlined
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { formatZillowUrl, formatGoogleMapsUrl } from '../utils/urlHelpers';
import { ZillowIcon } from '../assets/ZillowIcon';
import { PropWireIcon } from '../assets/PropWireIcon';
import { GavelIcon } from '../assets/GavelIcon';
import { GoogleMapsIcon } from '../assets/GoogleMapsIcon';
import { HurricaneWarningIcon } from '../assets/HurricaneWarningIcon';

const { Title, Text } = Typography;

// Helper function to get county deed search URL based on case number suffix
const getCountyDeedSearchUrl = (caseNumber) => {
  const suffix = caseNumber?.slice(-3);
  const searchUrls = {
    '910': 'https://rodrecords.wake.gov/web/web/integration/search',
    '310': 'https://rodweb.dconc.gov/web/search/DOCSEARCH5S1',
    '420': 'https://us6.courthousecomputersystems.com/HarnettNC/',
    '520': 'https://www.leencrod.org/search.wgx',
    '670': 'https://rod.orangecountync.gov/',
    '180': 'https://www.chathamnc.org/government/departments-programs-i-z/register-of-deeds',
  };
  return searchUrls[suffix] || null;
};

// Color scheme for urgency levels
const urgencyColors = {
  expired: { bg: '#fff1f0', border: '#ffa39e', text: '#cf1322', tag: 'error' },
  critical: { bg: '#fff7e6', border: '#ffd591', text: '#d46b08', tag: 'warning' },
  warning: { bg: '#fffbe6', border: '#ffe58f', text: '#d4b106', tag: 'gold' },
  normal: { bg: '#f6ffed', border: '#b7eb8f', text: '#389e0d', tag: 'success' }
};

// Color scheme for classifications
const classificationColors = {
  upset_bid: { color: '#fa541c', bg: '#fff2e8' },
  upcoming: { color: '#1890ff', bg: '#e6f7ff' },
  blocked: { color: '#faad14', bg: '#fffbe6' },
  closed_sold: { color: '#52c41a', bg: '#f6ffed' },
  closed_dismissed: { color: '#8c8c8c', bg: '#fafafa' }
};

// County tabs - key matches county_name from API
const COUNTY_TABS = [
  { key: 'all', label: 'All' },
  { key: 'Wake', label: 'Wake' },
  { key: 'Durham', label: 'Durham' },
  { key: 'Harnett', label: 'Harnett' },
  { key: 'Lee', label: 'Lee' },
  { key: 'Orange', label: 'Orange' },
  { key: 'Chatham', label: 'Chatham' }
];

// Interest status filter options
const INTEREST_FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'interested', label: 'Interested' },
  { key: 'needs_review', label: 'Needs Review' }
];

function Dashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [stats, setStats] = useState(null);
  const [allUpsetBids, setAllUpsetBids] = useState([]);  // All bids for counting
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedCounty, setSelectedCounty] = useState(() => {
    const countyParam = searchParams.get('county');
    return countyParam && COUNTY_TABS.some(t => t.key === countyParam) ? countyParam : 'all';
  });
  const [interestFilter, setInterestFilter] = useState(() => {
    const interestParam = searchParams.get('interest');
    return interestParam && INTEREST_FILTERS.some(f => f.key === interestParam) ? interestParam : 'all';
  });

  // Update URL when filters change
  const updateSearchParams = (county, interest) => {
    const params = {};
    if (county !== 'all') params.county = county;
    if (interest !== 'all') params.interest = interest;
    setSearchParams(params);
  };

  const handleCountyChange = (county) => {
    setSelectedCounty(county);
    updateSearchParams(county, interestFilter);
  };

  const handleInterestChange = (e) => {
    const interest = e.target.value;
    setInterestFilter(interest);
    updateSearchParams(selectedCounty, interest);
  };

  useEffect(() => {
    fetchData();
  }, []);  // Only fetch once on mount

  const fetchData = async () => {
    try {
      setLoading(true);

      // Always fetch all data (no county filter) to get counts for tabs
      const [statsRes, upsetRes] = await Promise.all([
        fetch('/api/cases/stats', { credentials: 'include' }),
        fetch('/api/cases/upset-bids', { credentials: 'include' })
      ]);

      if (!statsRes.ok || !upsetRes.ok) {
        throw new Error('Failed to fetch data');
      }

      const statsData = await statsRes.json();
      const upsetData = await upsetRes.json();

      setStats(statsData);
      setAllUpsetBids(upsetData.cases || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Filter bids by selected county first (for interest counts)
  const countyFilteredBids = selectedCounty === 'all'
    ? allUpsetBids
    : allUpsetBids.filter(bid => bid.county_name === selectedCounty);

  // Filter bids by selected county and interest status (client-side)
  const filteredBids = countyFilteredBids.filter(bid => {
    // Interest filter
    if (interestFilter === 'all') {
      return true;
    }
    if (interestFilter === 'interested' && bid.interest_status !== 'interested') {
      return false;
    }
    if (interestFilter === 'needs_review' && bid.interest_status !== null) {
      return false;
    }
    return true;
  });

  // Count bids per county for tab labels
  const countsByCounty = allUpsetBids.reduce((acc, bid) => {
    acc[bid.county_name] = (acc[bid.county_name] || 0) + 1;
    return acc;
  }, {});

  // Count bids by interest status for filter labels (filtered by selected county)
  const countsByInterest = {
    all: countyFilteredBids.length,
    interested: countyFilteredBids.filter(b => b.interest_status === 'interested').length,
    needs_review: countyFilteredBids.filter(b => b.interest_status === null).length
  };

  const toggleWatchlist = async (caseId, isWatchlisted) => {
    try {
      const method = isWatchlisted ? 'DELETE' : 'POST';
      await fetch(`/api/cases/${caseId}/watchlist`, {
        method,
        credentials: 'include'
      });
      // Refresh data
      fetchData();
    } catch (err) {
      console.error('Failed to update watchlist:', err);
    }
  };

  const formatCurrency = (amount) => {
    if (!amount) return '-';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  const getUrgencyIcon = (urgency) => {
    switch (urgency) {
      case 'expired':
        return <ExclamationCircleOutlined style={{ color: urgencyColors.expired.text }} />;
      case 'critical':
        return <WarningOutlined style={{ color: urgencyColors.critical.text }} />;
      case 'warning':
        return <ClockCircleOutlined style={{ color: urgencyColors.warning.text }} />;
      default:
        return <CheckCircleOutlined style={{ color: urgencyColors.normal.text }} />;
    }
  };

  const columns = [
    {
      title: '#',
      key: 'rowNumber',
      width: 50,
      align: 'center',
      render: (_, record, index) => index + 1
    },
    {
      title: '',
      key: 'watchlist',
      width: 40,
      render: (_, record) => (
        <Button
          type="text"
          size="small"
          icon={record.is_watchlisted ?
            <StarFilled style={{ color: '#faad14' }} /> :
            <StarOutlined />
          }
          onClick={() => toggleWatchlist(record.id, record.is_watchlisted)}
        />
      )
    },
    {
      title: 'Urgency',
      key: 'urgency',
      width: 110,
      render: (_, record) => {
        const colors = urgencyColors[record.urgency] || urgencyColors.normal;
        return (
          <div style={{
            background: colors.bg,
            border: `1px solid ${colors.border}`,
            borderRadius: 4,
            padding: '2px 6px',
            textAlign: 'center'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
              {getUrgencyIcon(record.urgency)}
              <Text strong style={{ color: colors.text, fontSize: 13 }}>
                {record.days_remaining === null ? 'No deadline' :
                 record.urgency === 'expired' ? 'EXPIRED' :
                 record.days_remaining === 0 ? 'TODAY' :
                 record.days_remaining === 1 ? '1 day' :
                 `${record.days_remaining} days`}
              </Text>
            </div>
          </div>
        );
      }
    },
    {
      title: 'Bid Deadline',
      key: 'deadline',
      width: 110,
      render: (_, record) => (
        <Text>
          {record.next_bid_deadline ? dayjs(record.next_bid_deadline).format('MMM D, YYYY') : '-'}
        </Text>
      )
    },
    {
      title: 'Case',
      key: 'case',
      width: 140,
      render: (_, record) => {
        const params = new URLSearchParams();
        if (selectedCounty !== 'all') params.set('county', selectedCounty);
        if (interestFilter !== 'all') params.set('interest', interestFilter);
        const queryString = params.toString();
        return (
        <div>
          <Link to={`/cases/${record.id}${queryString ? `?${queryString}` : ''}`} style={{ fontWeight: 500 }}>
            {record.case_number}
          </Link>
          <div>
            <Tag color="blue" style={{ marginTop: 2 }}>{record.county_name}</Tag>
          </div>
        </div>
      );
      }
    },
    {
      title: 'Type',
      key: 'type',
      width: 80,
      align: 'center',
      render: (_, record) => {
        const typeConfig = {
          'Mortgage': { label: 'MTG', color: 'default' },
          'HOA': { label: 'HOA', color: 'orange' },
          'Estate': { label: 'EST', color: 'purple' }
        };
        const config = typeConfig[record.foreclosure_type] || typeConfig['Mortgage'];
        return (
          <Tag color={config.color}>
            {config.label}
          </Tag>
        );
      }
    },
    {
      title: 'Property Address',
      dataIndex: 'property_address',
      key: 'property',
      render: (address) => (
        <div style={{ maxWidth: 300 }}>
          <HomeOutlined style={{ marginRight: 8, color: '#8c8c8c' }} />
          {address || 'Address not available'}
        </div>
      )
    },
    {
      title: 'Max Bid',
      key: 'max_bid',
      align: 'right',
      width: 100,
      render: (_, record) => (
        <Text strong style={{ color: record.our_max_bid ? '#52c41a' : '#8c8c8c' }}>
          {record.our_max_bid ? formatCurrency(record.our_max_bid) : '-'}
        </Text>
      )
    },
    {
      title: 'Est. Sale',
      key: 'estimated_sale_price',
      align: 'right',
      width: 100,
      render: (_, record) => (
        <Text style={{ color: record.estimated_sale_price ? '#1890ff' : '#8c8c8c' }}>
          {record.estimated_sale_price ? formatCurrency(record.estimated_sale_price) : '-'}
        </Text>
      )
    },
    {
      title: 'Est. Profit',
      key: 'estimated_profit',
      align: 'right',
      width: 100,
      render: (_, record) => {
        if (!record.estimated_profit && record.estimated_profit !== 0) {
          return <Text style={{ color: '#8c8c8c' }}>-</Text>;
        }
        const isPositive = record.estimated_profit >= 0;
        return (
          <Text strong style={{ color: isPositive ? '#52c41a' : '#ff4d4f' }}>
            {isPositive ? '+' : ''}{formatCurrency(record.estimated_profit)}
          </Text>
        );
      }
    },
    {
      title: 'Min Next Bid',
      key: 'min_next_bid',
      align: 'right',
      width: 120,
      render: (_, record) => (
        <Text style={{ color: '#52c41a' }}>
          {formatCurrency(record.minimum_next_bid)}
        </Text>
      )
    },
    {
      title: 'Review',
      key: 'review_status',
      width: 60,
      align: 'center',
      render: (_, record) => {
        if (record.interest_status === 'interested') {
          return (
            <Tooltip title="Interested">
              <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 18 }} />
            </Tooltip>
          );
        } else if (record.interest_status === 'not_interested') {
          return (
            <Tooltip title="Not Interested">
              <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 18 }} />
            </Tooltip>
          );
        } else {
          return (
            <Tooltip title="Not Reviewed">
              <HurricaneWarningIcon size={18} style={{ display: 'block', margin: '0 auto' }} />
            </Tooltip>
          );
        }
      }
    },
    {
      title: 'Links',
      key: 'quicklinks',
      width: 120,
      render: (_, record) => {
        const hasAddress = record.property_address;
        const hasCaseUrl = record.case_url;

        return (
          <Space size="small">
            <Tooltip title={hasCaseUrl ? "NC Courts Portal" : "No court link available"}>
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  if (hasCaseUrl) window.open(record.case_url, '_blank');
                }}
                style={{
                  cursor: hasCaseUrl ? 'pointer' : 'not-allowed',
                  opacity: hasCaseUrl ? 1 : 0.4,
                  display: 'inline-flex',
                  alignItems: 'center'
                }}
              >
                <GavelIcon size={16} />
              </span>
            </Tooltip>

            <Tooltip title={hasAddress ? "Search on Zillow" : "No address available"}>
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  if (hasAddress) window.open(formatZillowUrl(record.property_address), '_blank');
                }}
                style={{
                  cursor: hasAddress ? 'pointer' : 'not-allowed',
                  opacity: hasAddress ? 1 : 0.4,
                  display: 'inline-flex',
                  alignItems: 'center'
                }}
              >
                <ZillowIcon size={16} />
              </span>
            </Tooltip>

            <Tooltip title={hasAddress ? "View on Google Maps" : "No address available"}>
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  if (hasAddress) window.open(formatGoogleMapsUrl(record.property_address), '_blank');
                }}
                style={{
                  cursor: hasAddress ? 'pointer' : 'not-allowed',
                  opacity: hasAddress ? 1 : 0.4,
                  display: 'inline-flex',
                  alignItems: 'center'
                }}
              >
                <GoogleMapsIcon size={16} />
              </span>
            </Tooltip>

            <Tooltip title="PropWire - Coming soon">
              <span style={{ cursor: 'not-allowed', opacity: 0.4, display: 'inline-flex', alignItems: 'center' }}>
                <PropWireIcon size={16} />
              </span>
            </Tooltip>

            <Tooltip title={record.deed_url ? "View Deed Record" : "Search County Deeds"}>
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  const deedUrl = record.deed_url || getCountyDeedSearchUrl(record.case_number);
                  if (deedUrl) window.open(deedUrl, '_blank');
                }}
                style={{
                  cursor: 'pointer',
                  opacity: 1,
                  display: 'inline-flex',
                  alignItems: 'center'
                }}
              >
                <FileTextOutlined style={{ fontSize: 16 }} />
              </span>
            </Tooltip>

            <Tooltip title={
              record.wake_re_url ? "Wake County Property" :
              record.durham_re_url ? "Durham County Property" :
              record.harnett_re_url ? "Harnett County Property" :
              record.lee_re_url ? "Lee County Property" :
              record.orange_re_url ? "Orange County Property" :
              record.chatham_re_url ? "Chatham County Property" :
              "Coming soon"
            }>
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  const url = record.wake_re_url || record.durham_re_url || record.harnett_re_url || record.lee_re_url || record.orange_re_url || record.chatham_re_url;
                  if (url) window.open(url, '_blank');
                }}
                style={{
                  cursor: (record.wake_re_url || record.durham_re_url || record.harnett_re_url || record.lee_re_url || record.orange_re_url || record.chatham_re_url) ? 'pointer' : 'not-allowed',
                  opacity: (record.wake_re_url || record.durham_re_url || record.harnett_re_url || record.lee_re_url || record.orange_re_url || record.chatham_re_url) ? 1 : 0.4,
                  display: 'inline-flex',
                  alignItems: 'center'
                }}
              >
                <HomeOutlined style={{ fontSize: 16 }} />
              </span>
            </Tooltip>
          </Space>
        );
      }
    }
  ];

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>Loading dashboard...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <Alert type="error" message="Error" description={error} showIcon />
      </div>
    );
  }

  // Calculate percentages for progress bars
  const upsetPercent = stats ? Math.round((stats.upset_bid?.total / stats.total_cases) * 100) : 0;

  return (
    <div style={{ padding: 18 }}>
      <div style={{ marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Upset Bid Dashboard</Title>
      </div>

      {/* Stats Cards */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Total Cases"
              value={stats?.total_cases || 0}
              prefix={<HomeOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={{ background: classificationColors.upset_bid.bg }}>
            <Statistic
              title="Active Upset Bids"
              value={stats?.upset_bid?.total || 0}
              valueStyle={{ color: classificationColors.upset_bid.color }}
              prefix={<DollarOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={{ background: urgencyColors.critical.bg }}>
            <Statistic
              title="Urgent (< 3 days)"
              value={stats?.upset_bid?.urgent || 0}
              valueStyle={{ color: urgencyColors.critical.text }}
              prefix={<WarningOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Recent Filings (7 days)"
              value={stats?.recent_filings || 0}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* County Tabs with Upset Bid Table */}
      <Card bodyStyle={{ padding: 0 }}>
        <Tabs
          activeKey={selectedCounty}
          onChange={handleCountyChange}
          style={{ marginBottom: 0 }}
          tabBarStyle={{ marginBottom: 0, paddingLeft: 16, paddingRight: 16 }}
          items={COUNTY_TABS.map(tab => ({
            key: tab.key,
            label: tab.key === 'all'
              ? `All (${allUpsetBids.length})`
              : `${tab.label} (${countsByCounty[tab.key] || 0})`
          }))}
        />
        <div style={{ padding: 12 }}>
          {/* Interest Status Filter */}
          <div style={{ marginBottom: 12 }}>
            <Space>
              <Text type="secondary">Filter by review status:</Text>
              <Radio.Group
                value={interestFilter}
                onChange={handleInterestChange}
                optionType="button"
                buttonStyle="solid"
                size="small"
              >
                {INTEREST_FILTERS.map(filter => (
                  <Radio.Button key={filter.key} value={filter.key}>
                    {filter.label} ({countsByInterest[filter.key]})
                  </Radio.Button>
                ))}
              </Radio.Group>
            </Space>
          </div>
          {filteredBids.length === 0 ? (
            <Alert
              type="info"
              message="No Matching Cases"
              description={
                interestFilter !== 'all'
                  ? `No ${interestFilter === 'interested' ? 'interested' : 'unreviewed'} cases${selectedCounty !== 'all' ? ` in ${selectedCounty} County` : ''}.`
                  : selectedCounty === 'all'
                    ? "There are currently no cases in the upset bid period."
                    : `There are currently no active upset bids in ${selectedCounty} County.`
              }
              showIcon
            />
          ) : (
            <Table
              dataSource={filteredBids}
              columns={columns}
              rowKey="id"
              pagination={false}
              size="small"
              rowClassName={(record) => {
                if (record.urgency === 'expired') return 'row-expired';
                if (record.urgency === 'critical') return 'row-critical';
                return '';
              }}
            />
          )}
        </div>
      </Card>

      <style>{`
        .row-expired {
          background-color: ${urgencyColors.expired.bg} !important;
        }
        .row-critical {
          background-color: ${urgencyColors.critical.bg} !important;
        }
        .row-expired:hover td, .row-critical:hover td {
          background: inherit !important;
        }
      `}</style>
    </div>
  );
}

export default Dashboard;
