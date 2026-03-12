import axios from 'axios';
import type { FileMetadata, GDriveStatus } from '../types';

// Files API is at /api/files, not /api/v1/files
const FILES_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace('/api/v1', '/api') || 'http://localhost:8000/api';

const filesClient = axios.create({
  baseURL: FILES_BASE_URL,
  timeout: 60000, // 60 seconds for file uploads
});

// Add auth token to requests
filesClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const fileService = {
  async uploadFile(file: File, onProgress?: (progress: number) => void): Promise<FileMetadata> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await filesClient.post<FileMetadata>('/files/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percentCompleted);
        }
      },
    });

    return response.data;
  },

  async listFiles(page: number = 1, limit: number = 20): Promise<{ files: FileMetadata[]; total: number }> {
    const response = await filesClient.get<{ files: FileMetadata[]; total: number }>('/files/list', {
      params: { page, limit },
    });
    return response.data;
  },

  async deleteFile(fileId: string): Promise<void> {
    await filesClient.delete(`/files/${fileId}`);
  },

  async reindexFile(fileId: string): Promise<void> {
    await filesClient.post(`/files/${fileId}/reindex`);
  },

  async getIndexingStatus(): Promise<{ status: string; progress: number }> {
    const response = await filesClient.get<{ status: string; progress: number }>('/files/indexing-status');
    return response.data;
  },

  // Google Drive methods
  async getGDriveStatus(): Promise<GDriveStatus> {
    const response = await filesClient.get<GDriveStatus>('/config/gdrive/status');
    return response.data;
  },

  async connectGDrive(): Promise<{ authorization_url: string }> {
    const response = await filesClient.post<{ authorization_url: string }>('/config/gdrive/connect');
    return response.data;
  },

  async disconnectGDrive(): Promise<void> {
    await filesClient.delete('/config/gdrive/disconnect');
  },
};
