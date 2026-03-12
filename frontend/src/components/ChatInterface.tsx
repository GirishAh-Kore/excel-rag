import { useState } from 'react';
import { Box, Alert } from '@mui/material';
import MessageList from './MessageList';
import QueryInput from './QueryInput';
import { chatService } from '../services/chatService';
import type { Message } from '../types';

interface ChatInterfaceProps {
  sessionId: string | null;
  messages: Message[];
  onMessagesUpdate: (messages: Message[]) => void;
}

const ChatInterface = ({ sessionId, messages, onMessagesUpdate }: ChatInterfaceProps) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmitQuery = async (query: string) => {
    setLoading(true);
    setError(null);

    // Add user message immediately
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: query,
      timestamp: new Date().toISOString(),
    };

    onMessagesUpdate([...messages, userMessage]);

    try {
      const response = await chatService.submitQuery({
        query,
        session_id: sessionId || undefined,
      });

      // Add assistant message
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.answer,
        timestamp: new Date().toISOString(),
        sources: response.sources,
        confidence: response.confidence,
      };

      onMessagesUpdate([...messages, userMessage, assistantMessage]);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to process query';
      setError(errorMessage);

      // Remove the user message on error
      onMessagesUpdate(messages);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        flexGrow: 1,
      }}
    >
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ m: 2 }}>
          {error}
        </Alert>
      )}

      <MessageList messages={messages} />
      <QueryInput onSubmit={handleSubmitQuery} loading={loading} />
    </Box>
  );
};

export default ChatInterface;
