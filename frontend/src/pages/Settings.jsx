import React, { useState, useEffect } from 'react';
import {
  Card,
  DatePicker,
  Checkbox,
  Input,
  Button,
  message,
  Space,
  Typography,
  Row,
  Col,
  Divider,
  Table,
  Modal,
  Form,
  Select,
  Popconfirm,
  Tag,
  Radio
} from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const ALL_COUNTIES = ['WAKE', 'DURHAM', 'HARNETT', 'LEE', 'ORANGE', 'CHATHAM'];

export default function Settings() {
  // Manual Scrape State
  const [scrapeMode, setScrapeMode] = useState('date_range'); // 'date_range' or 'case_monitor'
  const [monitorClassification, setMonitorClassification] = useState('upset_bid'); // 'upset_bid' or 'upcoming'
  const [dateRange, setDateRange] = useState([null, null]);
  const [selectedCounties, setSelectedCounties] = useState(ALL_COUNTIES);
  const [partyName, setPartyName] = useState('');
  const [scrapeLoading, setScrapeLoading] = useState(false);
  const [scrapeResult, setScrapeResult] = useState(null);

  // User Management State
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [addForm] = Form.useForm();

  // Fetch users on mount
  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    setUsersLoading(true);
    try {
      const res = await fetch('/api/admin/users', { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setUsers(data);
      }
    } catch (err) {
      message.error('Failed to load users');
    } finally {
      setUsersLoading(false);
    }
  };

  // County selection handlers
  const handleSelectAll = () => setSelectedCounties(ALL_COUNTIES);
  const handleClearAll = () => setSelectedCounties([]);
  const handleCountyChange = (county, checked) => {
    if (checked) {
      setSelectedCounties([...selectedCounties, county]);
    } else {
      setSelectedCounties(selectedCounties.filter(c => c !== county));
    }
  };

  // Manual scrape handler
  const handleRunScrape = async () => {
    if (scrapeMode === 'date_range') {
      if (!dateRange[0] || !dateRange[1]) {
        message.error('Please select a date range');
        return;
      }
      if (selectedCounties.length === 0) {
        message.error('Please select at least one county');
        return;
      }
    }

    setScrapeLoading(true);
    setScrapeResult(null);

    try {
      const endpoint = scrapeMode === 'case_monitor' ? '/api/admin/monitor' : '/api/admin/scrape';
      const payload = scrapeMode === 'case_monitor'
        ? { classification: monitorClassification }
        : {
            start_date: dateRange[0].format('YYYY-MM-DD'),
            end_date: dateRange[1].format('YYYY-MM-DD'),
            counties: selectedCounties,
            party_name: partyName || undefined
          };

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      setScrapeResult(data);

      if (data.status === 'success') {
        const countText = scrapeMode === 'case_monitor'
          ? `${data.cases_updated || 0} cases updated`
          : `${data.cases_processed} cases processed`;
        message.success(`Complete: ${countText}`);
      } else {
        message.error(data.error || 'Operation failed');
      }
    } catch (err) {
      message.error('Failed to run operation');
      setScrapeResult({ status: 'failed', error: err.message });
    } finally {
      setScrapeLoading(false);
    }
  };

  // User management handlers
  const handleAddUser = async (values) => {
    try {
      const res = await fetch('/api/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(values)
      });

      if (res.ok) {
        message.success('User added');
        setAddModalVisible(false);
        addForm.resetFields();
        fetchUsers();
      } else {
        const data = await res.json();
        message.error(data.error || 'Failed to add user');
      }
    } catch (err) {
      message.error('Failed to add user');
    }
  };

  const handleRoleChange = async (userId, newRole) => {
    try {
      const res = await fetch(`/api/admin/users/${userId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ role: newRole })
      });

      if (res.ok) {
        message.success('Role updated');
        fetchUsers();
      } else {
        const data = await res.json();
        message.error(data.error || 'Failed to update role');
      }
    } catch (err) {
      message.error('Failed to update role');
    }
  };

  const handleDeleteUser = async (userId) => {
    try {
      const res = await fetch(`/api/admin/users/${userId}`, {
        method: 'DELETE',
        credentials: 'include'
      });

      if (res.ok) {
        message.success('User removed');
        fetchUsers();
      } else {
        const data = await res.json();
        message.error(data.error || 'Failed to remove user');
      }
    } catch (err) {
      message.error('Failed to remove user');
    }
  };

  const userColumns = [
    { title: 'Email', dataIndex: 'email', key: 'email' },
    {
      title: 'Role',
      dataIndex: 'role',
      key: 'role',
      render: (role, record) => (
        <Select
          value={role}
          onChange={(value) => handleRoleChange(record.id, value)}
          style={{ width: 100 }}
          options={[
            { value: 'admin', label: 'Admin' },
            { value: 'user', label: 'User' }
          ]}
        />
      )
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Popconfirm
          title="Remove this user?"
          onConfirm={() => handleDeleteUser(record.id)}
          okText="Yes"
          cancelText="No"
        >
          <Button type="text" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      )
    }
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>Admin</Title>

      {/* Manual Scrape Section */}
      <Card title="Manual Scrape" style={{ marginBottom: 24 }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {/* Mode Selection */}
          <div>
            <Text strong>Mode:</Text>
            <div style={{ marginTop: 8 }}>
              <Radio.Group value={scrapeMode} onChange={(e) => setScrapeMode(e.target.value)}>
                <Radio value="date_range">Date Range Scrape</Radio>
                <Radio value="case_monitor">Case Monitor</Radio>
              </Radio.Group>
            </div>
          </div>

          {/* Case Monitor Options */}
          {scrapeMode === 'case_monitor' && (
            <div>
              <Text strong>Monitor Classification:</Text>
              <div style={{ marginTop: 8 }}>
                <Radio.Group value={monitorClassification} onChange={(e) => setMonitorClassification(e.target.value)}>
                  <Radio value="upset_bid">Dashboard Cases (upset_bid)</Radio>
                  <Radio value="upcoming">All Upcoming Cases</Radio>
                </Radio.Group>
              </div>
            </div>
          )}

          {/* Date Range Scrape Options */}
          {scrapeMode === 'date_range' && (
            <>
              {/* Date Range */}
              <div>
                <Text strong>Date Range:</Text>
                <div style={{ marginTop: 8 }}>
                  <RangePicker
                    value={dateRange}
                    onChange={setDateRange}
                    format="YYYY-MM-DD"
                  />
                </div>
              </div>

              {/* Counties */}
              <div>
                <Text strong>Counties:</Text>
                <div style={{ marginTop: 8, marginBottom: 8 }}>
                  <Space>
                    <Button size="small" onClick={handleSelectAll}>Select All</Button>
                    <Button size="small" onClick={handleClearAll}>Clear All</Button>
                  </Space>
                </div>
                <Row gutter={[16, 8]}>
                  {ALL_COUNTIES.map(county => (
                    <Col span={8} key={county}>
                      <Checkbox
                        checked={selectedCounties.includes(county)}
                        onChange={(e) => handleCountyChange(county, e.target.checked)}
                      >
                        {county.charAt(0) + county.slice(1).toLowerCase()}
                      </Checkbox>
                    </Col>
                  ))}
                </Row>
              </div>

              {/* Party Name */}
              <div>
                <Text strong>Party Name:</Text>
                <Text type="secondary" style={{ marginLeft: 8 }}>(optional)</Text>
                <div style={{ marginTop: 8 }}>
                  <Input
                    placeholder="Enter party name to search"
                    value={partyName}
                    onChange={(e) => setPartyName(e.target.value)}
                    style={{ maxWidth: 400 }}
                  />
                </div>
              </div>
            </>
          )}

          {/* Run Button */}
          <Button
            type="primary"
            onClick={handleRunScrape}
            loading={scrapeLoading}
            disabled={scrapeLoading}
          >
            {scrapeLoading ? (scrapeMode === 'case_monitor' ? 'Running Monitor...' : 'Running Scrape...') : (scrapeMode === 'case_monitor' ? 'Run Monitor' : 'Run Scrape')}
          </Button>

          {/* Results */}
          {scrapeResult && (
            <div style={{ marginTop: 16, padding: 16, background: scrapeResult.status === 'success' ? '#f6ffed' : '#fff2f0', borderRadius: 4 }}>
              <Text strong>Result: </Text>
              <Tag color={scrapeResult.status === 'success' ? 'green' : 'red'}>
                {scrapeResult.status}
              </Tag>
              {scrapeResult.cases_processed !== undefined && (
                <Text>Cases processed: {scrapeResult.cases_processed}</Text>
              )}
              {scrapeResult.cases_checked !== undefined && (
                <div style={{ marginTop: 8 }}>
                  <div><Text>Cases checked: {scrapeResult.cases_checked}</Text></div>
                  {scrapeResult.events_added !== undefined && (
                    <div><Text>Events added: {scrapeResult.events_added}</Text></div>
                  )}
                  {scrapeResult.classifications_changed !== undefined && (
                    <div><Text>Classifications changed: {scrapeResult.classifications_changed}</Text></div>
                  )}
                  {scrapeResult.bid_updates !== undefined && (
                    <div><Text>Bid updates: {scrapeResult.bid_updates}</Text></div>
                  )}
                  {scrapeResult.errors !== undefined && scrapeResult.errors > 0 && (
                    <div><Text type="warning">Errors: {scrapeResult.errors}</Text></div>
                  )}
                </div>
              )}
              {scrapeResult.error && (
                <div style={{ marginTop: 8 }}>
                  <Text type="danger">{scrapeResult.error}</Text>
                </div>
              )}
            </div>
          )}
        </Space>
      </Card>

      {/* User Management Section */}
      <Card
        title="User Management"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setAddModalVisible(true)}
          >
            Add User
          </Button>
        }
      >
        <Table
          dataSource={users}
          columns={userColumns}
          rowKey="id"
          loading={usersLoading}
          pagination={false}
        />
      </Card>

      {/* Add User Modal */}
      <Modal
        title="Add User"
        open={addModalVisible}
        onCancel={() => setAddModalVisible(false)}
        footer={null}
      >
        <Form
          form={addForm}
          onFinish={handleAddUser}
          layout="vertical"
          initialValues={{ role: 'user' }}
        >
          <Form.Item
            name="email"
            label="Email"
            rules={[
              { required: true, message: 'Please enter email' },
              { type: 'email', message: 'Please enter a valid email' }
            ]}
          >
            <Input placeholder="user@example.com" />
          </Form.Item>
          <Form.Item
            name="role"
            label="Role"
          >
            <Select
              options={[
                { value: 'user', label: 'User' },
                { value: 'admin', label: 'Admin' }
              ]}
            />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">Add User</Button>
              <Button onClick={() => setAddModalVisible(false)}>Cancel</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
