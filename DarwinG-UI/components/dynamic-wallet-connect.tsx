"use client";

import * as React from "react";
import { useDynamicContext, DynamicWidget, useAuthenticateConnectedUser } from "@dynamic-labs/sdk-react-core";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { Wallet, LogOut, Copy, CheckCircle } from 'lucide-react';

type DynamicWalletConnectProps = {
  className?: string;
  label?: string;
};

// Format address as 0x****...ABCD
function shortAddress(addr: string) {
  if (!addr) return "";
  return `${addr.substring(0, 6)}…${addr.slice(-4).toUpperCase()}`;
}

export function DynamicWalletConnect({ className, label = "Connect Wallet" }: DynamicWalletConnectProps) {
  const { user, primaryWallet, setShowAuthFlow, handleLogOut } = useDynamicContext();
  const { authenticateUser, isAuthenticating } = useAuthenticateConnectedUser();
  const [copied, setCopied] = React.useState(false);
  const [currentTheme, setCurrentTheme] = React.useState<'light' | 'hacker'>('light');

  // 检测当前主题
  React.useEffect(() => {
    const theme = document.documentElement.getAttribute('data-theme') as 'light' | 'hacker';
    setCurrentTheme(theme || 'light');
    
    // 监听主题变化
    const observer = new MutationObserver(() => {
      const newTheme = document.documentElement.getAttribute('data-theme') as 'light' | 'hacker';
      setCurrentTheme(newTheme || 'light');
    });
    
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme']
    });
    
    return () => observer.disconnect();
  }, []);

  const isHacker = currentTheme === 'hacker';

  const walletAddress = primaryWallet?.address;
  // 支持访客登录：只要有 primaryWallet 就认为已连接
  const isConnected = !!walletAddress;
  const isAuthenticated = !!user && !!walletAddress;
  const isVisitor = !!walletAddress && !user;

  const copyAddress = React.useCallback(async () => {
    if (walletAddress) {
      await navigator.clipboard.writeText(walletAddress);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [walletAddress]);

  // If label is empty string, it means sidebar is collapsed
  const showAddressText = label !== "";

  if (!isConnected) {
    return (
      <Button
        variant="outline"
        className={cn(
          "gap-2.5 transition-all duration-200 hover:shadow-md hover:scale-[1.02] active:scale-[0.98]",
          isHacker 
            ? "bg-gradient-to-r from-[#00ff41]/10 to-[#00ff41]/5 border-[#00ff41]/50 text-[#00ff41] hover:from-[#00ff41]/20 hover:to-[#00ff41]/10 hover:border-[#00ff41]/70 hover:shadow-[0_0_20px_rgba(0,255,65,0.3)] font-mono uppercase tracking-wider"
            : "bg-gradient-to-r from-emerald-25 to-emerald-50/80 border-emerald-150/50 text-emerald-700 hover:from-emerald-50 hover:to-emerald-100/70 hover:border-emerald-200/60 hover:text-emerald-800",
          className
        )}
        onClick={() => setShowAuthFlow(true)}
      >
        <Wallet className={cn("h-4 w-4", isHacker ? "text-[#00ff41]" : "text-emerald-700")} />
        {label}
      </Button>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button 
          variant="secondary" 
          className={cn(
            "gap-2.5 border-0 shadow-md hover:shadow-lg transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]",
            isHacker
              ? "bg-gradient-to-r from-[#58a6ff]/20 to-[#58a6ff]/10 text-[#58a6ff] hover:from-[#58a6ff]/30 hover:to-[#58a6ff]/15 hover:shadow-[0_0_25px_rgba(88,166,255,0.4)] font-mono"
              : "bg-gradient-to-r from-emerald-500 to-emerald-600 text-white hover:from-emerald-600 hover:to-emerald-700",
            className
          )}
        >
          <div className="relative">
            <Wallet className="h-4 w-4" />
            <div className={cn(
              "absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full animate-pulse border",
              isHacker 
                ? "bg-[#00ff41] border-[#0d1117]" 
                : "bg-green-400 border-white"
            )} />
          </div>
          {showAddressText && (
            <span className="font-mono text-sm">{shortAddress(walletAddress)}</span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className={cn(
        "rounded-xl shadow-xl min-w-[250px]",
        isHacker 
          ? "bg-[#0d1117] border-[#30363d] shadow-[0_0_20px_rgba(0,255,65,0.2)]"
          : "border-gray-200"
      )}>
        <div className={cn(
          "px-4 py-3 text-sm border-b",
          isHacker 
            ? "text-[#7d8590] border-[#30363d]"
            : "text-gray-600 border-gray-100"
        )}>
          <div className={cn(
            "font-medium mb-1",
            isHacker ? "text-[#00ff41]" : "text-gray-900"
          )}>
            {isAuthenticated ? 'Authenticated Wallet' : 'Visitor Wallet'}
          </div>
          <div className={cn(
            "font-mono text-xs px-2 py-1 rounded-md flex items-center justify-between",
            isHacker 
              ? "bg-[#161b22] text-[#58a6ff] border border-[#30363d]"
              : "bg-gray-50 text-gray-900"
          )}>
            <span className="truncate">{walletAddress}</span>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 ml-2"
              onClick={copyAddress}
            >
              {copied ? (
                <CheckCircle className={cn("h-3 w-3", isHacker ? "text-[#00ff41]" : "text-green-600")} />
              ) : (
                <Copy className={cn(
                  "h-3 w-3",
                  isHacker 
                    ? "text-[#7d8590] hover:text-[#58a6ff]"
                    : "text-gray-400 hover:text-gray-600"
                )} />
              )}
            </Button>
          </div>
          
          {/* 访客状态提示 */}
          {isVisitor && (
            <div className={cn(
              "text-xs mt-2 px-2 py-1 rounded-md border",
              isHacker
                ? "text-[#ffa500] bg-[#ffa500]/10 border-[#ffa500]/30"
                : "text-amber-600 bg-amber-50 border-amber-200"
            )}>
              ⚠️ Visitor Mode - Sign message to unlock full features
            </div>
          )}
          
          {/* 已认证用户信息 */}
          {isAuthenticated && user?.email && (
            <div className={cn(
              "text-xs mt-2",
              isHacker ? "text-[#7d8590]" : "text-gray-500"
            )}>
              📧 {user.email}
            </div>
          )}
          
          <div className={cn(
            "text-xs mt-1",
            isHacker ? "text-[#7d8590]" : "text-gray-500"
          )}>
            🌐 via Dynamic Wallet
          </div>
        </div>
        {/* 访客升级按钮 */}
        {isVisitor && (
          <DropdownMenuItem 
            onClick={() => {
              console.log('🔐 Attempting to authenticate user...');
              if (authenticateUser) {
                authenticateUser();
                console.log('✅ Authentication triggered');
              } else {
                console.error('❌ authenticateUser is undefined');
                alert('Authentication not available. Please try refreshing the page.');
              }
            }}
            disabled={isAuthenticating}
            className={cn(
              "transition-colors rounded-lg m-1",
              isHacker
                ? "text-[#00ff41] hover:text-[#00cc33] hover:bg-[#00ff41]/10"
                : "text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50"
            )}
          >
            <CheckCircle className="h-4 w-4 mr-2" />
            {isAuthenticating ? 'Signing...' : 'Sign Message to Authenticate'}
          </DropdownMenuItem>
        )}
        
        <DropdownMenuItem 
          onClick={handleLogOut} 
          className={cn(
            "transition-colors rounded-lg m-1",
            isHacker
              ? "text-[#ff4757] hover:text-[#ff3742] hover:bg-[#ff4757]/10"
              : "text-red-600 hover:text-red-700 hover:bg-red-50"
          )}
        >
          <LogOut className="h-4 w-4 mr-2" />
          Disconnect
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// 也可以直接使用Dynamic的默认Widget
export function DynamicWidgetSimple({ className }: { className?: string }) {
  return (
    <div className={className}>
      <DynamicWidget />
    </div>
  );
}

export default DynamicWalletConnect;