// Blockchain interaction utilities for FM Listing Sync
import { parseUnits, formatUnits } from 'viem';


// FM Listing Sync Contract ABI (与合约事件完全对齐)
export const FM_LISTING_SYNC_ABI = [
  {
    "anonymous": false,
    "inputs": [
      { "indexed": true,  "internalType": "bytes32", "name": "skuHash",     "type": "bytes32" },
      { "indexed": false, "internalType": "string",  "name": "sku",         "type": "string"  },
      { "indexed": false, "internalType": "uint256", "name": "priceCents",  "type": "uint256" },
      { "indexed": true,  "internalType": "address", "name": "actor",       "type": "address" },
      { "indexed": false, "internalType": "address", "name": "currency",    "type": "address" }, // ← 非 indexed
      { "indexed": false, "internalType": "uint8",   "name": "decimals",    "type": "uint8"    },
      { "indexed": false, "internalType": "uint256", "name": "ts",          "type": "uint256" }
    ],
    "name": "ItemListed",
    "type": "event"
  },
  {
    "inputs": [
      { "internalType": "string",  "name": "sku",      "type": "string"  },
      { "internalType": "uint256", "name": "price",    "type": "uint256" },
      { "internalType": "address", "name": "currency", "type": "address" },
      { "internalType": "uint8",   "name": "decimals", "type": "uint8"   }
    ],
    "name": "syncListing",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  }
] as const;

// 币种配置
export const CURRENCY_CONFIG = {
  // 约定：address(0) 代表 “USDT(2dp) 展示/计价用”
  USDT2: {
    address: "0x0000000000000000000000000000000000000000" as `0x${string}`,
    decimals: 2,
  },
  // 若以后接入链上的真实 USDT(6dp)，新建此项并填入该网络 USDT ERC20 地址
  USDT6: {
    address: "0xYourUSDTAddressOnThisNetwork" as `0x${string}`,
    decimals: 6,
  }
} as const;

// SKU序列号管理
const skuSequences = new Map<string, number>();

// Global SKU tracking to prevent duplicates
const generatedSKUs = new Set<string>();
const pendingSKUs = new Map<string, number>(); // SKU -> timestamp

// 上链状态类型
export type BlockchainSyncStatus = {
  status: 'idle' | 'preparing' | 'waiting' | 'confirmed' | 'failed' | 'skipped' | 'parse_failed';
  sku?: string;
  txHash?: string;
  error?: string;
  reason?: string;
  timestamp?: number;
};

/**
 * 解析draft_to_listing工具响应
 */
export function parseDraftToListingResponse(toolResponse: string): any {
  try {
    // 去掉 "tool response: " 前缀
    const jsonString = toolResponse.replace(/^tool response:\s*/, '');
    return JSON.parse(jsonString);
  } catch (error) {
    console.error('Failed to parse draft_to_listing response:', error);
    return null;
  }
}

/**
 * 生成SKU: <ENV>-<CAT>-<EID前六位>-<SEQ>
 * Enhanced with deduplication to prevent race conditions
 */
export function generateSKU(category: string, eid: string): string {
  const env = "FM";
  const cat = category.substring(0, 3).toUpperCase();
  const eidPrefix = eid.substring(0, 6);
  
  let attempts = 0;
  const maxAttempts = 100;
  
  while (attempts < maxAttempts) {
    // 生成3位流水号
    const baseKey = `${env}-${cat}-${eidPrefix}`;
    const currentSeq = skuSequences.get(baseKey) || 0;
    const nextSeq = currentSeq + 1;
    skuSequences.set(baseKey, nextSeq);
    
    const seq = nextSeq.toString().padStart(3, '0');
    const sku = `${env}-${cat}-${eidPrefix}-${seq}`;
    
    // Check for duplicates (including pending SKUs)
    if (!generatedSKUs.has(sku) && !pendingSKUs.has(sku)) {
      generatedSKUs.add(sku);
      pendingSKUs.set(sku, Date.now());
      
      // Clean up old pending SKUs (older than 5 minutes)
      const fiveMinutesAgo = Date.now() - 5 * 60 * 1000;
      for (const [pendingSku, timestamp] of pendingSKUs.entries()) {
        if (timestamp < fiveMinutesAgo) {
          pendingSKUs.delete(pendingSku);
        }
      }
      
      return sku;
    }
    
    attempts++;
  }
  
  // Fallback with timestamp if unable to generate unique SKU
  const timestamp = Date.now().toString().slice(-6);
  const fallbackSku = `${env}-${cat}-${eidPrefix}-${timestamp}`;
  generatedSKUs.add(fallbackSku);
  return fallbackSku;
}

/**
 * 检查SKU是否已上链
 */
export function isSKUAlreadyOnChain(sku: string): boolean {
  if (typeof window === 'undefined') return false;
  
  const onChainSKUs = JSON.parse(localStorage.getItem('fm_onchain_skus') || '[]');
  return onChainSKUs.includes(sku);
}

/**
 * 记录SKU已上链
 */
export function markSKUAsOnChain(sku: string, txHash: string): void {
  if (typeof window === 'undefined') return;
  
  const onChainSKUs = JSON.parse(localStorage.getItem('fm_onchain_skus') || '[]');
  if (!onChainSKUs.includes(sku)) {
    onChainSKUs.push(sku);
    localStorage.setItem('fm_onchain_skus', JSON.stringify(onChainSKUs));
  }
  
  // 记录SKU到交易哈希的映射
  const skuTxMap = JSON.parse(localStorage.getItem('fm_sku_tx_map') || '{}');
  skuTxMap[sku] = txHash;
  localStorage.setItem('fm_sku_tx_map', JSON.stringify(skuTxMap));
}

/**
 * 获取SKU的交易哈希
 */
export function getSKUTxHash(sku: string): string | null {
  if (typeof window === 'undefined') return null;
  
  const skuTxMap = JSON.parse(localStorage.getItem('fm_sku_tx_map') || '{}');
  return skuTxMap[sku] || null;
}

/**
 * 检查draft_to_listing响应是否成功且需要上链
 */
export function shouldSyncToBlockchain(toolResponse: string): { shouldSync: boolean; data?: any } {
  const responseData = parseDraftToListingResponse(toolResponse);
  
  if (!responseData) {
    return { shouldSync: false };
  }
  
  // 检查success字段
  if (responseData.success !== true) {
    return { shouldSync: false };
  }
  
  // 生成SKU
  const sku = generateSKU(responseData.category, responseData.eid);
  
  // 检查是否已上链
  if (isSKUAlreadyOnChain(sku)) {
    console.log('SKU already on chain:', sku);
    return { shouldSync: false };
  }
  
  return { 
    shouldSync: true, 
    data: {
      ...responseData,
      generatedSKU: sku
    }
  };
}