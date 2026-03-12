// Authentication types
export interface LoginCredentials {
  username: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: {
    username: string;
  };
}

export interface AuthStatus {
  authenticated: boolean;
  user?: {
    username: string;
  };
}

// File types
export interface FileMetadata {
  file_id: string;
  name: string;
  path: string;
  size: number;
  modified_time: string;
  indexed_at?: string;
  status: 'indexed' | 'pending' | 'failed';
}

export interface UploadProgress {
  file_id: string;
  filename: string;
  progress: number;
  status: 'uploading' | 'processing' | 'complete' | 'error';
  error?: string;
}

// Google Drive types
export interface GDriveStatus {
  connected: boolean;
  email?: string;
  last_sync?: string;
}

// Chat types
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: Source[];
  confidence?: number;
}

export interface Source {
  file_name: string;
  sheet_name: string;
  cell_range: string;
  citation_number: number;
}

export interface QueryRequest {
  query: string;
  session_id?: string;
}

export interface QueryResponse {
  answer: string;
  sources: Source[];
  confidence: number;
  session_id: string;
  clarification?: ClarificationRequest;
}

export interface ClarificationRequest {
  question: string;
  options: string[];
}

export interface Session {
  session_id: string;
  created_at: string;
  last_activity: string;
  message_count: number;
}

// API Error types
export interface ApiError {
  detail: string;
  correlation_id?: string;
}
