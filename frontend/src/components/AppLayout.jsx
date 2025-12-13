import { useState, useEffect } from 'react';
import { Layout, Menu, Avatar, Dropdown, Space, Badge } from 'antd';
import {
  DashboardOutlined,
  FileSearchOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined,
  AuditOutlined,
  HistoryOutlined
} from '@ant-design/icons';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useReview } from '../contexts/ReviewContext';

const { Header, Content } = Layout;

function AppLayout({ user }) {
  const location = useLocation();
  const [pendingCount, setPendingCount] = useState(0);
  const { refreshTrigger } = useReview();

  useEffect(() => {
    fetch('/api/review/pending-count')
      .then(res => res.json())
      .then(data => setPendingCount(data.total || 0))
      .catch(() => {});
  }, [refreshTrigger]);

  const menuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: <Link to="/">Dashboard</Link>,
    },
    {
      key: '/cases',
      icon: <FileSearchOutlined />,
      label: <Link to="/cases">All Cases</Link>,
    },
    {
      key: '/review',
      icon: <Badge count={pendingCount} size="small"><AuditOutlined /></Badge>,
      label: <Link to="/review">Review Queue</Link>,
    },
    {
      key: '/scrapes',
      icon: <HistoryOutlined />,
      label: <Link to="/scrapes">Daily Scrapes</Link>,
    },
    // Only show Admin for admin users
    ...(user?.role === 'admin' ? [{
      key: '/settings',
      icon: <SettingOutlined />,
      label: <Link to="/settings">Admin</Link>,
    }] : []),
  ];

  const userMenuItems = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Logout',
      onClick: () => {
        window.location.href = '/api/auth/logout';
      },
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{
            color: 'white',
            fontSize: '18px',
            fontWeight: 'bold',
            marginRight: '48px'
          }}>
            NC Foreclosures
          </div>
          <Menu
            theme="dark"
            mode="horizontal"
            selectedKeys={[location.pathname]}
            items={menuItems}
            style={{ minWidth: 500, border: 'none' }}
          />
        </div>
        <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
          <Space style={{ cursor: 'pointer' }}>
            <Avatar
              src={user?.avatar_url}
              icon={!user?.avatar_url && <UserOutlined />}
            />
            <span style={{ color: 'white' }}>{user?.display_name || 'User'}</span>
          </Space>
        </Dropdown>
      </Header>
      <Content style={{ background: '#f0f2f5' }}>
        <Outlet />
      </Content>
    </Layout>
  );
}

export default AppLayout;
