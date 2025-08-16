// 通用类型定义

export interface User {
  id: string;
  address: string;
  email?: string;
  isAuthenticated: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
  lastMessage: string;
  walletAddress: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  attachments?: AttachmentPreview[];
}

export interface AttachmentPreview {
  id: string;
  name: string;
  size: number;
  type: string;
  url?: string;
  textSample?: string;
  originalFile?: File;
  isUrl?: boolean;
  fileUrl?: string;
  difyFileType?: string;
}

export interface ToolExecution {
  id: string;
  label: string;
  status: 'start' | 'progress' | 'complete' | 'error';
  timestamp: number;
  details?: any;
}

export interface DifyResponse {
  data: any[];
  has_more: boolean;
  limit: number;
}

export interface ApiError {
  message: string;
  code?: string;
  details?: any;
}