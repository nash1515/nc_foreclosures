import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Typography, Card, Row, Col, Table, Tag, Statistic,
  Spin, Alert, Progress, Space, Button, Select, Tooltip
} from 'antd';
import {
  DollarOutlined, ClockCircleOutlined, HomeOutlined,
  WarningOutlined, CheckCircleOutlined, ExclamationCircleOutlined,
  StarOutlined, StarFilled, FileTextOutlined
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { formatZillowUrl } from '../utils/urlHelpers';
import { ZillowIcon } from '../assets/ZillowIcon';
import { PropWireIcon } from '../assets/PropWireIcon';

const { Title, Text } = Typography;

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

// County options
const COUNTIES = [
  { label: 'All Counties', value: 'all' },
  { label: 'Wake', value: '910' },
  { label: 'Durham', value: '310' },
  { label: 'Harnett', value: '420' },
  { label: 'Lee', value: '520' },
  { label: 'Orange', value: '670' },
  { label: 'Chatham', value: '180' }
];

function Dashboard() {
  const [stats, setStats] = useState(null);
  const [upsetBids, setUpsetBids] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedCounty, setSelectedCounty] = useState('all');

  useEffect(() => {
    fetchData();
  }, [selectedCounty]);

  const fetchData = async () => {
    try {
      setLoading(true);

      // Build query params for county filter
      const countyParam = selectedCounty !== 'all' ? `?county=${selectedCounty}` : '';

      const [statsRes, upsetRes] = await Promise.all([
        fetch(`/api/cases/stats${countyParam}`, { credentials: 'include' }),
        fetch(`/api/cases/upset-bids${countyParam}`, { credentials: 'include' })
      ]);

      if (!statsRes.ok || !upsetRes.ok) {
        throw new Error('Failed to fetch data');
      }

      const statsData = await statsRes.json();
      const upsetData = await upsetRes.json();

      setStats(statsData);
      setUpsetBids(upsetData.cases || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
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
            padding: '4px 8px',
            textAlign: 'center'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
              {getUrgencyIcon(record.urgency)}
              <Text strong style={{ color: colors.text }}>
                {record.days_remaining === null ? 'No bid deadline' :
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
      render: (_, record) => (
        <div>
          <Link to={`/cases/${record.id}`} style={{ fontWeight: 500 }}>
            {record.case_number}
          </Link>
          <div>
            <Tag color="blue" style={{ marginTop: 4 }}>{record.county_name}</Tag>
          </div>
        </div>
      )
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
      title: 'Current Bid',
      key: 'current_bid',
      align: 'right',
      width: 120,
      render: (_, record) => (
        <Text strong style={{ color: '#52c41a' }}>
          {formatCurrency(record.current_bid_amount)}
        </Text>
      )
    },
    {
      title: 'Min Next Bid',
      key: 'min_next_bid',
      align: 'right',
      width: 120,
      render: (_, record) => (
        <Text style={{ color: '#fa8c16' }}>
          {formatCurrency(record.minimum_next_bid)}
        </Text>
      )
    },
    {
      title: 'Links',
      key: 'quicklinks',
      width: 120,
      render: (_, record) => {
        const hasAddress = record.property_address;

        return (
          <Space size="small">
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

            <Tooltip title="PropWire - Coming soon">
              <span style={{ cursor: 'not-allowed', opacity: 0.4, display: 'inline-flex', alignItems: 'center' }}>
                <PropWireIcon size={16} />
              </span>
            </Tooltip>

            <Tooltip title="Deed - Coming soon">
              <span style={{ cursor: 'not-allowed', opacity: 0.4, display: 'inline-flex', alignItems: 'center' }}>
                <FileTextOutlined style={{ fontSize: 16 }} />
              </span>
            </Tooltip>

            <Tooltip title="Property Info - Coming soon">
              <span style={{ cursor: 'not-allowed', opacity: 0.4, display: 'inline-flex', alignItems: 'center' }}>
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
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={2} style={{ margin: 0 }}>Upset Bid Dashboard</Title>
      </div>

      {/* Stats Cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
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

      {/* Upset Bid Cases Table */}
      <Card
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>
              <DollarOutlined style={{ marginRight: 8, color: '#fa541c' }} />
              Active Upset Bid Opportunities ({upsetBids.length})
            </span>
            <Space>
              <Text style={{ marginRight: 8 }}>Filter by County:</Text>
              <Select
                value={selectedCounty}
                onChange={setSelectedCounty}
                options={COUNTIES}
                style={{ width: 160 }}
                loading={loading}
              />
            </Space>
          </div>
        }
      >
        {upsetBids.length === 0 ? (
          <Alert
            type="info"
            message="No Active Upset Bids"
            description="There are currently no cases in the upset bid period. Check back later for new opportunities."
            showIcon
          />
        ) : (
          <Table
            dataSource={upsetBids}
            columns={columns}
            rowKey="id"
            pagination={false}
            size="middle"
            rowClassName={(record) => {
              if (record.urgency === 'expired') return 'row-expired';
              if (record.urgency === 'critical') return 'row-critical';
              return '';
            }}
          />
        )}
      </Card>

      {/* Classification Breakdown */}
      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} lg={12}>
          <Card title="Case Classifications" size="small">
            <Space direction="vertical" style={{ width: '100%' }}>
              {stats?.classifications && Object.entries(stats.classifications)
                .sort((a, b) => b[1] - a[1])
                .map(([classification, count]) => {
                  const colors = classificationColors[classification] || { color: '#8c8c8c', bg: '#fafafa' };
                  const percent = Math.round((count / stats.total_cases) * 100);
                  return (
                    <div key={classification}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <Tag color={colors.color} style={{ margin: 0 }}>
                          {classification || 'unclassified'}
                        </Tag>
                        <Text>{count.toLocaleString()} ({percent}%)</Text>
                      </div>
                      <Progress
                        percent={percent}
                        showInfo={false}
                        strokeColor={colors.color}
                        size="small"
                      />
                    </div>
                  );
                })}
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="Cases by County" size="small">
            <Space direction="vertical" style={{ width: '100%' }}>
              {stats?.counties && Object.entries(stats.counties)
                .sort((a, b) => b[1] - a[1])
                .map(([county, count]) => {
                  const percent = Math.round((count / stats.total_cases) * 100);
                  return (
                    <div key={county}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <Text>{county}</Text>
                        <Text>{count.toLocaleString()} ({percent}%)</Text>
                      </div>
                      <Progress
                        percent={percent}
                        showInfo={false}
                        strokeColor="#1890ff"
                        size="small"
                      />
                    </div>
                  );
                })}
            </Space>
          </Card>
        </Col>
      </Row>

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
