import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  Button,
  CircularProgress,
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import LogoutIcon from '@mui/icons-material/Logout';
import ConversationSidebar from '../components/ConversationSidebar';
import ChatInterface from '../components/ChatInterface';
import { chatService } from '../services/chatService';
import { useAuth } from '../hooks/useAuth';
import type { Session, Message } from '../types';

const ChatPage = () => {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    if (currentSessionId) {
      loadSessionHistory(currentSessionId);
    }
  }, [currentSessionId]);

  const loadSessions = async () => {
    try {
      const data = await chatService.getSessions();
      setSessions(data);
      if (data.length > 0 && !currentSessionId) {
        setCurrentSessionId(data[0].session_id);
      }
    } catch (err) {
      console.error('Failed to load sessions:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadSessionHistory = async (sessionId: string) => {
    try {
      const history = await chatService.getSessionHistory(sessionId);
      setMessages(history);
    } catch (err) {
      console.error('Failed to load session history:', err);
      setMessages([]);
    }
  };

  const handleNewSession = async () => {
    try {
      const newSession = await chatService.createSession();
      setSessions([newSession, ...sessions]);
      setCurrentSessionId(newSession.session_id);
      setMessages([]);
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  };

  const handleSelectSession = (sessionId: string) => {
    setCurrentSessionId(sessionId);
  };

  const handleDeleteSession = async (sessionId: string) => {
    if (!confirm('Are you sure you want to delete this conversation?')) return;

    try {
      await chatService.deleteSession(sessionId);
      setSessions(sessions.filter((s) => s.session_id !== sessionId));
      if (currentSessionId === sessionId) {
        const remaining = sessions.filter((s) => s.session_id !== sessionId);
        setCurrentSessionId(remaining.length > 0 ? remaining[0].session_id : null);
        setMessages([]);
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="100vh">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Excel RAG System
          </Typography>
          <Button
            color="inherit"
            startIcon={<SettingsIcon />}
            onClick={() => navigate('/config')}
            sx={{ display: { xs: 'none', sm: 'flex' } }}
          >
            Config
          </Button>
          <Button
            color="inherit"
            startIcon={<LogoutIcon />}
            onClick={handleLogout}
            sx={{ display: { xs: 'none', sm: 'flex' } }}
          >
            Logout
          </Button>
          {/* Mobile menu icons */}
          <Box sx={{ display: { xs: 'flex', sm: 'none' }, gap: 1 }}>
            <Button color="inherit" onClick={() => navigate('/config')}>
              <SettingsIcon />
            </Button>
            <Button color="inherit" onClick={handleLogout}>
              <LogoutIcon />
            </Button>
          </Box>
        </Toolbar>
      </AppBar>

      <Box sx={{ display: 'flex', flexGrow: 1, overflow: 'hidden' }}>
        <Box sx={{ display: { xs: 'none', md: 'block' } }}>
          <ConversationSidebar
            sessions={sessions}
            currentSessionId={currentSessionId}
            onSelectSession={handleSelectSession}
            onNewSession={handleNewSession}
            onDeleteSession={handleDeleteSession}
          />
        </Box>
        <ChatInterface
          sessionId={currentSessionId}
          messages={messages}
          onMessagesUpdate={setMessages}
        />
      </Box>
    </Box>
  );
};

export default ChatPage;
