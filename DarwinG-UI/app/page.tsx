"use client";

import * as React from "react";
import { useChat } from "@ai-sdk/react";
import {
  lastAssistantMessageIsCompleteWithToolCalls,
} from "ai";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Paperclip, Send, Sparkles, Square, Package, Megaphone, Users } from 'lucide-react';
import {
  MessageBubble,
  AttachmentChips,
  type AttachmentPreview,
    BubbleAttachmentPreview,
    type BubbleAttachment,
} from "@/components/chat-bubbles";
import { type ToolExecution } from "@/components/tool-execution";
import { cn } from "@/lib/utils";
import { useDynamicContext, DynamicWidget, useAuthenticateConnectedUser } from "@dynamic-labs/sdk-react-core";
import { 
  saveConversation, 
  deleteConversation,
  generateConversationTitle,
  convertDifyMessagesToLocal,
  getConversations,
  syncConversationsFromDify,
  type Conversation,
  type DifyHistoryResponse
} from "@/lib/conversation";

const CONVERSATION_ID_KEY = "davinci_conversation_id";
import { Sidebar } from "@/components/sidebar"; // Import the new Sidebar component

const BRAND_COLOR = "rgb(249, 217, 247)";

type DragState = "idle" | "over";

export default function Page() {
  // Dynamic钱包状态 - 作为唯一真实来源
  const { primaryWallet, user, setShowAuthFlow } = useDynamicContext();
  const { authenticateUser, isAuthenticating } = useAuthenticateConnectedUser();
  
  // 调试信息：检查认证功能是否可用
  console.log('🔍 Dynamic Context Debug:', {
    primaryWallet: !!primaryWallet,
    user: !!user,
    setShowAuthFlow: !!setShowAuthFlow,
    authenticateUser: !!authenticateUser,
    isAuthenticating
  });
  
  // 使用state来稳定钱包地址，避免无限循环
  const [walletAddress, setWalletAddress] = React.useState<string | null>(null);
  
  // 访客状态管理
  const isVisitor = !!walletAddress && !user;
  const isAuthenticated = !!walletAddress && !!user;
  
  // 访客模式对话次数限制
  const VISITOR_MESSAGE_LIMIT = 3; // 访客最多5条消息
  const [visitorMessageCount, setVisitorMessageCount] = React.useState(0);
  
  // 仅在primaryWallet.address实际变化时更新
  React.useEffect(() => {
    const newAddress = primaryWallet?.address || null;
    if (newAddress !== walletAddress) {
      setWalletAddress(newAddress);
      console.log('🔄 Wallet address updated:', newAddress);
      
      // Reset visitor message count when wallet changes
      if (newAddress) {
        setVisitorMessageCount(0);
      }
    }
  }, [primaryWallet?.address, walletAddress]);

  const {
    messages,
    sendMessage,
    addToolResult,
    setMessages,
    // Automatically send after tool calls complete (Generative UI pattern)
  } = useChat({
    sendAutomaticallyWhen: lastAssistantMessageIsCompleteWithToolCalls,
    onFinish: (message: any) => {
      console.log('✅ onFinish called with message:', message);
      
      // Reset generation state when finished
      console.log('🔄 Resetting all generation states in onFinish');
      setIsGenerating(false);
      setCurrentTaskId(null);
      setSending(false);
      
      // Move current tool executions to the actual message ID and save to localStorage
      if (message && message.id) {
        console.log('✅ onFinish called with message ID:', message.id);
        setToolExecutions(prev => {
          const currentTools = prev.get('current');
          console.log('🔧 Current tools found:', currentTools ? currentTools.length : 0);
          if (currentTools && currentTools.length > 0) {
            const newMap = new Map(prev);
            newMap.set(message.id, currentTools);
            newMap.delete('current');
            
            // Save to localStorage now that we have the actual message ID
            console.log('💾 Saving tools for message:', message.id);
            saveToolExecutionsToStorage(message.id, currentTools);
            
            console.log('🔧 Moved tools from current to message ID:', message.id);
            return newMap;
          } else {
            console.log('⚠️ No current tools to move');
          }
          return prev;
        });
      } else {
        console.log('⚠️ onFinish called but no message or message.id');
      }
      
      // Refresh sidebar conversations once after a completed reply
      setConversationRefreshTrigger(prev => prev + 1);
      
      // Clear sending timeout
      if (sendingTimeoutRef.current) {
        clearTimeout(sendingTimeoutRef.current);
        sendingTimeoutRef.current = null;
      }
    },
    onError: (error: any) => {
      console.error('❌ useChat error:', error);
      // Reset all generation states on error
      console.log('🔄 Resetting all generation states in onError');
      setIsGenerating(false);
      setCurrentTaskId(null);
      setSending(false);
      setConnectionError('An error occurred while processing your message. Please try again.');
      
      // Update any running tool executions to error state
      setToolExecutions(prev => {
        const currentTools = prev.get('current') || [];
        if (currentTools.length > 0) {
          console.log('🔧 Marking running tools as failed due to error');
          const updatedTools = currentTools.map(tool => {
            if (tool.status === 'start') {
              return { ...tool, status: 'error' as const, label: `${tool.label} (Failed)` };
            }
            return tool;
          });
          const newMap = new Map(prev);
          newMap.set('current', updatedTools);
          return newMap;
        }
        return prev;
      });
      
      // Clear sending timeout
      if (sendingTimeoutRef.current) {
        clearTimeout(sendingTimeoutRef.current);
        sendingTimeoutRef.current = null;
      }
    },
    // Example client-side tool handler (optional):
    async onToolCall({ toolCall }) {
      // You can run simple client-side tools. Here we just demo a stub handler.
      if (toolCall.toolName === "getLocation") {
        // Return a random demo city:
        const cities = ["New York", "Los Angeles", "Chicago", "San Francisco"];
        addToolResult({
          tool: "getLocation",
          toolCallId: toolCall.toolCallId,
          output: cities[Math.floor(Math.random() * cities.length)],
        });
      }
    },
  });

  const [input, setInput] = React.useState("");
  const [sending, setSending] = React.useState(false); // 恢复sending状态
  const [connectionError, setConnectionError] = React.useState<string | null>(null);
  const [currentTaskId, setCurrentTaskId] = React.useState<string | null>(null);
  const [isGenerating, setIsGenerating] = React.useState(false);
  const [files, setFiles] = React.useState<AttachmentPreview[]>([]);
  const [drag, setDrag] = React.useState<DragState>("idle");
  const [showAttachMenu, setShowAttachMenu] = React.useState(false);
  const [showUrlInput, setShowUrlInput] = React.useState(false);
  const [urlInput, setUrlInput] = React.useState("");
  const attachMenuRef = React.useRef<HTMLDivElement>(null);
  const attachMenuBottomRef = React.useRef<HTMLDivElement>(null);
  const [activeMainTab, setActiveMainTab] = React.useState<'chat' | 'products' | 'marketing' | 'crm'>('chat'); // State for active main content tab
  const [conversationId, setConversationId] = React.useState<string | undefined>(); // State for Dify conversation continuity
  const [currentConversationId, setCurrentConversationId] = React.useState<string | undefined>(undefined); // Current selected conversation
  const [isLoadingHistory, setIsLoadingHistory] = React.useState(false);
  const [conversationRefreshTrigger, setConversationRefreshTrigger] = React.useState(0); // Trigger to refresh sidebar
  const [isHydrated, setIsHydrated] = React.useState(false); // Track hydration status
  const [toolExecutions, setToolExecutions] = React.useState<Map<string, ToolExecution[]>>(new Map()); // Track tool executions per message
  const [isInitialLoading, setIsInitialLoading] = React.useState(true); // Start true to prevent welcome screen flash
  const [isNewConversation, setIsNewConversation] = React.useState(false); // Track when user explicitly wants new conversation

  // Helper functions for tool executions persistence
  const saveToolExecutionsToStorage = React.useCallback((messageId: string, tools: ToolExecution[]) => {
    if (!walletAddress || !conversationId) return;
    const key = `toolExecutions_${walletAddress}`;
    try {
      const existing = localStorage.getItem(key);
      const allToolExecutions = existing ? JSON.parse(existing) : {};
      
      // Store by conversation ID and message position instead of message ID
      // This way tools persist across message ID changes
      // ✅ 确保索引不为负数
      const messageIndex = Math.max(0, messages.length - 1);
      const conversationKey = `${conversationId}_msg_${messageIndex}`; // Use message position
      allToolExecutions[conversationKey] = { messageId, tools };
      
      localStorage.setItem(key, JSON.stringify(allToolExecutions));
      console.log('💾 SAVED tool executions for conversation:', conversationKey, 'message:', messageId, 'tools count:', tools.length);
      console.log('💾 Full localStorage key:', key);
      console.log('💾 Tools saved:', tools.map(t => `${t.label}(${t.status})`));
    } catch (error) {
      console.error('Error saving tool executions:', error);
    }
  }, [walletAddress, conversationId, messages.length]);

  const loadToolExecutionsFromStorage = React.useCallback(() => {
    if (!walletAddress) return new Map();
    const key = `toolExecutions_${walletAddress}`;
    try {
      const stored = localStorage.getItem(key);
      console.log('🔍 LOADING tool executions from localStorage, key:', key);
      console.log('🔍 Raw stored data:', stored);
      if (stored) {
        const parsed = JSON.parse(stored);
        console.log('🔍 Parsed data:', parsed);
        const map = new Map();
        Object.entries(parsed).forEach(([messageId, tools]) => {
          map.set(messageId, tools as ToolExecution[]);
          console.log('🔍 Loaded tools for message:', messageId, 'count:', (tools as ToolExecution[]).length);
        });
        console.log('🔍 Final map size:', map.size);
        return map;
      } else {
        console.log('🔍 No stored data found');
      }
    } catch (error) {
      console.error('Error loading tool executions:', error);
    }
    return new Map();
  }, [walletAddress]);

  const messagesRef = React.useRef<HTMLDivElement | null>(null);
  const conversationIdRef = React.useRef<string | undefined>(undefined); // Ref to ensure we have the latest conversationId
  const sendingTimeoutRef = React.useRef<NodeJS.Timeout | null>(null); // Track active timeout

  // Single unified loader that covers all loading phases
  const isUnifiedLoading = React.useMemo(() => {
    return (!isHydrated || isInitialLoading || isLoadingHistory) && activeMainTab === 'chat';
  }, [isHydrated, isInitialLoading, isLoadingHistory, activeMainTab]);

  // Progressive loading messages that smoothly transition between phases
  const unifiedLoader = React.useMemo(() => {
    if (!isHydrated) {
      return { title: 'Loading DaVinci', subtitle: 'Initializing your workspace...' };
    }
    if (isInitialLoading || isLoadingHistory) {
      return { title: 'Loading DaVinci', subtitle: 'Retrieving your conversations...' };
    }
    return { title: 'Loading DaVinci', subtitle: 'Almost ready...' };
  }, [isHydrated, isInitialLoading, isLoadingHistory]);

  // 注释掉重复的日志记录，避免循环

  // Hydration - should happen immediately regardless of wallet status
  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      console.log('🔄 HYDRATION - marking as hydrated');
      setIsHydrated(true); // Mark as hydrated immediately
    }
  }, []);

  // Conversation loading - only when we have wallet address
  React.useEffect(() => {
    if (isHydrated && walletAddress) {
      const savedConversationId = localStorage.getItem(CONVERSATION_ID_KEY);
      console.log('🔄 CONVERSATION LOAD - savedConversation:', savedConversationId);
      
      if (savedConversationId) {
        console.log('🔄 IMMEDIATE LOAD - Conversation found, setting up auto-load');
        setCurrentConversationId(savedConversationId);
      } else {
        console.log('🔄 NO CONVERSATION TO LOAD - Will show welcome screen');
        setIsInitialLoading(false); // Stop loading, show welcome screen
      }
    } else if (isHydrated && !walletAddress) {
      // Hydrated but no wallet - show welcome screen immediately
      console.log('🔄 NO WALLET - Will show welcome screen');
      setIsInitialLoading(false);
    }
  }, [isHydrated, walletAddress]);

  // Load tool executions when wallet address changes
  React.useEffect(() => {
    if (walletAddress && isHydrated) {
      console.log('🔄 Loading tool executions for wallet:', walletAddress);
      const storedToolExecutions = loadToolExecutionsFromStorage();
      console.log('🔄 Setting tool executions, size:', storedToolExecutions.size);
      setToolExecutions(storedToolExecutions);
    }
  }, [walletAddress, isHydrated, loadToolExecutionsFromStorage]);

  // Note: Wallet connection changes are now handled by Dynamic SDK

  // Removed early reset of sending to avoid hiding loading bubble before text arrives

  // Load conversation history when selecting a conversation
  const loadConversationHistory = React.useCallback(async (conversationId: string) => {
    console.log('🔄 LOAD CONVERSATION START:', { conversationId, walletAddress });
    if (!walletAddress) {
      console.log('❌ LOAD CONVERSATION FAILED: No wallet address');
      setIsLoadingHistory(false);
      setIsInitialLoading(false);
      return;
    }

    setIsLoadingHistory(true);
    console.log('🔄 LOAD CONVERSATION: Fetching messages from API...');
    
    // Set a timeout to prevent infinite loading
    const loadTimeout = setTimeout(() => {
      console.log('❌ LOAD CONVERSATION TIMEOUT: Taking too long, resetting states');
      setIsLoadingHistory(false);
      setIsInitialLoading(false);
      setConnectionError('Loading conversation timed out. Please try again.');
    }, 10000); // 10 second timeout
    
    try {
      const response = await fetch(`/api/messages?conversation_id=${conversationId}&user=${walletAddress}`);
      console.log('🔄 LOAD CONVERSATION: API response status:', response.status);
      if (response.ok) {
        const data: DifyHistoryResponse = await response.json();
        const convertedMessages = convertDifyMessagesToLocal(data.data); // Dify API returns in correct chronological order
        
        // Set the conversation ID first
        setConversationId(conversationId);
        conversationIdRef.current = conversationId;
        
        // Load tool executions for this conversation's messages BEFORE setting messages
        console.log('🔄 Loading tool executions for conversation messages...');
        const storedToolExecutions = loadToolExecutionsFromStorage();
        console.log('🔄 All stored tool executions size:', storedToolExecutions.size);
        
        const conversationToolExecutions = new Map();
        
        // Get all stored tool execution keys to match against
        const storedKeys = Array.from(storedToolExecutions.keys());
        console.log('🔍 Available stored tool keys:', storedKeys);
        
        // Get stored tool execution data for this wallet
        const key = `toolExecutions_${walletAddress}`;
        let allStoredData = {};
        try {
          const stored = localStorage.getItem(key);
          if (stored) {
            allStoredData = JSON.parse(stored);
            console.log('🔍 Loaded stored data for tool lookup:', Object.keys(allStoredData));
          }
        } catch (error) {
          console.error('Error loading stored data for tool lookup:', error);
        }

        convertedMessages.forEach((msg, index) => {
          console.log('🔍 Checking message at index:', index, 'ID:', msg.id, 'role:', msg.role);
          
          // Try to find tools by conversation ID and message position
          const conversationKey = `${conversationId}_msg_${index}`;
          console.log('🔍 Looking for conversation key:', conversationKey);
          
          let tools = null;
          
          // Look through stored data for this conversation key
          for (const [storageKey, storageData] of Object.entries(allStoredData)) {
            if (storageKey === conversationKey) {
              tools = (storageData as any).tools;
              console.log('✅ Found tools by conversation position:', conversationKey, 'tools:', tools?.length || 0);
              break;
            }
          }
          
          if (tools && tools.length > 0) {
            console.log('✅ Loading tools for message:', msg.id, 'tools:', tools.length);
            conversationToolExecutions.set(msg.id, tools);
          } else {
            console.log('❌ No tools found for message at position:', index);
          }
        });
        
        console.log('🔄 Setting conversation tool executions, size:', conversationToolExecutions.size);
        
        // Set tool executions FIRST, then messages to prevent collapse
        setToolExecutions(conversationToolExecutions);
        
        // Now load messages into the chat
        if (setMessages) {
          setMessages(convertedMessages);
        }
        
        console.log('✅ LOAD CONVERSATION SUCCESS:', convertedMessages.length, 'messages loaded');
        console.log('✅ LOAD CONVERSATION: Loaded tool executions for', conversationToolExecutions.size, 'messages with tools');
      } else {
        const errorText = await response.text().catch(() => 'Unknown error');
        console.log('❌ LOAD CONVERSATION FAILED: API error', response.status, errorText);
        
        if (response.status === 404) {
          // Conversation not found, clear the saved ID and show welcome
          console.log('🔄 CONVERSATION NOT FOUND: Clearing saved conversation ID');
          if (typeof window !== 'undefined') {
            localStorage.removeItem(CONVERSATION_ID_KEY);
          }
          setConversationId(undefined);
          setCurrentConversationId(undefined);
          conversationIdRef.current = undefined;
          // Don't show error, just show welcome screen
        } else {
          setConnectionError(`Failed to load conversation history: ${response.status}`);
        }
      }
    } catch (error) {
      console.error('❌ LOAD CONVERSATION ERROR:', error);
      setConnectionError('Failed to load conversation history. Please try again.');
    } finally {
      clearTimeout(loadTimeout); // Clear the timeout
      console.log('🔄 LOAD CONVERSATION COMPLETE: Resetting loading states');
      setIsLoadingHistory(false);
      setIsInitialLoading(false);
    }
  }, [walletAddress, loadToolExecutionsFromStorage]); // ✅ 添加缺失的依赖

  // Auto-load last conversation on page refresh - but not when user wants new conversation
  React.useEffect(() => {
    // Skip if user explicitly wants new conversation
    if (isNewConversation) {
      console.log('🔄 Auto-load skipped - user wants new conversation');
      return;
    }

    // Only run once after hydration when wallet is available
    if (!walletAddress || !isHydrated) {
      console.log('🔄 Auto-load waiting for:', { walletAddress: !!walletAddress, isHydrated });
      return;
    }

    // If we're already loading, wait
    if (isLoadingHistory) {
      console.log('🔄 Auto-load skipped - already loading');
      return;
    }

    // If we already have messages, ensure initial loading is cleared and stop
    if (messages.length > 0) {
      if (isInitialLoading) {
        console.log('🔄 Messages present - clearing initial loading');
        setIsInitialLoading(false);
      }
      return;
    }

    // Prefer currentConversationId, then saved ID from localStorage
    const savedConversationId = typeof window !== 'undefined' ? localStorage.getItem(CONVERSATION_ID_KEY) : null;
    const idToLoad = currentConversationId || savedConversationId || undefined;
    console.log('🔄 Page refresh - idToLoad:', idToLoad, 'currentConversationId:', currentConversationId, 'saved:', savedConversationId);

    if (idToLoad) {
      if (!currentConversationId) setCurrentConversationId(idToLoad);
      console.log('🔄 Auto-loading conversation:', idToLoad);
      loadConversationHistory(idToLoad);
    } else {
      console.log('🔄 No conversation to auto-load - showing welcome');
      setIsInitialLoading(false);
    }
  }, [walletAddress, isHydrated, messages.length, isLoadingHistory, currentConversationId, isNewConversation, isInitialLoading]);

  // Handle conversation selection
  const handleSelectConversation = React.useCallback((conversationId: string | undefined) => {
    setCurrentConversationId(conversationId);
    setIsNewConversation(false); // Reset new conversation flag when selecting existing conversation
    
    if (conversationId) {
      loadConversationHistory(conversationId);
    } else {
      // New conversation - only clear tool executions for new conversations
      setConversationId(undefined);
      conversationIdRef.current = undefined;
      setToolExecutions(new Map());
      // Clear messages - this would need to be implemented in useChat
    }
  }, [loadConversationHistory]);

  // Handle new conversation
  const handleNewConversation = React.useCallback(() => {
    console.log('🔄 NEW CONVERSATION - User clicked new chat button');
    setIsNewConversation(true); // Flag that this is intentional new conversation
    setCurrentConversationId(undefined);
    setConversationId(undefined);
    conversationIdRef.current = undefined;
    setIsInitialLoading(false); // Show welcome screen, not loading
    
    // Clear messages
    if (setMessages) {
      setMessages([]);
    }
    
    // Clear from localStorage
    if (typeof window !== 'undefined') {
      localStorage.removeItem(CONVERSATION_ID_KEY);
    }
  }, []); // Remove setMessages dependency to prevent instability

  // Handle delete conversation
  const handleDeleteConversation = React.useCallback(async (conversationId: string) => {
    if (!walletAddress) return;
    
    try {
      // Call Dify API to delete conversation
      const response = await fetch(`/api/conversations/${conversationId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          user: walletAddress
        })
      });

      if (response.ok) {
        // Delete from local storage after successful API deletion
        deleteConversation(conversationId, walletAddress);
        console.log('Conversation deleted successfully from Dify and local storage');
        
        // If current conversation is being deleted, start new conversation
        if (currentConversationId === conversationId) {
          handleNewConversation();
        }
        
        // Sync with Dify to get the latest data
        try {
          await syncConversationsFromDify(walletAddress);
          console.log('Synced conversations with Dify after delete');
        } catch (error) {
          console.warn('Failed to sync with Dify after delete:', error);
        }
        
        // Trigger sidebar refresh
        setConversationRefreshTrigger(prev => prev + 1);
      } else {
        const errorText = await response.text();
        console.error('Failed to delete conversation:', response.status, errorText);
        setConnectionError('Failed to delete conversation. Please try again.');
      }
    } catch (error) {
      console.error('Error deleting conversation:', error);
      setConnectionError('Error deleting conversation. Please check your connection and try again.');
    }
  }, [walletAddress, currentConversationId, handleNewConversation]);

  // Handle rename conversation
  const handleRenameConversation = React.useCallback(async (conversationId: string, newTitle: string) => {
    if (!walletAddress) return;
    
    try {
      // Call Dify API to rename conversation
      const response = await fetch(`/api/conversations/${conversationId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: newTitle,
          user: walletAddress
        })
      });

      if (response.ok) {
        const responseData = await response.json();
        console.log('Dify API rename response:', responseData);
        
        // Use the title returned by Dify API to ensure consistency
        const confirmedTitle = responseData.name || newTitle;
        
        // Update local storage with the confirmed title
        const { renameConversation } = await import('@/lib/conversation');
        renameConversation(conversationId, confirmedTitle, walletAddress);
        console.log('Conversation renamed successfully to:', confirmedTitle);
        
        // Sync with Dify to get the latest data
        try {
          await syncConversationsFromDify(walletAddress);
          console.log('Synced conversations with Dify after rename');
        } catch (error) {
          console.warn('Failed to sync with Dify after rename:', error);
        }
        
        // Trigger sidebar refresh
        setConversationRefreshTrigger(prev => prev + 1);
      } else {
        const errorText = await response.text();
        console.error('Failed to rename conversation:', response.status, errorText);
        setConnectionError('Failed to rename conversation. Please try again.');
      }
    } catch (error) {
      console.error('Error renaming conversation:', error);
      setConnectionError('Error renaming conversation. Please check your connection and try again.');
    }
  }, [walletAddress]);

  // Save conversation when new messages are added
  React.useEffect(() => {
    if (messages.length > 0 && walletAddress && conversationId) {
      // Get existing conversations to check if this one already exists
      const existingConversations = getConversations(walletAddress);
      const existingConversation = existingConversations.find(c => c.id === conversationId);
      
      // Get the first user message to generate title (only for new conversations)
      const firstUserMessage = messages.find(m => m.role === 'user');
      if (firstUserMessage) {
        // Use existing title if conversation exists, otherwise generate new title
        const title = existingConversation 
          ? existingConversation.title 
          : generateConversationTitle(
              firstUserMessage.parts.find(p => p.type === 'text')?.text || ''
            );
        
        const conversation: Conversation = {
          id: conversationId,
          title,
          createdAt: existingConversation?.createdAt || Date.now(),
          updatedAt: Date.now(),
          messageCount: messages.length,
          lastMessage: messages[messages.length - 1]?.parts.find(p => p.type === 'text')?.text || '',
          walletAddress
        };
        
        saveConversation(conversation);
        setCurrentConversationId(conversationId);
      }
    }
  }, [messages, walletAddress, conversationId]);

  // This useEffect was replaced by the auto-load conversation logic above
  // to prevent conflicts and ensure proper conversation loading on refresh

  // Update ref and localStorage when conversationId changes
  React.useEffect(() => {
    conversationIdRef.current = conversationId;
    if (typeof window !== 'undefined') {
      if (conversationId) {
        localStorage.setItem(CONVERSATION_ID_KEY, conversationId);
        console.log("ConversationId updated and saved:", conversationId);
      } else {
        localStorage.removeItem(CONVERSATION_ID_KEY);
        console.log("ConversationId cleared from storage");
      }
    }
  }, [conversationId]);

  // Add custom stream handling for metadata capture (conversation ID and task ID)
  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      const originalFetch = window.fetch;
      
      window.fetch = async (input, init) => {
        const response = await originalFetch(input, init);
        
        // Only intercept chat API calls
        if (typeof input === 'string' && input.includes('/api/chat') && init?.method === 'POST') {
          console.log('Intercepting chat API call for metadata');
          
          // Clone response to avoid consuming the stream
          const clonedResponse = response.clone();
          
          // Read the stream in background to extract metadata
          setTimeout(async () => {
            try {
              const reader = clonedResponse.body?.getReader();
              if (!reader) return;
              
              let buffer = '';
              while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += new TextDecoder().decode(value);
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                
                for (const line of lines) {
                  if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') continue;
                    
                    try {
                      const parsed = JSON.parse(data);
                      
                      // Handle AI SDK-compatible data-* events (payload in parsed.data)
                      if (parsed.type === 'data-task-id' && parsed.data?.taskId) {
                        const taskId = parsed.data.taskId as string;
                        console.log('Intercepted task ID from data-*:', taskId);
                        setCurrentTaskId(taskId);
                        setIsGenerating(true);
                      }
                      
                      if (parsed.type === 'data-conversation-id' && parsed.data?.conversationId) {
                        const convId = parsed.data.conversationId as string;
                        console.log('Intercepted conversation ID from data-*:', convId);
                        setConversationId(convId);
                        conversationIdRef.current = convId;
                      }
                      
                      // Handle tool execution events using AI SDK data-* format
                      if (parsed.type === 'data-tool-execution' && parsed.data?.toolExecution) {
                        const toolData = parsed.data.toolExecution as ToolExecution;
                        console.log('🔧 Intercepted tool execution:', toolData.label, toolData.status);
                        console.log('🔧 Tool data:', toolData);
                        
                        setToolExecutions(prev => {
                          const currentMessageId = 'current'; // We'll use current message since we don't have specific message ID yet
                          const currentTools = prev.get(currentMessageId) || [];
                          
                          // Update existing tool or add new one
                          const existingIndex = currentTools.findIndex(t => t.id === toolData.id);
                          let updatedTools: ToolExecution[];
                          
                          if (existingIndex >= 0) {
                            updatedTools = [...currentTools];
                            updatedTools[existingIndex] = toolData;
                          } else {
                            updatedTools = [...currentTools, toolData];
                          }
                          
                          const newMap = new Map(prev);
                          newMap.set(currentMessageId, updatedTools);
                          
                          // Save to localStorage (for 'current' we don't save yet, wait for message completion)
                          if (currentMessageId !== 'current') {
                            saveToolExecutionsToStorage(currentMessageId, updatedTools);
                          }
                          
                          return newMap;
                        });
                      }
                    } catch (e) {
                      // Skip malformed JSON
                    }
                  }
                }
              }
            } catch (e) {
              console.log('Error reading metadata from stream:', e);
            }
          }, 0);
        }
        
        return response;
      };
      
      return () => {
        window.fetch = originalFetch;
      };
    }
  }, [conversationId]);

  // Reset conversation when messages are cleared (new conversation)
  // BUT NOT on initial page load when messages naturally start empty
  React.useEffect(() => {
    if (messages.length === 0 && isHydrated && conversationId) {
      // Only clear if we previously had a conversation (not on initial load)
      console.log("Conversation reset - clearing conversation ID because messages were cleared");
      setConversationId(undefined);
      conversationIdRef.current = undefined;
      if (typeof window !== 'undefined') {
        localStorage.removeItem(CONVERSATION_ID_KEY);
      }
    }
  }, [messages.length, isHydrated, conversationId]);

  React.useEffect(() => {
    const el = messagesRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // Click-outside functionality for attachment menu
  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const clickedElement = event.target as Node;
      const isInsideTopMenu = attachMenuRef.current && attachMenuRef.current.contains(clickedElement);
      const isInsideBottomMenu = attachMenuBottomRef.current && attachMenuBottomRef.current.contains(clickedElement);
      
      if (!isInsideTopMenu && !isInsideBottomMenu) {
        setShowAttachMenu(false);
      }
    }

    if (showAttachMenu) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [showAttachMenu]);

  // 监听messages变化来停止发送状态（仅在收到首个文本增量后再隐藏加载气泡）
  React.useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if (!lastMessage || !sending) return;
    if (lastMessage.role === 'assistant') {
      const hasNonEmptyText = Array.isArray((lastMessage as any).parts)
        && (lastMessage as any).parts.some((p: any) => p.type === 'text' && typeof p.text === 'string' && p.text.length > 0);
      if (hasNonEmptyText) {
        console.log('AI text started streaming, stopping loading indicator');
        setSending(false);
        if (sendingTimeoutRef.current) {
          clearTimeout(sendingTimeoutRef.current);
          sendingTimeoutRef.current = null;
        }
      }
    }
  }, [messages, sending]);

  // Monitor for completed messages and move 'current' tools to message ID
  React.useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if (!lastMessage || lastMessage.role !== 'assistant') return;
    
    // Check if this is a completed assistant message (has text content and not currently generating)
    const hasTextContent = Array.isArray((lastMessage as any).parts) && 
      (lastMessage as any).parts.some((p: any) => p.type === 'text' && typeof p.text === 'string' && p.text.length > 0);
      
    if (hasTextContent && !isGenerating && !sending) {
      // Check if we have 'current' tools that need to be moved to this message
      const currentTools = toolExecutions.get('current');
      if (currentTools && currentTools.length > 0) {
        console.log('🔄 Moving tools from current to completed message:', lastMessage.id);
        setToolExecutions(prev => {
          const newMap = new Map(prev);
          newMap.set(lastMessage.id, currentTools);
          newMap.delete('current');
          
          // Save to localStorage
          saveToolExecutionsToStorage(lastMessage.id, currentTools);
          console.log('💾 Saved tools for completed message:', lastMessage.id);
          
          return newMap;
        });
      }
    }
  }, [messages, isGenerating, sending, toolExecutions, saveToolExecutionsToStorage]);

  const onFilesSelected = React.useCallback(async (list: FileList | null) => {
    if (!list || list.length === 0) return;
    const newItems: AttachmentPreview[] = [];
    for (let i = 0; i < list.length; i++) {
      const f = list.item(i)!;
      // Use a simple UUID fallback for better browser compatibility
      const generateId = () => {
        try {
          return crypto.randomUUID();
        } catch {
          // Fallback for browsers that don't support crypto.randomUUID
          return `${Date.now()}-${Math.random().toString(36).substring(2, 15)}`;
        }
      };
      const id = `${f.name}-${f.size}-${f.lastModified}-${generateId()}`;
      const item: AttachmentPreview = {
        id,
        name: f.name,
        size: f.size,
        type: f.type || "application/octet-stream",
        originalFile: f, // Store the original file
      };

      if (f.type.startsWith("image/")) {
        item.url = URL.createObjectURL(f);
      } else if (
        f.type.startsWith("text/") ||
        f.type.includes("json") ||
        f.type.includes("csv")
      ) {
        const text = await f.text();
        item.textSample = text.slice(0, 1000);
      }

      newItems.push(item);
    }
    setFiles((prev) => [...prev, ...newItems]);
    setShowAttachMenu(false);
  }, []);

  const onUrlAdd = React.useCallback(async () => {
    if (!urlInput.trim()) return;
    
    try {
      const url = urlInput.trim();
      // Basic URL validation
      new URL(url);
      
      // Determine file type from URL extension
      const urlObj = new URL(url);
      const pathname = urlObj.pathname.toLowerCase();
      let fileType = 'custom';
      let displayType = 'application/octet-stream';
      
      if (pathname.match(/\.(jpg|jpeg|png|gif|webp|svg)$/)) {
        fileType = 'image';
        displayType = 'image/*';
      } else if (pathname.match(/\.(txt|md|pdf|html|xlsx|docx|csv|xml|epub|pptx)$/)) {
        fileType = 'document';
        displayType = 'text/plain';
      } else if (pathname.match(/\.(mp3|m4a|wav|webm|amr)$/)) {
        fileType = 'audio';
        displayType = 'audio/*';
      } else if (pathname.match(/\.(mp4|mov|mpeg|mpga)$/)) {
        fileType = 'video';
        displayType = 'video/*';
      }

      const filename = pathname.split('/').pop() || 'file-from-url';
      
      // Use a simple UUID fallback for better browser compatibility
      const generateId = () => {
        try {
          return crypto.randomUUID();
        } catch {
          // Fallback for browsers that don't support crypto.randomUUID
          return `${Date.now()}-${Math.random().toString(36).substring(2, 15)}`;
        }
      };

      const urlFile: AttachmentPreview = {
        id: `url-${Date.now()}-${generateId()}`,
        name: filename,
        size: 0, // Unknown size for URL files
        type: displayType,
        url: fileType === 'image' ? url : undefined, // Show preview for images
        isUrl: true,
        fileUrl: url,
        difyFileType: fileType,
      };

      setFiles((prev) => [...prev, urlFile]);
      setUrlInput("");
      setShowUrlInput(false);
      setShowAttachMenu(false);
    } catch (error) {
      setConnectionError("Please enter a valid URL");
    }
  }, [urlInput]);

  const onDrop = React.useCallback(
    async (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDrag("idle");
      const dt = e.dataTransfer;
      await onFilesSelected(dt.files);
    },
    [onFilesSelected]
  );

  const onSend = React.useCallback(async () => {
    // Check wallet connection first
    if (!walletAddress) {
      alert("Please connect your wallet first to use chat functionality");
      return;
    }

    // Check visitor message limit
    if (isVisitor && visitorMessageCount >= VISITOR_MESSAGE_LIMIT) {
      // Don't show alert, just return - UI will show the limit message
      return;
    }

    if (!input.trim() && files.length === 0) return;

    // Store input and files before clearing them
    const messageText = input;
    const messageFiles = [...files];
    
    // Clear input and files immediately (but keep object URLs alive for previews)
    setInput("");
    setFiles([]);

    setSending(true);
    setConnectionError(null); // Clear any previous errors
    setIsGenerating(false); // Reset generation state for new message
    setCurrentTaskId(null);
    setIsNewConversation(false); // Reset new conversation flag when sending message
    
    // Clear any existing timeout
    if (sendingTimeoutRef.current) {
      clearTimeout(sendingTimeoutRef.current);
    }
    
    // Set a timeout to reset sending state if no response after 90 seconds
    sendingTimeoutRef.current = setTimeout(() => {
      // Use a ref or check current state to avoid closure issues
      console.log('Message sending timeout, resetting state');
      setSending(false);
      setIsGenerating(false);
      setCurrentTaskId(null);
      setConnectionError('Request timed out. The AI service may be experiencing issues. Please try again.');
      
      // Update any running tool executions to error state due to timeout
      setToolExecutions(prev => {
        const currentTools = prev.get('current') || [];
        if (currentTools.length > 0) {
          console.log('🔧 Marking running tools as failed due to timeout');
          const updatedTools = currentTools.map(tool => {
            if (tool.status === 'start') {
              return { ...tool, status: 'error' as const, label: `${tool.label} (Timeout)` };
            }
            return tool;
          });
          const newMap = new Map(prev);
          newMap.set('current', updatedTools);
          return newMap;
        }
        return prev;
      });
      
      sendingTimeoutRef.current = null;
    }, 90000);
    
    try {
      const currentConversationId = conversationIdRef.current;
      
      console.log("Sending message with conversation ID:", currentConversationId);
      console.log("Message files:", messageFiles);

      // Process files (both local uploads and URLs)
      let uploadedFiles: any[] = [];
      if (messageFiles.length > 0) {
        for (const file of messageFiles) {
          try {
            if (file.isUrl && file.fileUrl) {
              // Validate URL format
              try {
                new URL(file.fileUrl); // This will throw if URL is invalid
                
                // Handle URL files
                uploadedFiles.push({
                  type: file.difyFileType || 'custom',
                  transfer_method: 'remote_url',
                  url: file.fileUrl
                });
                
                console.log('URL file added:', {
                  fileName: file.name,
                  url: file.fileUrl,
                  type: file.difyFileType || 'custom'
                });
              } catch (urlError) {
                console.error('Invalid URL format for file:', file.name, 'URL:', file.fileUrl);
              }
            } else if (file.originalFile) {
              // Handle local file uploads
              const formData = new FormData();
              formData.append('file', file.originalFile);
              formData.append('user', walletAddress);

              const uploadResponse = await fetch('/api/upload', {
                method: 'POST',
                body: formData,
              });

              if (uploadResponse.ok) {
                const uploadResult = await uploadResponse.json();
                
                // Validate Dify file upload response
                if (!uploadResult || typeof uploadResult !== 'object') {
                  console.error('Invalid upload response format for:', file.name);
                  continue;
                }

                // Check if the response has the expected Dify file structure
                if (!uploadResult.id) {
                  console.error('Upload response missing file ID for:', file.name, uploadResult);
                  continue;
                }

                // Log the file information received from Dify for debugging
                console.log('File upload successful:', {
                  fileName: file.name,
                  difyResponse: uploadResult
                });
                
                // Determine file type based on MIME type
                let fileType = 'custom';
                if (file.type.startsWith('image/')) {
                  fileType = 'image';
                } else if (
                  file.type.startsWith('text/') || 
                  file.type.includes('json') || 
                  file.type.includes('csv') ||
                  file.type.includes('pdf') ||
                  file.type.includes('document') ||
                  file.type.includes('spreadsheet') ||
                  file.type.includes('xlsx') ||
                  file.type.includes('docx') ||
                  file.type.includes('pptx') ||
                  file.type.includes('html') ||
                  file.type.includes('xml') ||
                  file.type.includes('epub') ||
                  file.name.match(/\.(txt|md|pdf|html|xlsx|docx|csv|xml|epub|pptx)$/i)
                ) {
                  fileType = 'document';
                } else if (file.type.startsWith('audio/')) {
                  fileType = 'audio';
                } else if (file.type.startsWith('video/')) {
                  fileType = 'video';
                }
                
                // Validate the file ID format (Dify typically returns UUIDs)
                const fileId = uploadResult.id;
                if (typeof fileId !== 'string' || fileId.length === 0) {
                  console.error('Invalid file ID format from Dify:', fileId, 'for file:', file.name);
                  continue;
                }
                
                uploadedFiles.push({
                  type: fileType,
                  transfer_method: 'local_file',
                  upload_file_id: fileId
                });
              } else {
                const errorText = await uploadResponse.text().catch(() => 'Unknown error');
                console.error('File upload failed for:', file.name, 'Status:', uploadResponse.status, 'Error:', errorText);
              }
            } else {
              console.warn('File has no originalFile or URL, skipping:', file.name);
            }
          } catch (error) {
            console.error('Error processing file:', file.name, error);
          }
        }
      }

      // Final validation of uploaded files
      const validUploadedFiles = uploadedFiles.filter(file => {
        // Validate file structure
        if (!file || typeof file !== 'object') {
          console.warn('Invalid file object:', file);
          return false;
        }
        
        // Check required fields
        if (!file.type || !file.transfer_method) {
          console.warn('File missing required fields:', file);
          return false;
        }
        
        // Validate transfer method specific requirements
        if (file.transfer_method === 'local_file' && !file.upload_file_id) {
          console.warn('Local file missing upload_file_id:', file);
          return false;
        }
        
        if (file.transfer_method === 'remote_url' && !file.url) {
          console.warn('Remote file missing URL:', file);
          return false;
        }
        
        return true;
      });

      if (validUploadedFiles.length !== uploadedFiles.length) {
        console.warn(`Filtered out ${uploadedFiles.length - validUploadedFiles.length} invalid file(s)`);
        uploadedFiles = validUploadedFiles;
      }

      console.log('Final validated files for Dify:', uploadedFiles);

      // Show user feedback if some files failed to upload
      if (messageFiles.length > 0 && uploadedFiles.length < messageFiles.length) {
        const failedCount = messageFiles.length - uploadedFiles.length;
        setConnectionError(`Warning: ${failedCount} file(s) failed to upload and will only be included as text summary.`);
      }

      // Include file summary for files that couldn't be uploaded
      const attachmentSummary = messageFiles.length > uploadedFiles.length
        ? "\n\n[File Attachments]\n" +
          messageFiles
            .filter((_, idx) => idx >= uploadedFiles.length)
            .map((f, idx) => {
              const base = `${idx + 1}. ${f.name} (${Math.ceil(f.size / 1024)} KB, ${f.type || "unknown"})`;
              const snippet = f.textSample ? `\n---\n${f.textSample}\n---\n` : "";
              return base + (snippet ? `\n${snippet}` : "");
            })
            .join("\n")
        : "";

      // Build client-side attachment previews for this message
      const clientAttachments: BubbleAttachment[] = messageFiles.map((f) => ({
        id: f.id,
        name: f.name,
        size: f.size,
        type: f.type,
        url: f.isUrl ? f.fileUrl : undefined,
        previewUrl: f.type.startsWith('image/') ? f.url : (f.isUrl && (f.url || '').length ? f.url : undefined),
      }));

      // Send message with uploaded files and client-side preview metadata
      await sendMessage({
        parts: [{ type: "text", text: messageText + attachmentSummary }],
        ...(currentConversationId || walletAddress || uploadedFiles.length > 0 ? {
          data: { 
            ...(walletAddress && { walletAddress: walletAddress }),
            ...(currentConversationId && { conversationId: currentConversationId }),
            ...(uploadedFiles.length > 0 && { files: uploadedFiles }),
            ...(clientAttachments.length > 0 && { clientAttachments })
          } as any
        } : {})
      });

      // Update visitor message count
      if (isVisitor) {
        setVisitorMessageCount(prev => prev + 1);
      }

      // Schedule cleanup of any temporary object URLs used for previews
      try {
        messageFiles.forEach((f) => {
          if (!f.isUrl && f.url) {
            setTimeout(() => {
              try { URL.revokeObjectURL(f.url!); } catch {}
            }, 60000);
          }
        });
      } catch {}
      
      // Clear timeout on successful send
      if (sendingTimeoutRef.current) {
        clearTimeout(sendingTimeoutRef.current);
        sendingTimeoutRef.current = null;
      }
    } catch (error) {
      console.error('Error sending message:', error);
      setConnectionError('Failed to send message. Please check your connection and try again.');
      setSending(false);
      if (sendingTimeoutRef.current) {
        clearTimeout(sendingTimeoutRef.current);
        sendingTimeoutRef.current = null;
      }
    }
  }, [input, files, sendMessage, walletAddress]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Disable keyboard shortcuts when visitor limit reached
    if (isVisitor && visitorMessageCount >= VISITOR_MESSAGE_LIMIT) {
      return;
    }
    
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      onSend();
    }
  };

  const handleStopGeneration = React.useCallback(async () => {
    if (!currentTaskId || !walletAddress) return;

    try {
      console.log('Stopping generation for task:', currentTaskId);
      
      const response = await fetch('/api/stop', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          task_id: currentTaskId,
          user: walletAddress,
        }),
      });

      if (response.ok) {
        console.log('Generation stopped successfully');
        setIsGenerating(false);
        setCurrentTaskId(null);
        setSending(false);
        // Mark any current running tools as interrupted for UI clarity
        setToolExecutions(prev => {
          const newMap = new Map(prev);
          const currentTools = newMap.get('current');
          if (currentTools && currentTools.length > 0) {
            const interrupted = currentTools.map(t => (
              t.status === 'start' ? { ...t, status: 'error' as const, label: `${t.label} (Interrupted)` } : t
            ));
            newMap.set('current', interrupted);
          }
          return newMap;
        });
      } else {
        console.error('Failed to stop generation:', response.status);
        setConnectionError('Failed to stop generation. Please try again.');
      }
    } catch (error) {
      console.error('Error stopping generation:', error);
      setConnectionError('Error stopping generation. Please check your connection.');
    }
  }, [currentTaskId, walletAddress]);

  return (
    <main className="h-dvh bg-neutral-50 flex flex-col">
      <div className="flex flex-1 overflow-hidden"> {/* Full height container for sidebar and main content */}
        <Sidebar 
          onSelectTab={setActiveMainTab} 
          activeTab={activeMainTab}
          currentConversationId={currentConversationId}
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
          onDeleteConversation={handleDeleteConversation}
          onRenameConversation={handleRenameConversation}
          refreshTrigger={conversationRefreshTrigger}
          isHydrated={isHydrated}
        /> {/* Render the new Sidebar component */}

        {/* Main content area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {isUnifiedLoading ? (
            // Unified loading screen for hydration and conversation history
            <div className="flex-1 flex flex-col items-center justify-center p-6">
              <div className="relative mb-6">
                <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-emerald-100 to-emerald-200 flex items-center justify-center shadow-inner">
                  <div className="h-6 w-6 border-2 border-emerald-600/80 border-t-transparent rounded-full animate-spin"></div>
                </div>
                <div className="absolute -top-1 -right-1 h-2.5 w-2.5 bg-emerald-500 rounded-full animate-pulse" />
              </div>
              <p className="text-sm text-gray-600">{unifiedLoader.title}</p>
              <p className="text-xs text-gray-400 mt-2">{unifiedLoader.subtitle}</p>
            </div>
          ) : !walletAddress ? (
            // Modern welcome screen with integrated Dynamic wallet connection
            <div className="flex-1 flex items-center justify-center p-6 bg-gradient-to-br from-gray-50 via-white to-emerald-50/30 welcome-container">
              <div className="w-full max-w-2xl text-center mx-auto">
                {/* Logo and branding */}
                <div className="mx-auto mb-8 h-20 w-20 rounded-3xl bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shadow-lg">
                  <Sparkles className="h-10 w-10 text-white" />
                </div>
                
                {/* Main heading */}
                <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-4 text-gray-900 welcome-title">
                  <span className="bg-gradient-to-r from-emerald-600 via-emerald-700 to-teal-600 bg-clip-text text-transparent">
                    Welcome to DaVinci
                  </span>
                </h1>
                
                {/* Subtitle */}
                <p className="text-xl text-gray-600 mb-8 leading-relaxed max-w-3xl mx-auto welcome-subtitle">
                  AI-powered multi-agent system for autonomous e-commerce operations
                </p>
                
                {/* Feature highlights */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10 text-center">
                  <div className="p-4 rounded-xl bg-white/60 backdrop-blur-sm border border-gray-200/50">
                    <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center mx-auto mb-3">
                      <Package className="h-5 w-5 text-emerald-600" />
                    </div>
                    <h3 className="font-semibold text-gray-900 mb-1">Product Management</h3>
                    <p className="text-sm text-gray-600">AI-driven inventory & optimization</p>
                  </div>
                  <div className="p-4 rounded-xl bg-white/60 backdrop-blur-sm border border-gray-200/50">
                    <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center mx-auto mb-3">
                      <Megaphone className="h-5 w-5 text-emerald-600" />
                    </div>
                    <h3 className="font-semibold text-gray-900 mb-1">Smart Marketing</h3>
                    <p className="text-sm text-gray-600">Automated campaign generation</p>
                  </div>
                  <div className="p-4 rounded-xl bg-white/60 backdrop-blur-sm border border-gray-200/50">
                    <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center mx-auto mb-3">
                      <Users className="h-5 w-5 text-emerald-600" />
                    </div>
                    <h3 className="font-semibold text-gray-900 mb-1">CRM Intelligence</h3>
                    <p className="text-sm text-gray-600">Customer insights & automation</p>
                  </div>
                </div>
                
                {/* Dynamic Widget Integration */}
                <div className="rounded-2xl border border-gray-200/60 bg-white/80 backdrop-blur-sm shadow-lg p-8 mb-6">
                  <div className="mb-6">
                    <h2 className="text-xl font-semibold text-gray-900 mb-2">Connect to Get Started</h2>
                    <p className="text-gray-600 text-sm">
                      Choose your preferred connection method to access DaVinci's AI capabilities
                    </p>
                  </div>
                  
                  {/* Dynamic Widget - This will render the actual connection interface */}
                  <div className="flex justify-center">
                    <DynamicWidget />
                  </div>
                  
                  {/* Visitor Mode Info */}
                  <div className="mt-4 p-4 rounded-lg bg-amber-50 border border-amber-200">
                    <div className="flex items-center gap-2 text-amber-800">
                      <span className="text-sm">ℹ️</span>
                      <span className="text-sm font-medium">Visitor Mode Available</span>
                    </div>
                    <p className="text-xs text-amber-700 mt-1">
                      Connect your wallet to explore basic features. Sign a message to unlock full AI capabilities and persistent storage.
                    </p>
                  </div>
                  
                  {/* Connection methods info */}
                  <div className="mt-6 pt-6 border-t border-gray-200/60">
                    <div className="text-xs text-gray-500 mb-3 font-medium">Supported Methods:</div>
                    <div className="flex flex-wrap justify-center gap-2">
                      <span className="px-3 py-1.5 rounded-full bg-gray-100 text-gray-700 text-xs font-medium">🦊 MetaMask</span>
                      <span className="px-3 py-1.5 rounded-full bg-gray-100 text-gray-700 text-xs font-medium">🔗 WalletConnect</span>
                      <span className="px-3 py-1.5 rounded-full bg-gray-100 text-gray-700 text-xs font-medium">📧 Email</span>
                      <span className="px-3 py-1.5 rounded-full bg-gray-100 text-gray-700 text-xs font-medium">🔑 Social Login</span>
                      <span className="px-3 py-1.5 rounded-full bg-gray-100 text-gray-700 text-xs font-medium">₿ Multi-Chain</span>
                    </div>
                  </div>
                </div>
                
                {/* Security note */}
                <div className="text-xs text-gray-500 text-center max-w-md mx-auto">
                  🔒 Powered by Dynamic's enterprise-grade security. Your keys, your crypto. 
                  Non-custodial and fully decentralized.
                </div>
              </div>
            </div>
          ) : (
            // Main content based on selected tab
            <>
              {activeMainTab === 'chat' && (
                <div className="flex-1 flex flex-col min-h-0">
                <div
                  ref={messagesRef}
                    className="flex-1 min-h-0 overflow-y-auto"
                >
                    <div className="px-6 py-8 mx-auto max-w-4xl w-full">
                    
                  {/* 访客模式提示 - 简化版本 */}
                  {isVisitor && (
                    <div className="mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200">
                      <div className="flex items-center justify-between text-amber-800">
                        <div className="flex items-center gap-2">
                          <span className="text-sm">ℹ️</span>
                          <span className="text-sm">
                            <strong>Visitor Mode:</strong> Chat with AI, but conversations won't be saved.
                          </span>
                        </div>
                        <div className="text-xs bg-amber-100 px-2 py-1 rounded-full">
                          {visitorMessageCount}/{VISITOR_MESSAGE_LIMIT} messages
                        </div>
                      </div>
                      {visitorMessageCount >= VISITOR_MESSAGE_LIMIT && (
                        <div className="mt-2 text-xs text-amber-700">
                          Message limit reached. Sign a message to unlock unlimited conversations.
                        </div>
                      )}
                    </div>
                  )}
                  
                  {/* Unified loader already shown above; avoid second loader here */}
                  {/* Empty-state like ChatGPT: input centered until first message */}
                   {(() => {
                     const shouldShowWelcome = !isLoadingHistory && !isInitialLoading && messages.length === 0;
                     console.log('🔄 WELCOME SCREEN CHECK:', {
                       shouldShowWelcome,
                       isLoadingHistory,
                       isInitialLoading,
                       messagesLength: messages.length,
                       conversationId,
                       currentConversationId,
                       isNewConversation
                     });
                     return shouldShowWelcome;
                   })() ? (
                        <div className="h-full w-full flex items-center justify-center min-h-[60vh]">
                      <div className="max-w-3xl w-full">
                            <div className="text-center mb-8">
                              <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-emerald-100 flex items-center justify-center">
                                <Sparkles className="w-8 h-8 text-emerald-600" />
                              </div>
                              <h1 className="text-3xl font-semibold mb-3 welcome-title">{"Welcome to DaVinci"}</h1>
                              <p className="text-gray-600 text-lg leading-relaxed mb-2 welcome-subtitle">
                                {'A Multi-Agent AI System for Autonomous E-commerce Operations'}
                              </p>
                              <p className="text-sm text-gray-500 welcome-description">
                                {'Drag & drop product files here or type your message below. Press Ctrl/⌘ + Enter to send.'}
                          </p>
                        </div>
                        <div
                          className={cn(
                            "rounded-2xl border relative transition-all duration-300 shadow-lg hover:shadow-xl",
                            "bg-gradient-to-br from-white via-white to-gray-50/30 backdrop-blur-sm",
                            drag === "over" 
                              ? "border-emerald-400 bg-gradient-to-br from-emerald-50 to-emerald-100/50 shadow-emerald-200/50 scale-[1.02]" 
                              : "border-gray-200/60 hover:border-emerald-300/50",
                            isVisitor && visitorMessageCount >= VISITOR_MESSAGE_LIMIT && "opacity-50 cursor-not-allowed"
                          )}
                          onDragEnter={isVisitor && visitorMessageCount >= VISITOR_MESSAGE_LIMIT ? undefined : (e) => {
                            e.preventDefault();
                            setDrag("over");
                          }}
                          onDragOver={isVisitor && visitorMessageCount >= VISITOR_MESSAGE_LIMIT ? undefined : (e) => {
                            e.preventDefault();
                            setDrag("over");
                          }}
                          onDragLeave={isVisitor && visitorMessageCount >= VISITOR_MESSAGE_LIMIT ? undefined : (e) => {
                            e.preventDefault();
                            setDrag("idle");
                          }}
                          onDrop={isVisitor && visitorMessageCount >= VISITOR_MESSAGE_LIMIT ? undefined : onDrop}
                        >
                          <div className="p-5 sm:p-6">
                            <Textarea
                              value={input}
                              onChange={(e) => setInput(e.target.value)}
                              onKeyDown={handleKeyDown}
                              disabled={isVisitor && visitorMessageCount >= VISITOR_MESSAGE_LIMIT}
                              placeholder={
                                isVisitor && visitorMessageCount >= VISITOR_MESSAGE_LIMIT
                                  ? "Message limit reached. Sign a message to unlock unlimited conversations."
                                  : "Describe your ideal shop or business plan, upload your product files—DaVinci will take it from there."
                              }
                              className={cn(
                                "min-h-[120px] resize-y border-0 bg-transparent text-gray-800 placeholder:text-gray-500",
                                "focus:ring-0 focus:outline-none text-base leading-relaxed",
                                "transition-all duration-200",
                                isVisitor && visitorMessageCount >= VISITOR_MESSAGE_LIMIT && "opacity-50 cursor-not-allowed bg-gray-100"
                              )}
                            />
                            <div className="flex items-center justify-between mt-4">
                                  <div className="relative" ref={attachMenuRef}>
                              <Button
                                variant="ghost"
                                aria-label="Attach"
                                disabled={isVisitor && visitorMessageCount >= VISITOR_MESSAGE_LIMIT}
                                      className={cn(
                                        "h-12 w-12 p-0 rounded-xl transition-all duration-200 border shadow-sm",
                                        "bg-gradient-to-br from-white to-gray-50/80 border-gray-200/60",
                                        "hover:from-emerald-50 hover:to-emerald-100/50 hover:border-emerald-300/60 hover:shadow-md hover:scale-105",
                                        "active:scale-95 backdrop-blur-sm flex items-center justify-center",
                                        isVisitor && visitorMessageCount >= VISITOR_MESSAGE_LIMIT && "opacity-50 cursor-not-allowed"
                                      )}
                                      onClick={() => setShowAttachMenu(!showAttachMenu)}
                                    >
                                      <Paperclip className="h-5 w-5 text-gray-600 hover:text-emerald-700 transition-colors" />
                                    </Button>
                                    {showAttachMenu && (
                                      <div className="absolute bottom-full left-0 sm:left-0 mb-3 bg-white/95 backdrop-blur-md border border-gray-200/60 rounded-xl shadow-xl py-3 w-[220px] sm:min-w-[220px] z-50 animate-in slide-in-from-bottom-2 duration-200 -translate-x-1/2 sm:translate-x-0 overflow-hidden">
                                        <button
                                          className="flex items-center gap-3 w-full px-4 py-2 text-sm text-gray-700 hover:bg-gradient-to-r hover:from-blue-50 hover:to-blue-100/50 transition-all duration-200"
                                          onClick={() => {
                                            document.getElementById('file-input-top')?.click();
                                            setShowAttachMenu(false);
                                          }}
                                        >
                                          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-100 to-blue-200/50 flex items-center justify-center shadow-sm">
                                            <span className="text-lg">📁</span>
                                          </div>
                                          <div className="text-left">
                                            <div className="font-medium text-gray-800">Upload files</div>
                                            <div className="text-xs text-gray-500">Choose files from your device</div>
                                          </div>
                                        </button>
                                        <button
                                          className="flex items-center gap-3 w-full px-4 py-2 text-sm text-gray-700 hover:bg-gradient-to-r hover:from-green-50 hover:to-green-100/50 transition-all duration-200"
                                          onClick={() => {
                                            setShowUrlInput(true);
                                            setShowAttachMenu(false);
                                          }}
                                        >
                                          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-green-100 to-green-200/50 flex items-center justify-center shadow-sm">
                                            <span className="text-lg">🔗</span>
                                          </div>
                                          <div className="text-left">
                                            <div className="font-medium text-gray-800">Add from URL</div>
                                            <div className="text-xs text-gray-500">Link to file or image online</div>
                                          </div>
                                        </button>
                                      </div>
                                    )}
                                <input
                                      id="file-input-top"
                                  type="file"
                                  multiple
                                  className="hidden"
                                  onChange={(e) => onFilesSelected(e.target.files)}
                                />
                                  </div>
                                  {isGenerating && currentTaskId ? (
                                    <Button
                                      onClick={handleStopGeneration}
                                      variant="outline"
                                      aria-label="Stop generation"
                                      title="Stop generation (Esc)"
                                      className={cn(
                                        "h-12 w-12 p-0 rounded-xl transition-all duration-200 border shadow-sm",
                                        "bg-gradient-to-br from-red-50 to-red-100/60 border-red-200/70 text-red-600",
                                        "hover:from-red-100 hover:to-red-200/60 hover:border-red-300/70 hover:text-red-700 hover:shadow-md hover:scale-105",
                                        "active:scale-95 flex items-center justify-center relative"
                                      )}
                                    >
                                      <div className="relative">
                                        <Square className="h-5 w-5" />
                                        <span className="absolute -top-0.5 -right-0.5 h-2 w-2 bg-red-500 rounded-full animate-pulse" />
                                      </div>
                                    </Button>
                                  ) : (
                              <Button
                                onClick={onSend}
                                disabled={sending || (!input.trim() && files.length === 0) || (isVisitor && visitorMessageCount >= VISITOR_MESSAGE_LIMIT)}
                                aria-label="Send"
                                className={cn(
                                  "h-12 w-12 p-0 rounded-xl transition-all duration-200 shadow-md",
                                  "bg-gradient-to-br from-emerald-500 to-emerald-600 text-white border-0",
                                  "hover:from-emerald-600 hover:to-emerald-700 hover:shadow-lg hover:scale-105",
                                  "active:scale-95 disabled:from-gray-300 disabled:to-gray-400 disabled:shadow-sm disabled:scale-100",
                                  "flex items-center justify-center"
                                )}
                              >
                                {sending ? (
                                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                ) : (
                                  <Send className="h-5 w-5" />
                                )}
                              </Button>
                                  )}
                            </div>
                                {showUrlInput && (
                                  <div className="mt-4 p-4 bg-gradient-to-r from-gray-50 to-gray-100/50 rounded-xl border border-gray-200/60 animate-in slide-in-from-top-2 duration-200">
                                    <div className="flex gap-3">
                                      <input
                                        type="url"
                                        value={urlInput}
                                        onChange={(e) => setUrlInput(e.target.value)}
                                        placeholder="Enter file URL (e.g., https://example.com/image.jpg)"
                                        className={cn(
                                          "flex-1 px-4 py-3 bg-white border border-gray-200/60 rounded-xl text-sm",
                                          "focus:outline-none focus:ring-2 focus:ring-emerald-200 focus:border-emerald-300",
                                          "placeholder:text-gray-400 transition-all duration-200 shadow-sm"
                                        )}
                                        onKeyDown={(e) => {
                                          if (e.key === 'Enter') onUrlAdd();
                                          if (e.key === 'Escape') {
                                            setShowUrlInput(false);
                                            setUrlInput("");
                                          }
                                        }}
                                        autoFocus
                                      />
                                      <Button
                                        onClick={onUrlAdd}
                                        size="sm"
                                        disabled={!urlInput.trim()}
                                        className="px-4 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 transition-all duration-200 shadow-sm hover:shadow-md hover:scale-105 active:scale-95"
                                      >
                                        <span className="flex items-center gap-1">
                                          <span>Add</span>
                                          <span className="text-xs opacity-75">✓</span>
                                        </span>
                                      </Button>
                                      <Button
                                        onClick={() => {
                                          setShowUrlInput(false);
                                          setUrlInput("");
                                        }}
                                        size="sm"
                                        variant="outline"
                                        className="px-4 rounded-xl border-gray-300 hover:bg-gray-50 transition-all duration-200 hover:scale-105 active:scale-95"
                                      >
                                        <span className="flex items-center gap-1">
                                          <span>Cancel</span>
                                          <span className="text-xs opacity-75">✕</span>
                                        </span>
                                      </Button>
                                    </div>
                                  </div>
                                )}
                            <AttachmentChips
                              items={files}
                              onRemove={(id) =>
                                setFiles((prev) => prev.filter((f) => f.id !== id))
                              }
                            />
                            {sending && (
                              <div className="mt-4">
                                <MessageBubble role="system">
                                  <div className="flex items-center gap-3">
                                    <div className="flex space-x-1 items-center">
                                      <div className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{animationDelay: '-0.3s'}}></div>
                                      <div className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{animationDelay: '-0.15s'}}></div>
                                      <div className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce"></div>
                                    </div>
                                    <span className="text-sm text-muted-foreground animate-pulse">
                                      DaVinci is thinking...
                                    </span>
                                  </div>
                                </MessageBubble>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : !isLoadingHistory ? (
                    // Generative UI Chatbot rendering of message parts:
                        <div className="flex flex-col gap-6 pb-8">
                      {messages.map((m) => {
                        // Get tools for this message - check both message ID and 'current' for active streaming
                        const messageTools = toolExecutions.get(m.id) || [];
                        const currentTools = toolExecutions.get('current') || [];
                        const isLastMessage = m === messages[messages.length - 1];
                        
                        // For the last message, combine stored tools with current streaming tools
                        const finalTools = isLastMessage && currentTools.length > 0 ? currentTools : messageTools;
                        const lookupKey = isLastMessage && currentTools.length > 0 ? 'current' : m.id;
                        
                        if (finalTools.length > 0) {
                          console.log('🎯 Rendering tools for message:', m.id, 'lookup key:', lookupKey, 'tools count:', finalTools.length);
                          console.log('🎯 Tools:', finalTools.map(t => `${t.label}(${t.status})`));
                        }
                        
                        return (
                          <MessageBubble key={m.id} role={m.role as any} tools={m.role === 'assistant' ? finalTools : []}>
                            {m.parts.map((part, index) => {
                              switch (part.type) {
                                case "text":
                                  return m.role === 'assistant'
                                    ? <React.Fragment key={index}>{part.text}</React.Fragment>
                                    : <div key={index}>{part.text}</div>;
                                case "reasoning":
                                  return <pre key={index}>{part.text}</pre>;
                              // Example typed tool part rendering (will only appear if server provides tools)
                              case "tool-askForConfirmation": {
                                const callId = part.toolCallId;
                                switch (part.state) {
                                  case "input-streaming":
                                    return (
                                      <div key={callId}>Loading confirmation request...</div>
                                    );
                                  case "input-available":
                                    return (
                                      <div key={callId}>
                                        {(part.input as any)?.message}
                                        <div className="mt-2 flex gap-2">
                                          <Button
                                            size="sm"
                                            variant="secondary"
                                            onClick={() =>
                                              addToolResult({
                                                tool: "askForConfirmation",
                                                toolCallId: callId,
                                                output: "Yes, confirmed.",
                                              })
                                            }
                                          >
                                            Yes
                                          </Button>
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() =>
                                              addToolResult({
                                                tool: "askForConfirmation",
                                                toolCallId: callId,
                                                output: "No, denied",
                                              })
                                            }
                                          >
                                            No
                                          </Button>
                                        </div>
                                      </div>
                                    );
                                  case "output-available":
                                    return (
                                      <div key={callId}>
                                        Confirmation result: {String(part.output || '')}
                                      </div>
                                    );
                                  case "output-error":
                                    return <div key={callId}>Error: {part.errorText}</div>;
                                }
                                break;
                              }
                              case "tool-getLocation": {
                                const callId = part.toolCallId;
                                switch (part.state) {
                                  case "input-streaming":
                                    return <div key={callId}>Preparing location request...</div>;
                                  case "input-available":
                                    return <div key={callId}>Getting location...</div>;
                                  case "output-available":
                                    return <div key={callId}>Location: {String(part.output || '')}</div>;
                                  case "output-error":
                                    return <div key={callId}>Error: {part.errorText}</div>;
                                }
                                break;
                              }
                              default:
                                return null;
                            }
                          })}
                          {m.role === 'user' && (
                            <BubbleAttachmentPreview
                              attachments={(m as any)?.data?.clientAttachments as BubbleAttachment[] | undefined}
                              isUser
                            />
                          )}
                          </MessageBubble>
                        );
                      })}
                      
                      {/* Loading indicator when sending message - hide when we have tool executions */}
                      {sending && !toolExecutions.has('current') && (
                        <MessageBubble role="system">
                          <div className="flex items-center gap-3">
                                <div className="flex space-x-1 items-center">
                                  <div className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{animationDelay: '-0.3s'}}></div>
                                  <div className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" style={{animationDelay: '-0.15s'}}></div>
                              <div className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce"></div>
                            </div>
                                <span className="text-sm text-muted-foreground animate-pulse">
                                  DaVinci is thinking...
                                </span>
                          </div>
                        </MessageBubble>
                      )}
                    </div>
                  ) : null}
                </div>
              </div>

              {messages.length > 0 && (
                    <div className="px-6 py-5 border-t border-gray-100/60 bg-gradient-to-t from-white via-white to-gray-50/20 backdrop-blur-sm">
                      <div
                        className={cn(
                          "mx-auto max-w-4xl relative transition-all duration-300",
                          "bg-gradient-to-br from-white via-white to-gray-50/30 border border-gray-200/60 rounded-2xl shadow-lg hover:shadow-xl backdrop-blur-sm",
                          "p-5",
                          drag === "over" && "ring-2 ring-emerald-400/50 border-emerald-300 bg-gradient-to-br from-emerald-50 to-emerald-100/50 scale-[1.01]"
                        )}
                  onDragEnter={(e) => {
                    e.preventDefault();
                    setDrag("over");
                  }}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDrag("over");
                  }}
                  onDragLeave={(e) => {
                    e.preventDefault();
                    setDrag("idle");
                  }}
                  onDrop={onDrop}
                >
                      <div className="flex flex-col gap-3">
                        {connectionError && (
                          <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                            <span className="text-red-500">❌</span>
                            <span>{connectionError}</span>
                            <button 
                              onClick={() => setConnectionError(null)}
                              className="ml-auto text-red-400 hover:text-red-600 transition-colors"
                            >
                              ✕
                            </button>
                          </div>
                        )}
                        <div className="flex items-end gap-4">
                      <Textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Type a message or drop files here…"
                            className={cn(
                              "min-h-[56px] max-h-[160px] resize-y border-0 bg-transparent",
                              "focus:ring-0 focus:outline-none text-base text-gray-800 placeholder:text-gray-500",
                              "leading-relaxed transition-all duration-200"
                            )}
                          />
                          <div className="relative" ref={attachMenuBottomRef}>
                      <Button
                        variant="ghost"
                        aria-label="Attach"
                              className={cn(
                                "shrink-0 h-12 w-12 p-0 rounded-xl transition-all duration-200 border shadow-sm",
                                "bg-gradient-to-br from-white to-gray-50/80 border-gray-200/60",
                                "hover:from-emerald-50 hover:to-emerald-100/50 hover:border-emerald-300/60 hover:shadow-md hover:scale-105",
                                "active:scale-95 backdrop-blur-sm flex items-center justify-center"
                              )}
                              onClick={() => setShowAttachMenu(!showAttachMenu)}
                            >
                              <Paperclip className="h-5 w-5 text-gray-600 hover:text-emerald-700 transition-colors" />
                            </Button>
                            {showAttachMenu && (
                              <div className="absolute bottom-full left-0 sm:left-0 mb-3 bg-white/95 backdrop-blur-md border border-gray-200/60 rounded-xl shadow-xl py-3 w-[220px] sm:min-w-[220px] z-50 animate-in slide-in-from-bottom-2 duration-200 -translate-x-1/2 sm:translate-x-0 overflow-hidden">
                                <button
                                  className="flex items-center gap-3 w-full px-4 py-2 text-sm text-gray-700 hover:bg-gradient-to-r hover:from-blue-50 hover:to-blue-100/50 transition-all duration-200"
                                  onClick={() => {
                                    document.getElementById('file-input-bottom')?.click();
                                    setShowAttachMenu(false);
                                  }}
                                >
                                  <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-100 to-blue-200/50 flex items-center justify-center shadow-sm">
                                    <span className="text-lg">📁</span>
                                  </div>
                                  <div className="text-left">
                                    <div className="font-medium text-gray-800">Upload files</div>
                                    <div className="text-xs text-gray-500">Choose files from your device</div>
                                  </div>
                                </button>
                                <button
                                  className="flex items-center gap-3 w-full px-4 py-2 text-sm text-gray-700 hover:bg-gradient-to-r hover:from-green-50 hover:to-green-100/50 transition-all duration-200"
                                  onClick={() => {
                                    setShowUrlInput(true);
                                    setShowAttachMenu(false);
                                  }}
                                >
                                  <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-green-100 to-green-200/50 flex items-center justify-center shadow-sm">
                                    <span className="text-lg">🔗</span>
                                  </div>
                                  <div className="text-left">
                                    <div className="font-medium text-gray-800">Add from URL</div>
                                    <div className="text-xs text-gray-500">Link to file or image online</div>
                                  </div>
                                </button>
                              </div>
                            )}
                        <input
                              id="file-input-bottom"
                          type="file"
                          multiple
                          className="hidden"
                          onChange={(e) => onFilesSelected(e.target.files)}
                        />
                          </div>
                          {isGenerating && currentTaskId ? (
                            <Button
                              onClick={handleStopGeneration}
                              aria-label="Stop generation"
                              title="Stop generation (Esc)"
                              className={cn(
                                "shrink-0 h-12 w-12 p-0 rounded-xl transition-all duration-200 border shadow-sm",
                                "bg-gradient-to-br from-red-50 to-red-100/60 border-red-200/70 text-red-600",
                                "hover:from-red-100 hover:to-red-200/60 hover:border-red-300/70 hover:text-red-700 hover:shadow-md hover:scale-105",
                                "active:scale-95 flex items-center justify-center relative"
                              )}
                            >
                              <div className="relative">
                                <Square className="h-5 w-5" />
                                <span className="absolute -top-0.5 -right-0.5 h-2 w-2 bg-red-500 rounded-full animate-pulse" />
                              </div>
                      </Button>
                          ) : (
                      <Button
                        onClick={onSend}
                        disabled={sending || (!input.trim() && files.length === 0)}
                        aria-label="Send"
                              className={cn(
                                "shrink-0 h-12 w-12 p-0 rounded-xl transition-all duration-200 shadow-md",
                                "bg-gradient-to-br from-emerald-500 to-emerald-600 text-white border-0",
                                "hover:from-emerald-600 hover:to-emerald-700 hover:shadow-lg hover:scale-105",
                                "active:scale-95 disabled:from-gray-300 disabled:to-gray-400 disabled:shadow-sm disabled:scale-100",
                                "flex items-center justify-center"
                              )}
                      >
                        {sending ? (
                          <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        ) : (
                          <Send className="h-5 w-5" />
                        )}
                      </Button>
                          )}
                    </div>
                        {showUrlInput && (
                          <div className="mt-4 p-4 bg-gradient-to-r from-gray-50 to-gray-100/50 rounded-xl border border-gray-200/60 animate-in slide-in-from-top-2 duration-200">
                            <div className="flex gap-3">
                              <input
                                type="url"
                                value={urlInput}
                                onChange={(e) => setUrlInput(e.target.value)}
                                placeholder="Enter file URL (e.g., https://example.com/image.jpg)"
                                className={cn(
                                  "flex-1 px-4 py-3 bg-white border border-gray-200/60 rounded-xl text-sm",
                                  "focus:outline-none focus:ring-2 focus:ring-emerald-200 focus:border-emerald-300",
                                  "placeholder:text-gray-400 transition-all duration-200 shadow-sm"
                                )}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') onUrlAdd();
                                  if (e.key === 'Escape') {
                                    setShowUrlInput(false);
                                    setUrlInput("");
                                  }
                                }}
                                autoFocus
                              />
                              <Button
                                onClick={onUrlAdd}
                                size="sm"
                                disabled={!urlInput.trim()}
                                className="px-4 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 transition-all duration-200 shadow-sm hover:shadow-md hover:scale-105 active:scale-95"
                              >
                                <span className="flex items-center gap-1">
                                  <span>Add</span>
                                  <span className="text-xs opacity-75">✓</span>
                                </span>
                              </Button>
                              <Button
                                onClick={() => {
                                  setShowUrlInput(false);
                                  setUrlInput("");
                                }}
                                size="sm"
                                variant="outline"
                                className="px-4 rounded-xl border-gray-300 hover:bg-gray-50 transition-all duration-200 hover:scale-105 active:scale-95"
                              >
                                <span className="flex items-center gap-1">
                                  <span>Cancel</span>
                                  <span className="text-xs opacity-75">✕</span>
                                </span>
                              </Button>
                            </div>
                          </div>
                        )}
                    <AttachmentChips
                      items={files}
                      onRemove={(id) =>
                        setFiles((prev) => prev.filter((f) => f.id !== id))
                      }
                    />
                    
                    {/* 访客模式限制提示 - 美观版本 */}
                    {isVisitor && visitorMessageCount >= VISITOR_MESSAGE_LIMIT && (
                      <div className="mt-4 p-4 rounded-xl bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 shadow-lg">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
                            <span className="text-amber-600 text-lg">🔒</span>
                          </div>
                          <div className="flex-1">
                            <div className="font-semibold text-amber-800 mb-1">
                              Message Limit Reached
                            </div>
                            <div className="text-sm text-amber-700">
                              You've used all {VISITOR_MESSAGE_LIMIT} visitor messages. Sign a message to unlock unlimited conversations and save your chat history.
                            </div>
                          </div>
                          <Button
                            onClick={() => {
                              console.log('🔐 Chat area: Attempting to authenticate user...');
                              if (authenticateUser) {
                                authenticateUser();
                                console.log('✅ Chat area: Authentication triggered');
                              } else {
                                console.error('❌ Chat area: authenticateUser is undefined');
                                alert('Authentication not available. Please try refreshing the page.');
                              }
                            }}
                            disabled={isAuthenticating}
                            className="px-4 py-2 bg-gradient-to-r from-emerald-500 to-emerald-600 text-white rounded-lg hover:from-emerald-600 hover:to-emerald-700 transition-all duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {isAuthenticating ? 'Signing...' : 'Sign Message'}
                          </Button>
                        </div>
                      </div>
                    )}

                      </div>
                  </div>
                </div>
              )}
            </div>
              )}

              {activeMainTab === 'products' && (
            <div className="flex-1 flex flex-col p-6 overflow-y-auto mx-auto w-full max-w-5xl">
              <h2 className="text-xl font-semibold mb-4">Product Management</h2>
              <p className="text-muted-foreground mb-4">
                Upload your product list, and DaVinci will automatically generate optimized listings and publish them across supported e-commerce platforms.
              </p>
              <div className="border rounded-lg p-4 bg-white flex-1 flex items-center justify-center text-center text-muted-foreground">
                <p>Product listing and management features will appear here.</p>
              </div>
            </div>
          )}

              {activeMainTab === 'marketing' && (
            <div className="flex-1 flex flex-col p-6 overflow-y-auto mx-auto w-full max-w-5xl">
              <h2 className="text-xl font-semibold mb-4">Marketing & Promotion</h2>
              <p className="text-muted-foreground mb-4">
                DaVinci designs and executes data-driven marketing strategies, auto-generates engaging promotional content, and builds content commerce funnels.
              </p>
              <div className="border rounded-lg p-4 bg-white flex-1 flex items-center justify-center text-center text-muted-foreground">
                <p>Marketing campaign and social media features will appear here.</p>
              </div>
            </div>
          )}

              {activeMainTab === 'crm' && (
            <div className="flex-1 flex flex-col p-6 overflow-y-auto mx-auto w-full max-w-5xl">
              <h2 className="text-xl font-semibold mb-4">CRM User Management</h2>
              <p className="text-muted-foreground mb-4">
                Manage your buyer information, track interactions, and analyze customer data to enhance your e-commerce operations.
              </p>
              <div className="border rounded-lg p-4 bg-white flex-1 flex items-center justify-center text-center text-muted-foreground">
                <p>Buyer management features will appear here.</p>
              </div>
            </div>
              )}
            </>
          )}
        </div>
      </div>

      <footer className="w-full border-t">
        <div className="mx-auto max-w-5xl px-4 py-3 text-xs text-muted-foreground flex items-center justify-between">
          <span>{"© "} {new Date().getFullYear()} {" DaVinci"}</span>
          <span>{"A Multi-Agent AI System for Autonomous E-commerce Operations\n"}</span>
        </div>
      </footer>
    </main>
  );
}
