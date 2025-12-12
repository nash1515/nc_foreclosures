import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, Spin } from 'antd';
import { useState, useEffect } from 'react';
import { ReviewProvider } from './contexts/ReviewContext';
import AppLayout from './components/AppLayout';
import Dashboard from './pages/Dashboard';
import CaseList from './pages/CaseList';
import CaseDetail from './pages/CaseDetail';
import ReviewQueue from './pages/ReviewQueue';
import DailyScrape from './pages/DailyScrape';
import Settings from './pages/Settings';
import Login from './pages/Login';
import './App.css';

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if user is authenticated
    fetch('/api/auth/me')
      .then(res => {
        if (res.ok) return res.json();
        throw new Error('Not authenticated');
      })
      .then(data => {
        setUser(data);
        setLoading(false);
      })
      .catch(() => {
        setUser(null);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh'
      }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#1890ff',
        },
      }}
    >
      <ReviewProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={
              user ? <Navigate to="/" replace /> : <Login />
            } />
            <Route element={
              user ? <AppLayout user={user} /> : <Navigate to="/login" replace />
            }>
              <Route path="/" element={<Dashboard />} />
              <Route path="/cases" element={<CaseList />} />
              <Route path="/cases/:id" element={<CaseDetail />} />
              <Route path="/review" element={<ReviewQueue />} />
              <Route path="/scrapes" element={<DailyScrape />} />
              <Route path="/settings" element={<Settings />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ReviewProvider>
    </ConfigProvider>
  );
}

export default App;
