import { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  DatePicker,
  Space,
  Typography,
  Tag,
  Collapse,
  message,
  Dropdown,
  Popconfirm
} from 'antd';
import {
  CheckOutlined,
  CloseOutlined,
  PlusOutlined,
  DeleteOutlined,
  DownOutlined
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  getDailyReview,
  approveAllForeclosures,
  approveForeclosures,
  rejectForeclosures,
  addSkippedCases,
  dismissSkippedCases
} from '../api/review';

const { Title, Text } = Typography;

export default function ReviewQueue() {
  const [date, setDate] = useState(dayjs());
  const [data, setData] = useState({ foreclosures: [], skipped: [], counts: {} });
  const [loading, setLoading] = useState(true);
  const [selectedForeclosures, setSelectedForeclosures] = useState([]);
  const [selectedSkipped, setSelectedSkipped] = useState([]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const result = await getDailyReview(date.format('YYYY-MM-DD'));
      setData(result);
      setSelectedForeclosures([]);
      setSelectedSkipped([]);
    } catch (error) {
      message.error('Failed to load review data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [date]);

  const handleApproveAll = async () => {
    try {
      const result = await approveAllForeclosures(date.format('YYYY-MM-DD'));
      message.success(`Approved ${result.approved} foreclosure(s)`);
      fetchData();
    } catch (error) {
      message.error('Failed to approve all foreclosures');
    }
  };

  const handleApproveSelected = async () => {
    if (selectedForeclosures.length === 0) return;
    try {
      const result = await approveForeclosures(selectedForeclosures);
      message.success(`Approved ${result.approved} case(s)`);
      fetchData();
    } catch (error) {
      message.error('Failed to approve cases');
    }
  };

  const handleRejectSelected = async () => {
    if (selectedForeclosures.length === 0) return;
    try {
      await rejectForeclosures(selectedForeclosures);
      message.success(`Rejected ${selectedForeclosures.length} case(s)`);
      fetchData();
    } catch (error) {
      message.error('Failed to reject cases');
    }
  };

  const handleAddSelected = async () => {
    if (selectedSkipped.length === 0) return;
    try {
      const result = await addSkippedCases(selectedSkipped);
      message.success(`Added ${result.added} case(s)`);
      fetchData();
    } catch (error) {
      message.error('Failed to add cases');
    }
  };

  const handleDismissSelected = async () => {
    if (selectedSkipped.length === 0) return;
    try {
      await dismissSkippedCases(selectedSkipped);
      message.success(`Dismissed ${selectedSkipped.length} case(s)`);
      fetchData();
    } catch (error) {
      message.error('Failed to dismiss cases');
    }
  };

  const handleDismissAll = async () => {
    const allIds = data.skipped.map(s => s.id);
    if (allIds.length === 0) return;
    try {
      await dismissSkippedCases(allIds);
      message.success(`Dismissed all ${allIds.length} skipped case(s)`);
      fetchData();
    } catch (error) {
      message.error('Failed to dismiss cases');
    }
  };

  const foreclosureColumns = [
    {
      title: 'Case Number',
      dataIndex: 'case_number',
      key: 'case_number',
      render: (text, record) => (
        <a href={record.case_url} target="_blank" rel="noopener noreferrer">
          {text}
        </a>
      )
    },
    {
      title: 'County',
      dataIndex: 'county_name',
      key: 'county_name'
    },
    {
      title: 'Case Type',
      dataIndex: 'case_type',
      key: 'case_type',
      ellipsis: true
    },
    {
      title: 'Style',
      dataIndex: 'style',
      key: 'style',
      ellipsis: true
    },
    {
      title: 'File Date',
      dataIndex: 'file_date',
      key: 'file_date'
    },
    {
      title: 'Action',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Button
            type="primary"
            icon={<CheckOutlined />}
            size="small"
            onClick={async () => {
              try {
                await approveForeclosures([record.id]);
                message.success('Case approved');
                fetchData();
              } catch (error) {
                message.error('Failed to approve case');
              }
            }}
          >
            Approve
          </Button>
          <Popconfirm
            title="Reject this case?"
            description="This will delete the case from the database."
            onConfirm={async () => {
              try {
                await rejectForeclosures([record.id]);
                message.success('Case rejected');
                fetchData();
              } catch (error) {
                message.error('Failed to reject case');
              }
            }}
          >
            <Button danger icon={<CloseOutlined />} size="small">
              Reject
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ];

  const skippedColumns = [
    {
      title: 'Case Number',
      dataIndex: 'case_number',
      key: 'case_number',
      render: (text, record) => (
        <a href={record.case_url} target="_blank" rel="noopener noreferrer">
          {text}
        </a>
      )
    },
    {
      title: 'County',
      dataIndex: 'county_name',
      key: 'county_name'
    },
    {
      title: 'Case Type',
      dataIndex: 'case_type',
      key: 'case_type',
      ellipsis: true
    },
    {
      title: 'Reason',
      dataIndex: 'skip_reason',
      key: 'skip_reason',
      ellipsis: true,
      render: (text) => <Tag color="orange">{text}</Tag>
    },
    {
      title: 'Action',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            size="small"
            onClick={async () => {
              try {
                await addSkippedCases([record.id]);
                message.success('Case added');
                fetchData();
              } catch (error) {
                message.error('Failed to add case');
              }
            }}
          >
            Add
          </Button>
          <Button
            icon={<DeleteOutlined />}
            size="small"
            onClick={async () => {
              try {
                await dismissSkippedCases([record.id]);
                message.success('Case dismissed');
                fetchData();
              } catch (error) {
                message.error('Failed to dismiss case');
              }
            }}
          >
            Dismiss
          </Button>
        </Space>
      )
    }
  ];

  const expandedRowRender = (record) => (
    <div style={{ padding: '8px 0' }}>
      <Text strong>Events:</Text>
      <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
        {record.events?.map((event, idx) => (
          <li key={idx}>
            {event.event_date} - {event.event_type || '(no type)'}
            {event.document_title && (
              <Text type="secondary"> (Doc: {event.document_title})</Text>
            )}
          </li>
        ))}
        {(!record.events || record.events.length === 0) && (
          <li><Text type="secondary">No events</Text></li>
        )}
      </ul>
    </div>
  );

  const foreclosureBulkMenu = {
    items: [
      {
        key: 'approveAll',
        label: 'Approve All',
        icon: <CheckOutlined />,
        disabled: data.foreclosures.length === 0,
        onClick: handleApproveAll
      },
      {
        key: 'approveSelected',
        label: `Approve Selected (${selectedForeclosures.length})`,
        icon: <CheckOutlined />,
        disabled: selectedForeclosures.length === 0,
        onClick: handleApproveSelected
      },
      { type: 'divider' },
      {
        key: 'reject',
        label: `Reject Selected (${selectedForeclosures.length})`,
        icon: <CloseOutlined />,
        danger: true,
        disabled: selectedForeclosures.length === 0,
        onClick: handleRejectSelected
      }
    ]
  };

  const skippedBulkMenu = {
    items: [
      {
        key: 'add',
        label: `Add Selected (${selectedSkipped.length})`,
        icon: <PlusOutlined />,
        disabled: selectedSkipped.length === 0,
        onClick: handleAddSelected
      },
      {
        key: 'dismiss',
        label: `Dismiss Selected (${selectedSkipped.length})`,
        icon: <DeleteOutlined />,
        disabled: selectedSkipped.length === 0,
        onClick: handleDismissSelected
      },
      { type: 'divider' },
      {
        key: 'dismissAll',
        label: 'Dismiss All',
        icon: <DeleteOutlined />,
        danger: true,
        disabled: data.skipped.length === 0,
        onClick: handleDismissAll
      }
    ]
  };

  const collapseItems = [
    {
      key: 'foreclosures',
      label: (
        <Space>
          <CheckOutlined style={{ color: '#52c41a' }} />
          <span>Foreclosures ({data.counts.foreclosures || 0} cases)</span>
        </Space>
      ),
      extra: (
        <Dropdown menu={foreclosureBulkMenu} trigger={['click']}>
          <Button onClick={(e) => e.stopPropagation()}>
            Bulk Actions <DownOutlined />
          </Button>
        </Dropdown>
      ),
      children: (
        <Table
          rowKey="id"
          columns={foreclosureColumns}
          dataSource={data.foreclosures}
          loading={loading}
          pagination={{ pageSize: 10 }}
          expandable={{ expandedRowRender }}
          rowSelection={{
            selectedRowKeys: selectedForeclosures,
            onChange: setSelectedForeclosures
          }}
          size="small"
        />
      )
    },
    {
      key: 'skipped',
      label: (
        <Space>
          <CloseOutlined style={{ color: '#faad14' }} />
          <span>Skipped ({data.counts.skipped || 0} cases)</span>
        </Space>
      ),
      extra: (
        <Dropdown menu={skippedBulkMenu} trigger={['click']}>
          <Button onClick={(e) => e.stopPropagation()}>
            Bulk Actions <DownOutlined />
          </Button>
        </Dropdown>
      ),
      children: (
        <Table
          rowKey="id"
          columns={skippedColumns}
          dataSource={data.skipped}
          loading={loading}
          pagination={{ pageSize: 10 }}
          expandable={{ expandedRowRender }}
          rowSelection={{
            selectedRowKeys: selectedSkipped,
            onChange: setSelectedSkipped
          }}
          size="small"
        />
      )
    }
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={2} style={{ margin: 0 }}>Review Queue</Title>
        <DatePicker
          value={date}
          onChange={(d) => d && setDate(d)}
          allowClear={false}
        />
      </div>

      <Collapse defaultActiveKey={['foreclosures', 'skipped']} items={collapseItems} />
    </div>
  );
}
