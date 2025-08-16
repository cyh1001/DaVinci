// Conversation types and utilities

export interface DifyMessage {
  id: string;
  conversation_id: string;
  inputs: Record<string, any>;
  query: string;
  answer: string;
  message_files: Array<{
    id: string;
    type: string;
    url: string;
    belongs_to: 'user' | 'assistant';
  }>;
  feedback?: {
    rating: 'like' | 'dislike';
  } | null;
  retriever_resources: Array<{
    position: number;
    dataset_id: string;
    dataset_name: string;
    document_id: string;
    document_name: string;
    segment_id: string;
    score: number;
    content: string;
  }>;
  created_at: number;
}

export interface DifyHistoryResponse {
  limit: number;
  has_more: boolean;
  data: DifyMessage[];
}

export interface DifyConversationItem {
  id: string;
  name: string;
  inputs: Record<string, any>;
  status: string;
  introduction: string | null;
  created_at: number;
  updated_at: number;
}

export interface DifyConversationsResponse {
  limit: number;
  has_more: boolean;
  data: DifyConversationItem[];
}

export interface Conversation {
  id: string; // conversation_id from Dify
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
  lastMessage: string; // Preview of last message
  walletAddress: string;
}

const CONVERSATIONS_STORAGE_KEY = "darwin_conversations";

// Get all conversations for current wallet
export function getConversations(walletAddress: string): Conversation[] {
  if (typeof window === 'undefined') return [];
  
  try {
    const stored = localStorage.getItem(CONVERSATIONS_STORAGE_KEY);
    if (!stored) return [];
    
    const allConversations: Conversation[] = JSON.parse(stored);
    return allConversations.filter(conv => conv.walletAddress === walletAddress);
  } catch (error) {
    console.error('Error loading conversations:', error);
    return [];
  }
}

// Save conversation list for a specific wallet
export function saveConversationsForWallet(conversations: Conversation[], walletAddress: string): void {
  if (typeof window === 'undefined') return;
  
  try {
    // Get all conversations from all wallets
    const stored = localStorage.getItem(CONVERSATIONS_STORAGE_KEY);
    let allConversations: Conversation[] = stored ? JSON.parse(stored) : [];
    
    // Remove old conversations for this specific wallet
    allConversations = allConversations.filter(c => c.walletAddress !== walletAddress);
    
    // Add new conversations for this wallet
    allConversations.push(...conversations);
    
    localStorage.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(allConversations));
  } catch (error) {
    console.error('Error saving conversations:', error);
  }
}

// Save conversation list (legacy function, redirects to the new one)
export function saveConversations(conversations: Conversation[]): void {
  if (conversations.length === 0) {
    console.warn('saveConversations called with empty array, this might not work as expected');
    return;
  }
  
  // Get wallet address from first conversation
  const walletAddress = conversations[0].walletAddress;
  saveConversationsForWallet(conversations, walletAddress);
}

// Add or update a conversation
export function saveConversation(conversation: Conversation): void {
  if (typeof window === 'undefined') return;
  
  const conversations = getConversations(conversation.walletAddress);
  const existingIndex = conversations.findIndex(c => c.id === conversation.id);
  
  if (existingIndex >= 0) {
    conversations[existingIndex] = conversation;
  } else {
    conversations.unshift(conversation); // Add new conversation at the beginning
  }
  
  saveConversations(conversations);
}

// Delete a conversation
export function deleteConversation(conversationId: string, walletAddress: string): void {
  if (typeof window === 'undefined') return;
  
  const conversations = getConversations(walletAddress);
  console.log('Before delete - conversations:', conversations.length, conversations.map(c => c.id));
  console.log('Deleting conversation ID:', conversationId);
  
  const filtered = conversations.filter(c => c.id !== conversationId);
  console.log('After filter - conversations:', filtered.length, filtered.map(c => c.id));
  
  // Use the new function that explicitly handles wallet address
  saveConversationsForWallet(filtered, walletAddress);
  
  // Verify deletion
  const afterSave = getConversations(walletAddress);
  console.log('After save - conversations:', afterSave.length, afterSave.map(c => c.id));
}

