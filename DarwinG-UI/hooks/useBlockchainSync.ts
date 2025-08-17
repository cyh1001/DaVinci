"use client";

import React, { useState, useCallback } from 'react';
import { useWriteContract, useWaitForTransactionReceipt, useAccount, useChainId, useSwitchChain } from 'wagmi';
import { parseUnits } from 'viem';
import { 
  FM_LISTING_SYNC_ABI, 
  CURRENCY_CONFIG, 
  generateSKU,
  markSKUAsOnChain,
  type BlockchainSyncStatus 
} from '@/lib/blockchain';
import { useDynamicContext } from '@dynamic-labs/sdk-react-core';

// Flow EVM Testnet Chain ID
const FLOW_EVM_TESTNET_CHAIN_ID = 545;
const FLOW_EVM_MAINNET_CHAIN_ID = 747;

// 合约地址配置 - 支持多链
const CONTRACT_ADDRESSES = {
  [FLOW_EVM_TESTNET_CHAIN_ID]: process.env.NEXT_PUBLIC_FM_LISTING_CONTRACT_ADDRESS_FLOW_TESTNET as `0x${string}`,
  [FLOW_EVM_MAINNET_CHAIN_ID]: process.env.NEXT_PUBLIC_FM_LISTING_CONTRACT_ADDRESS_FLOW_MAINNET as `0x${string}`,
  // 兼容旧环境变量
  default: process.env.NEXT_PUBLIC_FM_LISTING_CONTRACT_ADDRESS as `0x${string}`,
} as const;

