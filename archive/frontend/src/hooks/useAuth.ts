import { useState, useEffect } from 'react';
import { authService } from '../services/authService';
import type { LoginCredentials, AuthStatus } from '../types';

export const useAuth = () => {
  const [authStatus, setAuthStatus] = useState<AuthStatus>({ authenticated: false });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const status = await authService.getStatus();
      setAuthStatus(status);
    } catch (err) {
      setAuthStatus({ authenticated: false });
    } finally {
      setLoading(false);
    }
  };

  const login = async (credentials: LoginCredentials) => {
    setLoading(true);
    setError(null);
    try {
      const response = await authService.login(credentials);
      setAuthStatus({
        authenticated: true,
        user: response.user,
      });
      return true;
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Login failed. Please try again.';
      setError(errorMessage);
      return false;
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    setLoading(true);
    try {
      await authService.logout();
      setAuthStatus({ authenticated: false });
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setLoading(false);
    }
  };

  return {
    authStatus,
    loading,
    error,
    login,
    logout,
    isAuthenticated: authStatus.authenticated,
  };
};
