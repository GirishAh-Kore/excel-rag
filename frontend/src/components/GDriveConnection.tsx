import { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  CircularProgress,
  Alert,
  Chip,
} from '@mui/material';
import CloudIcon from '@mui/icons-material/Cloud';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import { fileService } from '../services/fileService';
import type { GDriveStatus } from '../types';

const GDriveConnection = () => {
  const [status, setStatus] = useState<GDriveStatus>({ connected: false });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      const data = await fileService.getGDriveStatus();
      setStatus(data);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load status');
    } finally {
      setLoading(false);
    }
  };

  const handleConnect = async () => {
    setLoading(true);
    setError(null);
    try {
      const { authorization_url } = await fileService.connectGDrive();
      window.location.href = authorization_url;
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to connect');
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    setLoading(true);
    setError(null);
    try {
      await fileService.disconnectGDrive();
      await loadStatus();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to disconnect');
      setLoading(false);
    }
  };

  if (loading && !status.connected) {
    return (
      <Box display="flex" justifyContent="center" p={3}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
          <Typography variant="h6">Google Drive Connection</Typography>
          {status.connected ? (
            <Chip icon={<CloudIcon />} label="Connected" color="success" />
          ) : (
            <Chip icon={<CloudOffIcon />} label="Disconnected" color="default" />
          )}
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {status.connected && status.email && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Connected as: {status.email}
          </Typography>
        )}

        {status.connected && status.last_sync && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Last synced: {new Date(status.last_sync).toLocaleString()}
          </Typography>
        )}

        <Box display="flex" gap={2}>
          {status.connected ? (
            <Button
              variant="outlined"
              color="error"
              onClick={handleDisconnect}
              disabled={loading}
            >
              {loading ? <CircularProgress size={24} /> : 'Disconnect'}
            </Button>
          ) : (
            <Button
              variant="contained"
              startIcon={<CloudIcon />}
              onClick={handleConnect}
              disabled={loading}
            >
              {loading ? <CircularProgress size={24} /> : 'Connect to Google Drive'}
            </Button>
          )}
        </Box>
      </CardContent>
    </Card>
  );
};

export default GDriveConnection;
