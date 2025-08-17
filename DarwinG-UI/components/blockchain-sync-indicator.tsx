"use client";

import React from 'react';
import { cn } from '@/lib/utils';
import { ExternalLink, Loader2, CheckCircle, AlertCircle, Link } from 'lucide-react';
import { type BlockchainSyncStatus } from '@/lib/blockchain';

interface BlockchainSyncIndicatorProps {
  syncStatus: BlockchainSyncStatus;
  className?: string;
}

export function BlockchainSyncIndicator({ syncStatus, className }: BlockchainSyncIndicatorProps) {
  console.log('🎯 BlockchainSyncIndicator rendering with status:', syncStatus);
  
  if (syncStatus.status === 'idle') {
    return null;
  }

  const getStatusIcon = () => {
    switch (syncStatus.status) {
      case 'preparing':
        return <Loader2 className="h-3 w-3 animate-spin" />;
      case 'waiting':
        return <Loader2 className="h-3 w-3 animate-spin" />;
      case 'confirmed':
        return <CheckCircle className="h-3 w-3" />;
      case 'failed':
        return <AlertCircle className="h-3 w-3" />;
      case 'skipped':
        return <AlertCircle className="h-3 w-3" />;
      case 'parse_failed':
        return <AlertCircle className="h-3 w-3" />;
      default:
        return <Link className="h-3 w-3" />;
    }
  };

  const getStatusText = () => {
    switch (syncStatus.status) {
      case 'preparing':
        return 'Preparing blockchain sync...';
      case 'waiting':
        return 'Waiting for confirmation...';
      case 'confirmed':
        return 'Synced to blockchain ✓';
      case 'failed':
        return `Sync failed: ${syncStatus.error || 'Unknown error'}`;
      case 'skipped':
        return `Sync skipped: ${syncStatus.reason === 'tool_response_not_successful' ? 'AI tool not successful' : syncStatus.reason || 'Not needed'}`;
      case 'parse_failed':
        return `Parse failed: ${syncStatus.error || 'Could not read AI response'}`;
      default:
        return 'Unknown status';
    }
  };

  const getStatusColor = () => {
    switch (syncStatus.status) {
      case 'preparing':
      case 'waiting':
        return 'text-blue-600 border-blue-200 bg-blue-50';
      case 'confirmed':
        return 'text-green-600 border-green-200 bg-green-50';
      case 'failed':
      case 'parse_failed':
        return 'text-red-600 border-red-200 bg-red-50';
      case 'skipped':
        return 'text-orange-600 border-orange-200 bg-orange-50';
      default:
        return 'text-gray-600 border-gray-200 bg-gray-50';
    }
  };

  const getExplorerUrl = () => {
    if (!syncStatus.txHash) return null;
    return `https://evm-testnet.flowscan.io/tx/${syncStatus.txHash}`;
  };

  return (
    <div className={cn(
      "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all duration-200",
      "backdrop-blur-sm",
      getStatusColor(),
      className
    )}>
      {getStatusIcon()}
      <span className="truncate max-w-[200px]">
        {getStatusText()}
      </span>
      
      {/* SKU信息 */}
      {syncStatus.sku && (
        <span className="text-xs opacity-75 font-mono">
          SKU: {syncStatus.sku}
        </span>
      )}
      
      {/* 交易链接 */}
      {syncStatus.txHash && (
        <a
          href={getExplorerUrl()!}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 hover:opacity-80 transition-opacity"
          title="View transaction on Flow EVM Testnet Explorer"
        >
          <ExternalLink className="h-3 w-3" />
        </a>
      )}
    </div>
  );
}

// interface BlockchainSyncBadgeProps {
//   syncStatus: BlockchainSyncStatus;
//   compact?: boolean;
// }

// export function BlockchainSyncBadge({ syncStatus, compact = false }: BlockchainSyncBadgeProps) {
//   if (syncStatus.status === 'idle') {
//     return null;
//   }

//   const getStatusEmoji = () => {
//     switch (syncStatus.status) {
//       case 'preparing':
//         return '⏳';
//       case 'waiting':
//         return '⏳';
//       case 'confirmed':
//         return '✅';
//       case 'failed':
//         return '❌';
//       case 'skipped':
//         return '⏭️';
//       case 'parse_failed':
//         return '🔧';
//       default:
//         return '🔗';
//     }
//   };

//   if (compact) {
//     return (
//       <span className="text-xs" title={`Blockchain sync: ${syncStatus.status}`}>
//         {getStatusEmoji()}
//       </span>
//     );
//   }

//   return (
//     <div className="flex items-center gap-1 text-xs opacity-75">
//       <span>{getStatusEmoji()}</span>
//       <span className="capitalize">{syncStatus.status}</span>
//       {syncStatus.txHash && (
//         <a
//           href={`https://evm-testnet.flowscan.io/tx/${syncStatus.txHash}`}
//           target="_blank"
//           rel="noopener noreferrer"
//           className="text-blue-600 hover:text-blue-800 transition-colors"
//           title="View on Flow EVM Testnet Explorer"
//         >
//           <ExternalLink className="h-3 w-3" />
//         </a>
//       )}
//     </div>
//   );
// }