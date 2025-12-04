import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Typography, Table, Input, Select, DatePicker, Space, Tag, Button, Switch, message
} from 'antd';
import { StarOutlined, StarFilled, SearchOutlined } from '@ant-design/icons';
import { fetchCases, addToWatchlist, removeFromWatchlist } from '../api/cases';
import dayjs from 'dayjs';

const { Title } = Typography;
const { RangePicker } = DatePicker;

// County options
const COUNTIES = [
  { value: '180', label: 'Chatham' },
  { value: '310', label: 'Durham' },
  { value: '420', label: 'Harnett' },
  { value: '520', label: 'Lee' },
  { value: '670', label: 'Orange' },
  { value: '910', label: 'Wake' },
];

// Classification options with colors
const CLASSIFICATIONS = [
  { value: 'upcoming', label: 'Upcoming', color: 'blue' },
  { value: 'upset_bid', label: 'Upset Bid', color: 'red' },
  { value: 'blocked', label: 'Blocked', color: 'orange' },
  { value: 'closed_sold', label: 'Closed (Sold)', color: 'green' },
  { value: 'closed_dismissed', label: 'Closed (Dismissed)', color: 'default' },
];

function CaseList() {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [sorter, setSorter] = useState({ field: 'file_date', order: 'descend' });

  // Filters
  const [search, setSearch] = useState('');
  const [classification, setClassification] = useState([]);
  const [county, setCounty] = useState([]);
  const [dateRange, setDateRange] = useState(null);
  const [watchlistOnly, setWatchlistOnly] = useState(false);

  const loadCases = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchCases({
        page: pagination.current,
        pageSize: pagination.pageSize,
        classification: classification.join(','),
        county: county.join(','),
        search,
        startDate: dateRange?.[0]?.format('YYYY-MM-DD') || '',
        endDate: dateRange?.[1]?.format('YYYY-MM-DD') || '',
        watchlistOnly,
        sortBy: sorter.field || 'file_date',
        sortOrder: sorter.order === 'ascend' ? 'asc' : 'desc'
      });
      setCases(result.cases);
      setTotal(result.total);
    } catch (error) {
      message.error('Failed to load cases');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [pagination, classification, county, search, dateRange, watchlistOnly, sorter]);

  useEffect(() => {
    loadCases();
  }, [loadCases]);

  const handleTableChange = (newPagination, filters, newSorter) => {
    setPagination({
      current: newPagination.current,
      pageSize: newPagination.pageSize
    });
    if (newSorter.field) {
      setSorter({
        field: newSorter.field,
        order: newSorter.order
      });
    }
  };

  const handleSearch = (value) => {
    setSearch(value);
    setPagination(prev => ({ ...prev, current: 1 }));
  };

  const handleWatchlistToggle = async (caseId, currentlyWatchlisted) => {
    try {
      if (currentlyWatchlisted) {
        await removeFromWatchlist(caseId);
        message.success('Removed from watchlist');
      } else {
        await addToWatchlist(caseId);
        message.success('Added to watchlist');
      }
      // Update local state
      setCases(prev => prev.map(c =>
        c.id === caseId ? { ...c, is_watchlisted: !currentlyWatchlisted } : c
      ));
    } catch (error) {
      message.error('Failed to update watchlist');
    }
  };

  const columns = [
    {
      title: '',
      dataIndex: 'is_watchlisted',
      key: 'watchlist',
      width: 50,
      render: (isWatchlisted, record) => (
        <Button
          type="text"
          icon={isWatchlisted ? <StarFilled style={{ color: '#faad14' }} /> : <StarOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            handleWatchlistToggle(record.id, isWatchlisted);
          }}
        />
      )
    },
    {
      title: 'Case Number',
      dataIndex: 'case_number',
      key: 'case_number',
      sorter: true,
      render: (text, record) => (
        <Link to={`/cases/${record.id}`}>{text}</Link>
      )
    },
    {
      title: 'Style',
      dataIndex: 'style',
      key: 'style',
      ellipsis: true,
      width: 300
    },
    {
      title: 'County',
      dataIndex: 'county_name',
      key: 'county_name',
      sorter: true,
      width: 100
    },
    {
      title: 'Classification',
      dataIndex: 'classification',
      key: 'classification',
      width: 140,
      render: (value) => {
        const config = CLASSIFICATIONS.find(c => c.value === value);
        return config ? (
          <Tag color={config.color}>{config.label}</Tag>
        ) : (
          <Tag>{value || 'Unknown'}</Tag>
        );
      }
    },
    {
      title: 'File Date',
      dataIndex: 'file_date',
      key: 'file_date',
      sorter: true,
      width: 110,
      render: (date) => date ? dayjs(date).format('MM/DD/YYYY') : '-'
    },
    {
      title: 'Current Bid',
      dataIndex: 'current_bid_amount',
      key: 'current_bid_amount',
      sorter: true,
      width: 120,
      align: 'right',
      render: (amount) => amount ? `$${amount.toLocaleString()}` : '-'
    },
    {
      title: 'Deadline',
      dataIndex: 'next_bid_deadline',
      key: 'next_bid_deadline',
      sorter: true,
      width: 110,
      render: (date) => date ? dayjs(date).format('MM/DD/YYYY') : '-'
    }
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>All Cases</Title>

      {/* Filters */}
      <Space wrap style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="Search case #, address, party..."
          allowClear
          onSearch={handleSearch}
          style={{ width: 280 }}
          prefix={<SearchOutlined />}
        />

        <Select
          mode="multiple"
          placeholder="Classification"
          style={{ minWidth: 180 }}
          value={classification}
          onChange={(value) => {
            setClassification(value);
            setPagination(prev => ({ ...prev, current: 1 }));
          }}
          options={CLASSIFICATIONS.map(c => ({ value: c.value, label: c.label }))}
          allowClear
        />

        <Select
          mode="multiple"
          placeholder="County"
          style={{ minWidth: 150 }}
          value={county}
          onChange={(value) => {
            setCounty(value);
            setPagination(prev => ({ ...prev, current: 1 }));
          }}
          options={COUNTIES}
          allowClear
        />

        <RangePicker
          value={dateRange}
          onChange={(dates) => {
            setDateRange(dates);
            setPagination(prev => ({ ...prev, current: 1 }));
          }}
          format="MM/DD/YYYY"
          placeholder={['Start Date', 'End Date']}
        />

        <Space>
          <span>Watchlist Only:</span>
          <Switch
            checked={watchlistOnly}
            onChange={(checked) => {
              setWatchlistOnly(checked);
              setPagination(prev => ({ ...prev, current: 1 }));
            }}
          />
        </Space>
      </Space>

      {/* Table */}
      <Table
        columns={columns}
        dataSource={cases}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          total,
          showSizeChanger: true,
          showTotal: (total) => `${total} cases`
        }}
        onChange={handleTableChange}
        size="middle"
      />
    </div>
  );
}

export default CaseList;
