import axios from 'axios';
import { apiClient } from './api';
import type { QueryRequest, QueryResponse, Session, Message } from '../types';

// Chat sessions API is at /api/chat, not /api/v1/chat
const CHAT_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace('/api/v1', '/api') || 'http://localhost:8000/api';

const chatClient = axios.create({
  baseURL: CHAT_BASE_URL,
  timeout: 30000,
});

// Add auth token to requests
chatClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 errors by redirecting to login
chatClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const chatService = {
  // Query endpoint is at /api/v1/query - use apiClient
  async submitQuery(request: QueryRequest): Promise<QueryResponse> {
    const response = await apiClient.post<QueryResponse>('/query', request);
    return response.data;
  },

  // Chat session endpoints are at /api/chat - use chatClient
  async getSessions(): Promise<Session[]> {
    const response = await chatClient.get<{ sessions: Session[]; total: number }>('/chat/sessions');
    return response.data.sessions;
  },

  async createSession(): Promise<Session> {
    const response = await chatClient.post<Session>('/chat/sessions');
    return response.data;
  },

  async deleteSession(sessionId: string): Promise<void> {
    await chatClient.delete(`/chat/sessions/${sessionId}`);
  },

  async getSessionHistory(sessionId: string): Promise<Message[]> {
    const response = await chatClient.get<Message[]>(`/chat/sessions/${sessionId}/history`);
    return response.data;
  },

  // Feedback is at /api/v1/query/feedback - use apiClient
  async submitFeedback(queryId: string, feedback: 'positive' | 'negative'): Promise<void> {
    await apiClient.post('/query/feedback', { query_id: queryId, feedback });
  },
};
