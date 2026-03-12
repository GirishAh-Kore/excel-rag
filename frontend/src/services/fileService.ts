import { apiClient } from './api';
import type { FileMetadata, GDriveStatus } from '../types';

export const fileService = {
  async uploadFile(file: File, onProgress?: (progress: number) => void): Promise<FileMetadata> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post<FileMetadata>('/files/upload', formData, {
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
    const response = await apiClient.get<{ files: FileMetadata[]; total: number }>('/files/list', {
      params: { page, limit },
    });
    return response.data;
  },

  async deleteFile(fileId: string): Promise<void> {
    await apiClient.delete(`/files/${fileId}`);
  },

  async reindexFile(fileId: string): Promise<void> {
    await apiClient.post(`/files/${fileId}/reindex`);
  },

  async getIndexingStatus(): Promise<{ status: string; progress: number }> {
    const response = await apiClient.get<{ status: string; progress: number }>('/files/indexing-status');
    return response.data;
  },

  // Google Drive methods
  async getGDriveStatus(): Promise<GDriveStatus> {
    const response = await apiClient.get<GDriveStatus>('/config/gdrive/status');
    return response.data;
  },

  async connectGDrive(): Promise<{ authorization_url: string }> {
    const response = await apiClient.post<{ authorization_url: string }>('/config/gdrive/connect');
    return response.data;
  },

  async disconnectGDrive(): Promise<void> {
    await apiClient.delete('/config/gdrive/disconnect');
  },
};
