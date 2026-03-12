import { useState, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  Alert,
  IconButton,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import DeleteIcon from '@mui/icons-material/Delete';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import { fileService } from '../services/fileService';
import type { UploadProgress } from '../types';

const FileUpload = () => {
  const [uploads, setUploads] = useState<UploadProgress[]>([]);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files) return;

    const validFiles = Array.from(files).filter((file) => {
      const ext = file.name.toLowerCase();
      return ext.endsWith('.xlsx') || ext.endsWith('.xls') || ext.endsWith('.xlsm');
    });

    if (validFiles.length === 0) {
      setError('Please select valid Excel files (.xlsx, .xls, .xlsm)');
      return;
    }

    setError(null);
    validFiles.forEach(uploadFile);

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const uploadFile = async (file: File) => {
    const uploadId = `${Date.now()}-${file.name}`;
    const newUpload: UploadProgress = {
      file_id: uploadId,
      filename: file.name,
      progress: 0,
      status: 'uploading',
    };

    setUploads((prev) => [...prev, newUpload]);

    try {
      await fileService.uploadFile(file, (progress) => {
        setUploads((prev) =>
          prev.map((u) =>
            u.file_id === uploadId ? { ...u, progress } : u
          )
        );
      });

      setUploads((prev) =>
        prev.map((u) =>
          u.file_id === uploadId
            ? { ...u, status: 'complete', progress: 100 }
            : u
        )
      );
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Upload failed';
      setUploads((prev) =>
        prev.map((u) =>
          u.file_id === uploadId
            ? { ...u, status: 'error', error: errorMsg }
            : u
        )
      );
    }
  };

  const removeUpload = (fileId: string) => {
    setUploads((prev) => prev.filter((u) => u.file_id !== fileId));
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    const files = event.dataTransfer.files;
    if (files.length > 0) {
      const input = fileInputRef.current;
      if (input) {
        input.files = files;
        handleFileSelect({ target: input } as any);
      }
    }
  };

  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault();
  };

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Upload Excel Files
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Box
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          sx={{
            border: '2px dashed',
            borderColor: 'primary.main',
            borderRadius: 2,
            p: 4,
            textAlign: 'center',
            cursor: 'pointer',
            mb: 2,
            '&:hover': {
              bgcolor: 'action.hover',
            },
          }}
          onClick={() => fileInputRef.current?.click()}
        >
          <UploadFileIcon sx={{ fontSize: 48, color: 'primary.main', mb: 1 }} />
          <Typography variant="body1" gutterBottom>
            Drag and drop Excel files here
          </Typography>
          <Typography variant="body2" color="text.secondary">
            or click to browse
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
            Supported formats: .xlsx, .xls, .xlsm
          </Typography>
        </Box>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".xlsx,.xls,.xlsm"
          style={{ display: 'none' }}
          onChange={handleFileSelect}
        />

        {uploads.length > 0 && (
          <List>
            {uploads.map((upload) => (
              <ListItem
                key={upload.file_id}
                secondaryAction={
                  upload.status === 'complete' || upload.status === 'error' ? (
                    <IconButton edge="end" onClick={() => removeUpload(upload.file_id)}>
                      <DeleteIcon />
                    </IconButton>
                  ) : null
                }
              >
                <Box sx={{ width: '100%' }}>
                  <Box display="flex" alignItems="center" gap={1}>
                    {upload.status === 'complete' && <CheckCircleIcon color="success" />}
                    {upload.status === 'error' && <ErrorIcon color="error" />}
                    <ListItemText
                      primary={upload.filename}
                      secondary={
                        upload.status === 'error'
                          ? upload.error
                          : upload.status === 'complete'
                          ? 'Upload complete'
                          : 'Uploading...'
                      }
                    />
                  </Box>
                  {upload.status === 'uploading' && (
                    <LinearProgress
                      variant="determinate"
                      value={upload.progress}
                      sx={{ mt: 1 }}
                    />
                  )}
                </Box>
              </ListItem>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
};

export default FileUpload;