// Rename a conversation
export function renameConversation(conversationId: string, newTitle: string, walletAddress: string): void {
  if (typeof window === 'undefined') return;
  
  const conversations = getConversations(walletAddress);
  const conversationIndex = conversations.findIndex(c => c.id === conversationId);
  
  if (conversationIndex >= 0) {
    conversations[conversationIndex] = {
      ...conversations[conversationIndex],
      title: newTitle,
      updatedAt: Date.now()
    };
    saveConversations(conversations);
  }
}

// Generate conversation title from first message
export function generateConversationTitle(firstMessage: string): string {
  if (!firstMessage) return 'New Chat';
  
  // Clean and truncate the message
  const cleaned = firstMessage.replace(/\[Attachments\][\s\S]*/g, '').trim();
  const truncated = cleaned.length > 50 ? cleaned.substring(0, 50) + '...' : cleaned;
  
  return truncated || 'New Chat';
}

// Sync conversations from Dify API to local storage
export async function syncConversationsFromDify(walletAddress: string): Promise<Conversation[]> {
  if (typeof window === 'undefined') return [];
  
  try {
    const response = await fetch(`/api/conversations?user=${encodeURIComponent(walletAddress)}&limit=100`);
    if (!response.ok) {
      console.error('Failed to fetch conversations from Dify:', response.status);
      return getConversations(walletAddress); // Fallback to local storage
    }
    
    const difyData: DifyConversationsResponse = await response.json();
    
    // Convert Dify conversations to our format
    const difyConversations: Conversation[] = difyData.data.map(difyConv => ({
      id: difyConv.id,
      title: difyConv.name,
      createdAt: difyConv.created_at * 1000, // Convert to milliseconds
      updatedAt: difyConv.updated_at * 1000, // Convert to milliseconds
      messageCount: 0, // We don't have this info from the list API
      lastMessage: difyConv.introduction || '',
      walletAddress
    }));
    
    // Get existing local conversations
    const localConversations = getConversations(walletAddress);
    
    // Merge: use Dify data as authoritative, but preserve local data for conversations not in Dify
    const mergedConversations: Conversation[] = [];
    
    // Add all Dify conversations (these are authoritative)
    mergedConversations.push(...difyConversations);
    
    // Add local conversations that are not in Dify (might be newly created but not yet synced)
    for (const localConv of localConversations) {
      if (!difyConversations.find(difyConv => difyConv.id === localConv.id)) {
        mergedConversations.push(localConv);
      }
    }
    
    // Sort by updated time (newest first)
    mergedConversations.sort((a, b) => b.updatedAt - a.updatedAt);
    
    // Save merged data to local storage
    saveConversationsForWallet(mergedConversations, walletAddress);
    
    return mergedConversations;
  } catch (error) {
    console.error('Error syncing conversations from Dify:', error);
    return getConversations(walletAddress); // Fallback to local storage
  }
}

// Convert Dify messages to our message format
export function convertDifyMessagesToLocal(difyMessages: DifyMessage[]) {
  const messages = [];
  
  for (const difyMessage of difyMessages) {
    // Add user message
    if (difyMessage.query) {
      // Build client-side attachments from Dify message_files that belong to the user
      const userFiles = Array.isArray(difyMessage.message_files)
        ? difyMessage.message_files.filter((f) => f.belongs_to === 'user')
        : [];
      const clientAttachments = userFiles.map((f) => {
        const fileNameFromUrl = (() => {
          try {
            const u = new URL(f.url);
            const last = u.pathname.split('/').filter(Boolean).pop();
            return last || f.id;
          } catch {
            // Fallback: attempt simple split if not a valid URL
            const parts = (f.url || '').split('/');
            return parts[parts.length - 1] || f.id;
          }
        })();
        const isImage = (f.type || '').toLowerCase() === 'image' || /\.(jpg|jpeg|png|gif|webp|svg)$/i.test(f.url);
        return {
          id: f.id,
          name: fileNameFromUrl,
          url: f.url,
          previewUrl: isImage ? f.url : undefined,
        } as any;
      });

      messages.push({
        id: `user_${difyMessage.id}`,
        role: 'user' as const,
        parts: [{ type: 'text' as const, text: difyMessage.query }],
        ...(clientAttachments.length > 0 ? { data: { clientAttachments } } : {})
      });
    }
    
    // Add assistant message
    if (difyMessage.answer) {
      messages.push({
        id: `assistant_${difyMessage.id}`,
        role: 'assistant' as const,
        parts: [{ type: 'text' as const, text: difyMessage.answer }]
      });
    }
  }
  
  return messages;
}