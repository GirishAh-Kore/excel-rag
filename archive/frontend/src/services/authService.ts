import { apiClient } from './api';
import type { LoginCredentials, AuthResponse, AuthStatus } from '../types';

export const authService = {
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const formData = new FormData();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    const response = await apiClient.post<AuthResponse>('/auth/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    if (response.data.access_token) {
      localStorage.setItem('auth_token', response.data.access_token);
    }

    return response.data;
  },

  async logout(): Promise<void> {
    try {
      await apiClient.post('/auth/logout');
    } finally {
      localStorage.removeItem('auth_token');
    }
  },

  async getStatus(): Promise<AuthStatus> {
    try {
      const response = await apiClient.get<AuthStatus>('/auth/status');
      return response.data;
    } catch (error) {
      return { authenticated: false };
    }
  },

  isAuthenticated(): boolean {
    return !!localStorage.getItem('auth_token');
  },
};
