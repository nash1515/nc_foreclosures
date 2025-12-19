import { useState, useCallback } from 'react';
import { Card, Input, Typography, Space } from 'antd';
import { CheckCircleOutlined, LoadingOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { useAutoSave } from '../hooks/useAutoSave';

const { TextArea } = Input;
const { Text } = Typography;

/**
 * NotesCard - Auto-saving team notes for a case
 *
 * @param {string} initialNotes - Initial notes value from API
 * @param {Function} onSave - Async function to save notes (receives notes string)
 * @param {Object} style - Optional style override for the card
 */
function NotesCard({ initialNotes, onSave, style }) {
  const [notes, setNotes] = useState(initialNotes || '');

  // Memoize save function to prevent re-renders
  const handleSave = useCallback(async (value) => {
    await onSave({ team_notes: value });
  }, [onSave]);

  const { saveState, error } = useAutoSave(handleSave, notes);

  return (
    <Card
      title="Team Notes"
      extra={
        <Space size={4}>
          {saveState === 'saving' && (
            <>
              <LoadingOutlined style={{ color: '#1890ff' }} />
              <Text type="secondary" style={{ fontSize: 12 }}>Saving...</Text>
            </>
          )}
          {saveState === 'saved' && (
            <>
              <CheckCircleOutlined style={{ color: '#52c41a' }} />
              <Text type="success" style={{ fontSize: 12 }}>Saved</Text>
            </>
          )}
          {saveState === 'error' && (
            <>
              <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
              <Text type="danger" style={{ fontSize: 12 }}>Save failed</Text>
            </>
          )}
        </Space>
      }
      style={{ marginBottom: 16, ...style }}
    >
      <TextArea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Add notes about property condition, research findings, strategy..."
        autoSize={{ minRows: 4, maxRows: 20 }}
        style={{ fontSize: 14 }}
      />
      {error && (
        <Text type="danger" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
          {error}
        </Text>
      )}
    </Card>
  );
}

export default NotesCard;