export function useBlockchainSync() {
  const { address, isConnected, address: wagmiAddress, isConnected: wagmiIsConnected, chainId: wagmiChainId } = useAccount();
  const { primaryWallet } = useDynamicContext();
  const chainId = useChainId();
  const { switchChain } = useSwitchChain();
  const [syncStatus, setSyncStatus] = useState<BlockchainSyncStatus>({ status: 'idle' });
  
  // Debug logging for wallet connection state (development only)
  if (process.env.NODE_ENV === 'development') {
    console.log('🔍 Blockchain Sync Hook Debug:', {
      address: address || 'undefined',
      wagmiAddress: wagmiAddress || 'undefined',
      dynamicAddress: primaryWallet?.address || 'undefined',
      isConnected,
      wagmiIsConnected: wagmiIsConnected,
      wagmiChainId: wagmiChainId,
      isFlowEVMTestnet: wagmiChainId === 545,
      isFlowEVMMainnet: wagmiChainId === 747
    });
  }
  
  const { writeContract, data: hash, error: writeError, isPending: isWritePending } = useWriteContract();
  
  const { isLoading: isConfirming, isSuccess: isConfirmed } = useWaitForTransactionReceipt({
    hash,
  });

  // 获取当前链的合约地址
  const getContractAddress = useCallback(() => {
    return CONTRACT_ADDRESSES[chainId as keyof typeof CONTRACT_ADDRESSES] || CONTRACT_ADDRESSES.default;
  }, [chainId]);

  // 检查是否为Flow EVM网络
  const isFlowEVMNetwork = useCallback(() => {
    return chainId === FLOW_EVM_TESTNET_CHAIN_ID || chainId === FLOW_EVM_MAINNET_CHAIN_ID;
  }, [chainId]);

  // 切换到Flow EVM测试网
  const ensureFlowEVMNetwork = useCallback(async () => {
    if (!isFlowEVMNetwork()) {
      if (process.env.NODE_ENV === 'development') console.log('🔄 Switching to Flow EVM Testnet...');
      try {
        await switchChain({ chainId: FLOW_EVM_TESTNET_CHAIN_ID });
        if (process.env.NODE_ENV === 'development') console.log('✅ Successfully switched to Flow EVM Testnet');
        return true;
      } catch (error) {
        console.error('❌ Failed to switch to Flow EVM Testnet:', error);
        setSyncStatus({ 
          status: 'failed', 
          error: 'Failed to switch to Flow EVM Testnet. Please switch manually.',
          timestamp: Date.now()
        });
        return false;
      }
    }
    return true;
  }, [isFlowEVMNetwork, switchChain]);

  /**
   * 同步商品到区块链 - Enhanced for Flow EVM
   */
  const syncListing = useCallback(async (listingData: any) => {
    // Wallet check temporarily disabled to prevent React Strict Mode issues
    // if (!address || !isConnected) {
    //   console.error('❌ No wallet connected');
    //   setSyncStatus({ 
    //     status: 'failed', 
    //     error: 'Please connect your wallet first',
    //     timestamp: Date.now()
    //   });
    //   return;
    // }

    // 确保切换到Flow EVM网络
    const networkSwitched = await ensureFlowEVMNetwork();
    if (!networkSwitched) {
      return; // Error already set in ensureFlowEVMNetwork
    }

    const contractAddress = getContractAddress();
    if (!contractAddress) {
      console.error('❌ Contract address not configured for chain:', chainId);
      setSyncStatus({ 
        status: 'failed', 
        error: `Contract address not configured for ${isFlowEVMNetwork() ? 'Flow EVM' : 'current'} network`,
        timestamp: Date.now()
      });
      return;
    }

    try {
      // 生成SKU
      const sku = generateSKU(listingData.category, listingData.eid);
      if (process.env.NODE_ENV === 'development') console.log('📦 Generated SKU:', sku);

      setSyncStatus({ 
        status: 'preparing', 
        sku,
        timestamp: Date.now()
      });

      // 准备价格（使用两位 USDT（或按你命名用 USDT2）
      const priceInWei = parseUnits(listingData.price.toString(), CURRENCY_CONFIG.USDT2.decimals);
      
      if (process.env.NODE_ENV === 'development') {
        console.log('💰 Syncing to Flow EVM blockchain:', {
          sku,
          price: priceInWei.toString(),
          currency: CURRENCY_CONFIG.USDT2.address,
          decimals: CURRENCY_CONFIG.USDT2.decimals,
          contractAddress,
          chainId,
          network: isFlowEVMNetwork() ? 'Flow EVM' : 'Other'
        });
      }

      // 调用合约 - 使用动态合约地址
      await writeContract({
        address: contractAddress,
        abi: FM_LISTING_SYNC_ABI,
        functionName: 'syncListing',
        args: [
          sku,
          priceInWei,
          CURRENCY_CONFIG.USDT2.address,
          CURRENCY_CONFIG.USDT2.decimals
        ],
        chainId: isFlowEVMNetwork() ? chainId : FLOW_EVM_TESTNET_CHAIN_ID, // 强制使用Flow EVM
      });

      setSyncStatus({ 
        status: 'waiting', 
        sku,
        timestamp: Date.now()
      });

    } catch (error) {
      console.error('❌ Failed to sync listing to Flow EVM:', error);
      setSyncStatus(prevStatus => ({ 
        status: 'failed', 
        sku: prevStatus.sku,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: Date.now()
      }));
    }
  }, [address, writeContract, chainId, isFlowEVMNetwork, ensureFlowEVMNetwork, getContractAddress]);

  // 监听交易确认
  React.useEffect(() => {
    if (isConfirmed && hash && syncStatus.sku) {
      if (process.env.NODE_ENV === 'development') console.log('✅ Transaction confirmed:', hash);
      
      // 记录SKU已上链
      markSKUAsOnChain(syncStatus.sku, hash);
      
      setSyncStatus({ 
        status: 'confirmed', 
        sku: syncStatus.sku,
        txHash: hash,
        timestamp: Date.now()
      });
    }
  }, [isConfirmed, hash, syncStatus.sku]);

  // 监听写入错误
  React.useEffect(() => {
    if (writeError) {
      console.error('❌ Write contract error:', writeError);
      setSyncStatus(prevStatus => ({ 
        status: 'failed', 
        sku: prevStatus.sku,
        error: writeError.message,
        timestamp: Date.now()
      }));
    }
  }, [writeError]);

  return {
    syncStatus,
    syncListing,
    isLoading: isWritePending || isConfirming,
    reset: () => setSyncStatus({ status: 'idle' }),
    // 新增Flow EVM相关状态
    isFlowEVMNetwork: isFlowEVMNetwork(),
    currentChainId: chainId,
    ensureFlowEVMNetwork,
  };
}