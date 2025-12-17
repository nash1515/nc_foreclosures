import { useState, useEffect } from 'react';
import {
  Typography, Card, Table, Tag, Spin, Alert, Space, Button, Collapse, Progress
} from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined,
  ReloadOutlined, ExclamationCircleOutlined, DownOutlined, RightOutlined
} from '@ant-design/icons';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';

dayjs.extend(relativeTime);

const { Title, Text } = Typography;

// Human-readable task names
const TASK_LABELS = {
  'new_case_search': 'New Case Search',
  'ocr_after_search': 'OCR Processing (Search)',
  'case_monitoring': 'Case Monitoring',
  'ocr_after_monitoring': 'OCR Processing (Monitor)',
  'upset_bid_validation': 'Upset Bid Validation',
  'stale_reclassification': 'Stale Reclassification',
  'self_diagnosis': 'Self-Diagnosis'
};

function DailyScrape() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retrying, setRetrying] = useState(null);
  const [acknowledging, setAcknowledging] = useState(null);

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
    const seconds = diffSeconds % 60;
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    }
    return `${seconds}s`;
  };

  // Render task breakdown for expandable row
  const renderTaskBreakdown = (record) => {
    const tasks = record.tasks || [];
    if (tasks.length === 0) {
      return <Text type="secondary">No task details available</Text>;
    }

    return (
      <div style={{ padding: '8px 16px', background: '#fafafa' }}>
        <Text strong style={{ marginBottom: 12, display: 'block' }}>Task Breakdown</Text>
        <div style={{ display: 'grid', gap: 8 }}>
          {tasks.map((task) => {
            const taskLabel = TASK_LABELS[task.task_name] || task.task_name;
            const duration = formatDuration(task.started_at, task.completed_at);
            const statusColor = task.status === 'success' ? '#52c41a' :
              task.status === 'failed' ? '#ff4d4f' : '#faad14';

            return (
              <div
                key={task.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '8px 12px',
                  background: '#fff',
                  borderRadius: 4,
                  borderLeft: `3px solid ${statusColor}`
                }}
              >
                <div style={{ flex: 1 }}>
                  <Text strong>{taskLabel}</Text>
                </div>
                <div style={{ textAlign: 'right', minWidth: 100 }}>
                  {task.items_checked != null && (
                    <Text type="secondary" style={{ marginRight: 16 }}>
                      Checked: {task.items_checked}
                    </Text>
                  )}
                  {task.items_found != null && task.items_found > 0 && (
                    <Text type="secondary" style={{ marginRight: 16 }}>
                      Found: {task.items_found}
                    </Text>
                  )}
                  {task.items_processed != null && task.items_processed > 0 && (
                    <Text style={{ color: '#1890ff', marginRight: 16 }}>
                      Processed: {task.items_processed}
                    </Text>
                  )}
                </div>
                <div style={{ minWidth: 60, textAlign: 'right' }}>
                  <Text type="secondary">{duration}</Text>
                </div>
                <div style={{ minWidth: 20 }}>
                  {task.status === 'success' ? (
                    <CheckCircleOutlined style={{ color: '#52c41a' }} />
                  ) : task.status === 'failed' ? (
                    <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                  ) : (
                    <ClockCircleOutlined style={{ color: '#faad14' }} />
                  )}
                </div>
              </div>
            );
          })}
        </div>
        {tasks.some(t => t.error_message) && (
          <div style={{ marginTop: 12 }}>
            {tasks.filter(t => t.error_message).map(t => (
              <Text key={t.id} type="danger" style={{ display: 'block', fontSize: 12 }}>
                {TASK_LABELS[t.task_name]}: {t.error_message}
              </Text>
            ))}
          </div>
        )}
      </div>
    );
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

  const handleAcknowledge = async (logId) => {
    try {
      setAcknowledging(logId);
      const response = await fetch(`/api/scheduler/acknowledge/${logId}`, {
        method: 'POST',
        credentials: 'include'
      });

      if (!response.ok) {
        throw new Error('Failed to acknowledge scrape');
      }

      // Refresh history to update the UI
      fetchHistory();
    } catch (err) {
      console.error('Acknowledge failed:', err);
    } finally {
      setAcknowledging(null);
    }
  };

  // Separate unacknowledged failed scrapes from last 7 days
  const recentFailures = history.filter(item => {
    const isRecent = dayjs(item.started_at).isAfter(dayjs().subtract(7, 'day'));
    const isUnacknowledged = !item.acknowledged_at;
    return item.status === 'failed' && isRecent && isUnacknowledged;
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
                          <Space>
                            <Button
                              size="small"
                              type="primary"
                              danger
                              loading={retrying === item.start_date}
                              onClick={() => handleRetry(item.start_date)}
                            >
                              Retry
                            </Button>
                            <Button
                              size="small"
                              loading={acknowledging === item.id}
                              onClick={() => handleAcknowledge(item.id)}
                            >
                              Dismiss
                            </Button>
                          </Space>
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
          expandable={{
            expandedRowRender: renderTaskBreakdown,
            rowExpandable: (record) => record.tasks && record.tasks.length > 0,
            expandIcon: ({ expanded, onExpand, record }) => {
              if (!record.tasks || record.tasks.length === 0) {
                return <span style={{ width: 24, display: 'inline-block' }} />;
              }
              return expanded ? (
                <DownOutlined
                  style={{ cursor: 'pointer', color: '#1890ff' }}
                  onClick={(e) => onExpand(record, e)}
                />
              ) : (
                <RightOutlined
                  style={{ cursor: 'pointer', color: '#1890ff' }}
                  onClick={(e) => onExpand(record, e)}
                />
              );
            }
          }}
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
