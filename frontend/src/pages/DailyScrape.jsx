import { useState, useEffect } from 'react';
import {
  Typography, Card, Table, Tag, Spin, Alert, Space, Button, Collapse
} from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined,
  ReloadOutlined, ExclamationCircleOutlined
} from '@ant-design/icons';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';

dayjs.extend(relativeTime);

const { Title, Text } = Typography;

function DailyScrape() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retrying, setRetrying] = useState(null);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/scheduler/history?limit=30', {
        credentials: 'include'
      });

      if (!response.ok) {
        throw new Error('Failed to fetch scrape history');
      }

      const data = await response.json();
      setHistory(data.history || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const formatDuration = (startedAt, completedAt) => {
    if (!startedAt || !completedAt) return '-';
    const start = dayjs(startedAt);
    const end = dayjs(completedAt);
    const diffSeconds = end.diff(start, 'second');
    const hours = Math.floor(diffSeconds / 3600);
    const minutes = Math.floor((diffSeconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  };

  const handleRetry = async (targetDate) => {
    try {
      setRetrying(targetDate);
      const response = await fetch('/api/scheduler/run/daily_scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ target_date: targetDate })
      });

      if (!response.ok) {
        throw new Error('Failed to trigger scrape');
      }

      // Refresh history after a short delay
      setTimeout(fetchHistory, 2000);
    } catch (err) {
      console.error('Retry failed:', err);
    } finally {
      setRetrying(null);
    }
  };

  // Separate failed scrapes from last 7 days
  const recentFailures = history.filter(item => {
    const isRecent = dayjs(item.started_at).isAfter(dayjs().subtract(7, 'day'));
    return item.status === 'failed' && isRecent;
  });

  const columns = [
    {
      title: 'Date',
      key: 'date',
      width: 120,
      render: (_, record) => (
        <div>
          <Text strong>{dayjs(record.start_date).format('MMM D, YYYY')}</Text>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {dayjs(record.start_date).format('ddd')}
            </Text>
          </div>
        </div>
      )
    },
    {
      title: 'Status',
      key: 'status',
      width: 100,
      render: (_, record) => {
        if (record.status === 'success') {
          return (
            <Tag icon={<CheckCircleOutlined />} color="success">
              Success
            </Tag>
          );
        } else if (record.status === 'failed') {
          return (
            <Tag icon={<CloseCircleOutlined />} color="error">
              Failed
            </Tag>
          );
        } else if (record.status === 'partial') {
          return (
            <Tag icon={<ExclamationCircleOutlined />} color="warning">
              Partial
            </Tag>
          );
        }
        return <Tag>{record.status}</Tag>;
      }
    },
    {
      title: 'Cases Found',
      dataIndex: 'cases_processed',
      key: 'cases',
      width: 100,
      align: 'center',
      render: (val) => val ?? '-'
    },
    {
      title: 'Duration',
      key: 'duration',
      width: 100,
      render: (_, record) => (
        <Space>
          <ClockCircleOutlined style={{ color: '#8c8c8c' }} />
          {formatDuration(record.started_at, record.completed_at)}
        </Space>
      )
    },
    {
      title: 'Started',
      key: 'started',
      width: 160,
      render: (_, record) => (
        <div>
          <Text>{dayjs(record.started_at).format('MMM D, h:mm A')}</Text>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {dayjs(record.started_at).fromNow()}
            </Text>
          </div>
        </div>
      )
    },
    {
      title: 'Error',
      dataIndex: 'error_message',
      key: 'error',
      render: (error) => error ? (
        <Text type="danger" style={{ fontSize: 12 }}>
          {error.length > 80 ? `${error.substring(0, 80)}...` : error}
        </Text>
      ) : null
    }
  ];

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>Loading scrape history...</div>
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

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={2} style={{ margin: 0 }}>Daily Scrapes</Title>
        <Button icon={<ReloadOutlined />} onClick={fetchHistory}>
          Refresh
        </Button>
      </div>

      {/* Error Alert Section */}
      {recentFailures.length > 0 && (
        <Alert
          type="error"
          showIcon
          icon={<ExclamationCircleOutlined />}
          style={{ marginBottom: 24 }}
          message={
            <Text strong>
              {recentFailures.length} failed scrape{recentFailures.length > 1 ? 's' : ''} in the last 7 days
            </Text>
          }
          description={
            <Collapse
              ghost
              items={[
                {
                  key: '1',
                  label: 'View failed scrapes',
                  children: (
                    <div style={{ marginTop: 8 }}>
                      {recentFailures.map((item) => (
                        <div
                          key={item.id}
                          style={{
                            padding: '8px 12px',
                            background: '#fff1f0',
                            borderRadius: 4,
                            marginBottom: 8,
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center'
                          }}
                        >
                          <div>
                            <Text strong>
                              {dayjs(item.start_date).format('MMM D, YYYY')}
                            </Text>
                            <Text type="secondary" style={{ marginLeft: 12 }}>
                              {dayjs(item.started_at).format('h:mm A')}
                            </Text>
                            {item.error_message && (
                              <div style={{ marginTop: 4 }}>
                                <Text type="danger" style={{ fontSize: 12 }}>
                                  {item.error_message}
                                </Text>
                              </div>
                            )}
                          </div>
                          <Button
                            size="small"
                            type="primary"
                            danger
                            loading={retrying === item.start_date}
                            onClick={() => handleRetry(item.start_date)}
                          >
                            Retry
                          </Button>
                        </div>
                      ))}
                    </div>
                  )
                }
              ]}
            />
          }
        />
      )}

      {/* History Table */}
      <Card title={`Scrape History (Last ${history.length} scrapes)`}>
        <Table
          dataSource={history}
          columns={columns}
          rowKey="id"
          pagination={{ pageSize: 14, showSizeChanger: false }}
          size="middle"
          rowClassName={(record) => {
            if (record.status === 'failed') return 'row-failed';
            if (record.status === 'partial') return 'row-partial';
            return '';
          }}
        />
      </Card>

      <style>{`
        .row-failed {
          background-color: #fff1f0 !important;
        }
        .row-partial {
          background-color: #fffbe6 !important;
        }
        .row-failed:hover td, .row-partial:hover td {
          background: inherit !important;
        }
      `}</style>
    </div>
  );
}

export default DailyScrape;
