import { apiClient } from './api';
import type { QueryRequest, QueryResponse, Session, Message } from '../types';

export const chatService = {
  async submitQuery(request: QueryRequest): Promise<QueryResponse> {
    const response = await apiClient.post<QueryResponse>('/query', request);
    return response.data;
  },

  async getSessions(): Promise<Session[]> {
    const response = await apiClient.get<Session[]>('/chat/sessions');
    return response.data;
  },

  async createSession(): Promise<Session> {
    const response = await apiClient.post<Session>('/chat/sessions');
    return response.data;
  },

  async deleteSession(sessionId: string): Promise<void> {
    await apiClient.delete(`/chat/sessions/${sessionId}`);
  },

  async getSessionHistory(sessionId: string): Promise<Message[]> {
    const response = await apiClient.get<Message[]>(`/chat/sessions/${sessionId}/history`);
    return response.data;
  },

  async submitFeedback(queryId: string, feedback: 'positive' | 'negative'): Promise<void> {
    await apiClient.post('/query/feedback', { query_id: queryId, feedback });
  },
};
