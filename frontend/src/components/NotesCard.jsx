import { useState, useCallback } from 'react';
import { Card, Input, Typography, Space, Button, Divider } from 'antd';
import { CheckCircleOutlined, LoadingOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { useAutoSave } from '../hooks/useAutoSave';

const { TextArea } = Input;
const { Text } = Typography;

/**
 * NotesCard - Auto-saving team notes for a case with interest status
 *
 * @param {string} initialNotes - Initial notes value from API
 * @param {Function} onSave - Async function to save notes (receives notes string)
 * @param {Object} style - Optional style override for the card
 * @param {string} interestStatus - Current interest status ('interested', 'not_interested', or null)
 * @param {Function} onInterestChange - Callback when interest status changes
 * @param {boolean} interestSaving - Whether interest status is currently saving
 * @param {string} interestError - Error message for interest status validation
 */
function NotesCard({
  initialNotes,
  onSave,
  style,
  interestStatus,
  onInterestChange,
  interestSaving,
  interestError
}) {
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

      {/* Interest Status Section */}
      {onInterestChange && (
        <>
          <Divider style={{ margin: '16px 0 12px 0' }} />
          <Space size="middle" align="center">
            <Text strong>Interested?</Text>
            <Button
              type={interestStatus === 'interested' ? 'primary' : 'default'}
              style={interestStatus === 'interested' ? {
                backgroundColor: '#52c41a',
                borderColor: '#52c41a'
              } : {}}
              onClick={() => onInterestChange('interested')}
              loading={interestSaving}
              size="small"
            >
              Yes
            </Button>
            <Button
              type={interestStatus === 'not_interested' ? 'primary' : 'default'}
              danger={interestStatus === 'not_interested'}
              onClick={() => onInterestChange('not_interested')}
              loading={interestSaving}
              size="small"
            >
              No
            </Button>
            {interestError && (
              <Text type="danger" style={{ fontSize: 12 }}>{interestError}</Text>
            )}
          </Space>
        </>
      )}
    </Card>
  );
}

export default NotesCard;
