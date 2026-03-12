import axios from 'axios';
import type { LoginCredentials, AuthResponse, AuthStatus } from '../types';

// Use separate base URL for auth endpoints (they're at /api/auth, not /api/v1/auth)
const AUTH_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace('/api/v1', '/api') || 'http://localhost:8000/api';

const authClient = axios.create({
  baseURL: AUTH_BASE_URL,
  timeout: 30000,
});

// Add auth token to requests
authClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const authService = {
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await authClient.post<AuthResponse>('/auth/login', {
      username: credentials.username,
      password: credentials.password,
    });

    if (response.data.access_token) {
      localStorage.setItem('auth_token', response.data.access_token);
    }

    return response.data;
  },

  async logout(): Promise<void> {
    try {
      await authClient.post('/auth/logout');
    } finally {
      localStorage.removeItem('auth_token');
    }
  },

  async getStatus(): Promise<AuthStatus> {
    try {
      const response = await authClient.get<AuthStatus>('/auth/status');
      return response.data;
    } catch (error) {
      return { authenticated: false };
    }
  },

  isAuthenticated(): boolean {
    return !!localStorage.getItem('auth_token');
  },
};
