"use client";

import * as React from "react";
import { DynamicWalletConnect } from "@/components/dynamic-wallet-connect";
import { useDynamicContext } from "@dynamic-labs/sdk-react-core";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, MessageSquare, Package, Megaphone, Users, Plus, MoreHorizontal, Trash2, Edit, ChevronDown } from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { getConversations, syncConversationsFromDify, type Conversation } from "@/lib/conversation";
import { ThemeToggle } from "@/components/theme-toggle";

type SidebarProps = {
  className?: string;
  onSelectTab: (tab: 'chat' | 'products' | 'marketing' | 'crm') => void;
  activeTab: 'chat' | 'products' | 'marketing' | 'crm';
  currentConversationId?: string;
  onSelectConversation: (conversationId: string | undefined) => void;
  onNewConversation: () => void;
  onDeleteConversation: (conversationId: string) => void;
  onRenameConversation: (conversationId: string, newTitle: string) => void;
  refreshTrigger?: number; // Add refresh trigger prop
  isHydrated?: boolean; // Add hydration status prop
  defaultExpandConversations?: boolean; // Persisted expand state default
};

export function Sidebar({ 
  className, 
  onSelectTab, 
  activeTab, 
  currentConversationId, 
  onSelectConversation, 
  onNewConversation, 
  onDeleteConversation, 
  onRenameConversation,
  refreshTrigger,
  isHydrated: _parentIsHydrated,
  defaultExpandConversations = false
}: SidebarProps) {
  const [isCollapsed, setIsCollapsed] = React.useState(false);
  const [conversations, setConversations] = React.useState<Conversation[]>([]);
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [editingTitle, setEditingTitle] = React.useState("");
  const [showConversations, setShowConversations] = React.useState(false);
  const lastRefreshProcessedRef = React.useRef<number>(0);
  const conversationsRef = React.useRef<Conversation[]>([]); // ✅ 添加 ref 来存储当前值
  

  const SHOW_CONV_KEY = 'davinci_show_conversations';

  const setConversationsIfChanged = React.useRef(
    (current: Conversation[], next: Conversation[]) => {
      if (current.length !== next.length) return true;
      for (let i = 0; i < current.length; i++) {
        const a = current[i];
        const b = next[i];
        if (!b || a.id !== b.id || a.title !== b.title || a.updatedAt !== b.updatedAt) return true;
      }
      return false;
    }
  );

  // 从Dynamic获取钱包地址 - 稳定化处理
  const { primaryWallet, user } = useDynamicContext();
  const [walletAddress, setWalletAddress] = React.useState<string | null>(null);
  
  // 仅在primaryWallet.address实际变化时更新
  React.useEffect(() => {
    const newAddress = primaryWallet?.address || null;
    if (newAddress !== walletAddress) {
      setWalletAddress(newAddress);
    }
  }, [primaryWallet?.address, walletAddress]);

  // Initialize conversations expand state (persisted)
  React.useEffect(() => {
    if (typeof window === 'undefined') return;
    const saved = localStorage.getItem(SHOW_CONV_KEY);
    if (saved === '1') {
      setShowConversations(true);
    } else if (saved === '0') {
      setShowConversations(false);
    } else if (defaultExpandConversations) {
      setShowConversations(true);
      localStorage.setItem(SHOW_CONV_KEY, '1');
    }
  }, [defaultExpandConversations]);

  // Load conversations when wallet changes - sync with Dify (single pass per wallet change)
  React.useEffect(() => {
    if (walletAddress) {
      // First load local conversations immediately for better UX
      const localConvs = getConversations(walletAddress);
      if (setConversationsIfChanged.current(conversationsRef.current, localConvs)) {
        setConversations(localConvs);
        conversationsRef.current = localConvs; // ✅ 更新 ref
      }
      
      // Then sync with Dify in background
      syncConversationsFromDify(walletAddress)
        .then(syncedConvs => {
          if (setConversationsIfChanged.current(conversationsRef.current, syncedConvs)) {
            setConversations(syncedConvs);
            conversationsRef.current = syncedConvs; // ✅ 更新 ref
          }
          console.log('Synced conversations with Dify:', syncedConvs.length);
        })
        .catch(error => {
          console.warn('Failed to sync conversations with Dify:', error);
        });
    } else {
      setConversations([]);
      conversationsRef.current = []; // ✅ 更新 ref
    }
  }, [walletAddress]); // ✅ 只依赖 walletAddress

  // Refresh conversations when refreshTrigger changes (dedup by lastRefreshProcessedRef)
  React.useEffect(() => {
    if (walletAddress && refreshTrigger && refreshTrigger !== lastRefreshProcessedRef.current) {
      // Sync with Dify when refresh is triggered (e.g., after rename)
      syncConversationsFromDify(walletAddress)
        .then(syncedConvs => {
          if (setConversationsIfChanged.current(conversationsRef.current, syncedConvs)) {
            setConversations(syncedConvs);
            conversationsRef.current = syncedConvs; // ✅ 更新 ref
          }
          lastRefreshProcessedRef.current = refreshTrigger!;
          console.log('Refreshed conversations with Dify sync:', syncedConvs.length);
        })
        .catch(error => {
          console.warn('Failed to sync conversations during refresh:', error);
          // Fallback to local storage
          const convs = getConversations(walletAddress);
          if (setConversationsIfChanged.current(conversationsRef.current, convs)) {
            setConversations(convs);
            conversationsRef.current = convs; // ✅ 更新 ref
          }
        });
    }
  }, [walletAddress, refreshTrigger]);

  // ✅ 同步 conversations 状态到 ref
  React.useEffect(() => {
    conversationsRef.current = conversations;
  }, [conversations]);

  // No longer need to listen for wallet changes via localStorage
  // Dynamic handles wallet state internally

  const handleRename = (conversationId: string) => {
    const conv = conversations.find(c => c.id === conversationId);
    if (conv) {
      setEditingId(conversationId);
      setEditingTitle(conv.title);
    }
  };

  const confirmRename = () => {
    if (editingId && editingTitle.trim()) {
      onRenameConversation(editingId, editingTitle.trim());
      setEditingId(null);
      setEditingTitle("");
      // Refresh conversations
      if (walletAddress) {
        const convs = getConversations(walletAddress);
        setConversations(convs);
      }
    }
  };

  const cancelRename = () => {
    setEditingId(null);
    setEditingTitle("");
  };

  return (
    <aside
      className={cn(
        "flex flex-col h-full min-h-0 elegant-sidebar",
        isCollapsed ? "w-16" : "w-64",
        className
      )}
    >
      <div className={cn(
        "flex-1 overflow-y-auto",
        isCollapsed ? "p-3" : "p-5"
      )}>
        <div className={cn(
          "flex items-center justify-between",
          isCollapsed ? "mb-4" : "mb-6"
        )}>
          {!isCollapsed && (
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shadow-sm">
                <span className="text-white font-bold text-sm">D</span>
              </div>
              <h2 className="text-lg font-semibold bg-gradient-to-r from-gray-900 to-gray-700 bg-clip-text text-transparent">
                DaVinci
              </h2>
            </div>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsCollapsed(!isCollapsed)}
            className={cn(
              "ml-auto rounded-xl hover:bg-gray-100/80 transition-all duration-200 hover:scale-105 active:scale-95",
              isCollapsed && "mx-auto"
            )}
            aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {isCollapsed ? <ChevronRight className="h-4 w-4 text-gray-600" /> : <ChevronLeft className="h-4 w-4 text-gray-600" />}
          </Button>
        </div>
        <nav className={cn(
          "space-y-1.5",
          isCollapsed && "space-y-2"
        )}>
          {/* Chat Tab - Unified rendering logic */}
          {(() => {
            // 统一 Chat 按钮的渲染逻辑
            const shouldShowExpandedChat = !isCollapsed && walletAddress;
            const shouldShowSimpleChat = !walletAddress || isCollapsed;
            
            // 检查是否为访客模式
            const isVisitor = walletAddress && !user;
            
            if (shouldShowExpandedChat) {
              return (
                <div className="space-y-1">
                  <div className="flex items-center gap-1">
                    <div
                      className={cn(
                        "flex-1 elegant-nav-item cursor-pointer",
                        activeTab === 'chat' && "active"
                      )}
                      onClick={() => onSelectTab('chat')}
                    >
                      <MessageSquare className={cn(
                        "h-4 w-4 mr-2.5 transition-colors",
                        activeTab === 'chat' ? "text-emerald-600" : "text-gray-500"
                      )} />
                      Chat
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="px-2 rounded-lg hover:bg-gray-100/60 transition-all duration-200"
                      onClick={() => setShowConversations(prev => {
                        const next = !prev;
                        try { localStorage.setItem(SHOW_CONV_KEY, next ? '1' : '0'); } catch {}
                        return next;
                      })}
                    >
                      <ChevronDown className={cn(
                        "h-4 w-4 transition-all duration-200 text-gray-500", 
                        showConversations && "rotate-180 text-gray-700"
                      )} />
                    </Button>
                  </div>
                  
                  {/* Expandable conversations list */}
                  {showConversations && (
                    <div className="mt-3 pl-4 border-l border-gradient-to-b from-emerald-200/60 to-gray-200/40">
                      {/* 访客模式提示 */}
                      {isVisitor && (
                        <div className="mb-3 p-2 rounded-lg bg-amber-50 border border-amber-200">
                          <div className="flex items-center gap-2 text-amber-800">
                            <span className="text-xs">⚠️</span>
                            <span className="text-xs font-medium">Visitor Mode</span>
                          </div>
                          <p className="text-xs text-amber-700 mt-1">
                            Sign message to unlock conversation history and full features
                          </p>
                        </div>
                      )}
                      
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-medium text-gray-600 tracking-wide uppercase">Conversations</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={onNewConversation}
                          className="h-7 w-7 p-0 rounded-lg hover:bg-emerald-100/60 hover:text-emerald-700 transition-all duration-200 hover:scale-105"
                        >
                          <Plus className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                      <div className="space-y-1 max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent">
                        {conversations.map((conv, convIndex) => (
                          <div
                            key={`conv-${conv.id}-${convIndex}`}
                            className={cn(
                              "group flex items-center gap-2 px-3 py-2 rounded-lg text-sm cursor-pointer transition-all duration-200",
                              currentConversationId === conv.id 
                                ? "bg-gradient-to-r from-emerald-50 to-emerald-100/50 border border-emerald-200/50 shadow-sm" 
                                : "hover:bg-gray-100/60 hover:shadow-sm"
                            )}
                          >
                            {editingId === conv.id ? (
                              <input
                                type="text"
                                value={editingTitle}
                                onChange={(e) => setEditingTitle(e.target.value)}
                                onBlur={confirmRename}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') confirmRename();
                                  if (e.key === 'Escape') cancelRename();
                                }}
                                className="flex-1 bg-white/80 border border-emerald-200 rounded-md px-2 py-1 outline-none text-xs focus:ring-2 focus:ring-emerald-200 focus:border-emerald-300"
                                autoFocus
                              />
                            ) : (
                              <>
                                <div 
                                  className={cn(
                                    "flex-1 truncate text-xs font-medium transition-colors",
                                    currentConversationId === conv.id ? "text-emerald-800" : "text-gray-700 group-hover:text-gray-900"
                                  )}
                                  onClick={() => onSelectConversation(conv.id)}
                                >
                                  {conv.title}
                                </div>
                                <DropdownMenu>
                                  <DropdownMenuTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 rounded-md hover:bg-gray-200/60 transition-all duration-200"
                                    >
                                      <MoreHorizontal className="h-3 w-3 text-gray-500" />
                                    </Button>
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent align="end" className="rounded-xl shadow-lg border-gray-200">
                                    <DropdownMenuItem 
                                      onClick={() => handleRename(conv.id)}
                                      className="rounded-lg hover:bg-gray-50 transition-colors"
                                    >
                                      <Edit className="h-3 w-3 mr-2 text-gray-500" />
                                      Rename
                                    </DropdownMenuItem>
                                    <DropdownMenuItem 
                                      onClick={() => onDeleteConversation(conv.id)}
                                      className="text-red-600 rounded-lg hover:bg-red-50 hover:text-red-700 transition-colors"
                                    >
                                      <Trash2 className="h-3 w-3 mr-2" />
                                      Delete
                                    </DropdownMenuItem>
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              </>
                            )}
                          </div>
                        ))}
                        {conversations.length === 0 && (
                          <div className="px-3 py-6 text-xs text-gray-500 text-center italic">
                            No conversations yet
                            <div className="text-[10px] text-gray-400 mt-1">Start chatting to create one</div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            }
            
            if (shouldShowSimpleChat) {
              return (
                <div
                  className={cn(
                    "w-full elegant-nav-item cursor-pointer",
                    isCollapsed && "collapsed",
                    activeTab === 'chat' && "active"
                  )}
                  onClick={() => onSelectTab('chat')}
                >
                  <MessageSquare className={cn(
                    "h-4 w-4 transition-colors",
                    !isCollapsed && "mr-2.5",
                    activeTab === 'chat' ? "text-emerald-600" : "text-gray-500"
                  )} />
                  {!isCollapsed && "Chat"}
                </div>
              );
            }
            
            return null;
          })()}
          
          <div
            className={cn(
              "w-full elegant-nav-item cursor-pointer",
              isCollapsed && "collapsed",
              activeTab === 'products' && "active"
            )}
            onClick={() => onSelectTab('products')}
          >
            <Package className={cn(
              "h-4 w-4 transition-colors",
              !isCollapsed && "mr-2.5",
              activeTab === 'products' ? "text-emerald-600" : "text-gray-500"
            )} />
            {!isCollapsed && "Products"}
          </div>
          <div
            className={cn(
              "w-full elegant-nav-item cursor-pointer",
              isCollapsed && "collapsed",
              activeTab === 'marketing' && "active"
            )}
            onClick={() => onSelectTab('marketing')}
          >
            <Megaphone className={cn(
              "h-4 w-4 transition-colors",
              !isCollapsed && "mr-2.5",
              activeTab === 'marketing' ? "text-emerald-600" : "text-gray-500"
            )} />
            {!isCollapsed && "Marketing"}
          </div>
          <div
            className={cn(
              "w-full elegant-nav-item cursor-pointer",
              isCollapsed && "collapsed",
              activeTab === 'crm' && "active"
            )}
            onClick={() => onSelectTab('crm')}
          >
            <Users className={cn(
              "h-4 w-4 transition-colors",
              !isCollapsed && "mr-2.5",
              activeTab === 'crm' ? "text-emerald-600" : "text-gray-500"
            )} />
            {!isCollapsed && "CRM"}
          </div>
        </nav>
      </div>
      <div className="p-5 border-t border-gray-200/60 bg-gradient-to-t from-gray-50/30 to-transparent">
        
        {/* 主题切换器 */}
        {!isCollapsed && (
          <div className="mb-3">
            <ThemeToggle className="w-full" />
          </div>
        )}
        
        {/* Dynamic Wallet connection button at the bottom */}
        <DynamicWalletConnect 
          label={isCollapsed ? "" : "Connect Wallet"} 
          className={cn(
            "w-full transition-all duration-300 rounded-xl font-medium shadow-sm hover:shadow-md",
            isCollapsed && "px-0 justify-center"
          )} 
        />
      </div>
    </aside>
  );
}
