"use client";

import {
  DynamicContextProvider,
  DynamicWidget,
} from "@dynamic-labs/sdk-react-core";

import { DynamicWagmiConnector } from "@dynamic-labs/wagmi-connector";
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createConfig, WagmiProvider } from 'wagmi';
import { http } from 'viem';
import { mainnet, polygon, arbitrum, base } from 'viem/chains';
import { BitcoinWalletConnectors } from "@dynamic-labs/bitcoin";
import { EthereumWalletConnectors } from "@dynamic-labs/ethereum";
import { FlowWalletConnectors } from "@dynamic-labs/flow";
import { SolanaWalletConnectors } from "@dynamic-labs/solana";

// Wagmi配置 - 参考Dynamic官方示例
const config = createConfig({
  chains: [mainnet, polygon, arbitrum, base],
  multiInjectedProviderDiscovery: false,
  transports: {
    [mainnet.id]: http(),
    [polygon.id]: http(),
    [arbitrum.id]: http(),
    [base.id]: http(),
  },
});

const queryClient = new QueryClient();

export function DynamicWalletProvider({ children }: { children: React.ReactNode }) {
  return (
    <DynamicContextProvider
      settings={{
        environmentId: process.env.NEXT_PUBLIC_DYNAMIC_ENVIRONMENT_ID || "",
        walletConnectors: [
          BitcoinWalletConnectors,
          EthereumWalletConnectors,
          FlowWalletConnectors,
          SolanaWalletConnectors,
        ],
        
        // DaVinci品牌定制
        appName: 'DaVinci AI Commerce',
        
        
        // 访客模式配置 - 使用官方推荐的方法
        initialAuthenticationMode: 'connect-only', // 启用仅连接模式（访客模式）
        enableVisitTrackingOnConnectOnly: true, // 启用访客追踪（可选）
        
        // CSS样式定制
        cssOverrides: `
          .dynamic-shadow-dom .dynamic-modal {
            --dynamic-color-primary: rgb(16, 185, 129);
            --dynamic-color-primary-hover: rgb(5, 150, 105);
          }
        `,
        
        // 事件处理
        events: {
          onAuthSuccess: (args) => console.log('✅ DaVinci: Connected successfully', args.user),
          onLogout: () => console.log('👋 DaVinci: Disconnected'),
          onSignedMessage: (args: any) => console.log('✍️ DaVinci: Message signed', args),
        },
      }}
    >
      <QueryClientProvider client={queryClient}>
        <WagmiProvider config={config}>
          <DynamicWagmiConnector>
            {children}
          </DynamicWagmiConnector>
        </WagmiProvider>
      </QueryClientProvider>
    </DynamicContextProvider>
  );
}

// 导出DynamicWidget供组件使用
export { DynamicWidget };
export default DynamicWalletProvider;