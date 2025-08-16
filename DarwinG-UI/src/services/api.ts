// API 服务层
import { API_ENDPOINTS, ERROR_MESSAGES } from '@/src/constants';
import type { DifyResponse, ApiError } from '@/src/types';

export class ApiService {
  private static async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const error: ApiError = {
        message: `HTTP error! status: ${response.status}`,
        code: response.status.toString(),
      };
      throw error;
    }
    return response.json();
  }

  static async fetchMessages(conversationId: string, user: string): Promise<DifyResponse> {
    const response = await fetch(
      `${API_ENDPOINTS.MESSAGES}?conversation_id=${conversationId}&user=${user}`
    );
    return this.handleResponse<DifyResponse>(response);
  }

  static async fetchConversations(user: string): Promise<DifyResponse> {
    const response = await fetch(`${API_ENDPOINTS.CONVERSATIONS}?user=${user}`);
    return this.handleResponse<DifyResponse>(response);
  }

  static async deleteConversation(conversationId: string, user: string): Promise<void> {
    const response = await fetch(`${API_ENDPOINTS.CONVERSATIONS}/${conversationId}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user }),
    });
    return this.handleResponse<void>(response);
  }

  static async renameConversation(
    conversationId: string, 
    name: string, 
    user: string
  ): Promise<{ name: string }> {
    const response = await fetch(`${API_ENDPOINTS.CONVERSATIONS}/${conversationId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, user }),
    });
    return this.handleResponse<{ name: string }>(response);
  }

  static async uploadFile(file: File, user: string): Promise<{ id: string }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('user', user);

    const response = await fetch(API_ENDPOINTS.UPLOAD, {
      method: 'POST',
      body: formData,
    });
    return this.handleResponse<{ id: string }>(response);
  }

  static async stopGeneration(taskId: string, user: string): Promise<void> {
    const response = await fetch(API_ENDPOINTS.STOP, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: taskId, user }),
    });
    return this.handleResponse<void>(response);
  }
}