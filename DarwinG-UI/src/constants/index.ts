// 应用常量
export const APP_CONFIG = {
  name: 'DaVinci AI Commerce',
  description: 'AI-powered multi-agent e-commerce ecosystem',
  version: '1.0.0',
  repository: 'https://github.com/DaVinci-AI/DarwinG-UI',
};

// 存储键名
export const STORAGE_KEYS = {
  CONVERSATION_ID: 'davinci_conversation_id',
  SHOW_CONVERSATIONS: 'davinci_show_conversations', 
  WALLET_ADDRESS: 'davinci_wallet_address',
  TOOL_EXECUTIONS: 'toolExecutions',
} as const;

// API 端点
export const API_ENDPOINTS = {
  CHAT: '/api/chat',
  MESSAGES: '/api/messages',
  CONVERSATIONS: '/api/conversations',
  UPLOAD: '/api/upload',
  STOP: '/api/stop',
} as const;

// 支持的文件类型
export const SUPPORTED_FILE_TYPES = {
  IMAGES: ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'],
  DOCUMENTS: ['txt', 'md', 'pdf', 'html', 'xlsx', 'docx', 'csv', 'xml', 'epub', 'pptx'],
  AUDIO: ['mp3', 'm4a', 'wav', 'webm', 'amr'],
  VIDEO: ['mp4', 'mov', 'mpeg', 'mpga'],
} as const;

// Dynamic.xyz 配置
export const DYNAMIC_CONFIG = {
  ENVIRONMENT_ID: process.env.NEXT_PUBLIC_DYNAMIC_ENVIRONMENT_ID || '',
  APP_NAME: 'DaVinci AI Commerce',
} as const;

// 错误消息
export const ERROR_MESSAGES = {
  WALLET_NOT_CONNECTED: 'Please connect your wallet first',
  FILE_UPLOAD_FAILED: 'File upload failed',
  CONVERSATION_LOAD_FAILED: 'Failed to load conversation',
  MESSAGE_SEND_FAILED: 'Failed to send message',
  TIMEOUT: 'Request timed out',
} as const;