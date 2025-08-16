"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { Wallet, LogOut } from 'lucide-react';

type WalletConnectButtonProps = {
  className?: string;
  label?: string;
};

type ConnectResult = {
  address: string;
  provider: "porto" | "injected" | "mock";
};

export const STORAGE_KEY = "darwin1:wallet-address";
export const STORAGE_PROVIDER_KEY = "darwin1:wallet-provider";

// Format address as 0x****...ABCD (showing last 4 chars per requirement "显示地址的后面几个数")
function shortAddress(addr: string) {
  if (!addr) return "";
  const clean = addr;
  const tail = clean.slice(-4).toUpperCase();
  return `${clean.substring(0, 6)}…${tail}`;
}

async function connectWithPorto(): Promise<ConnectResult | null> {
  try {
    // "Porto" via Portto's Blocto SDK
    // Uses NEXT_PUBLIC_BLOCTO_APP_ID if provided, else will skip to fallback.
    const appId = (process as any).env?.NEXT_PUBLIC_BLOCTO_APP_ID as string | undefined;
    if (!appId) return null;

    const { default: BloctoSDK } = await import("@blocto/sdk");
    // Use mainnet RPC without key for demo; change as needed.
    const blocto = new (BloctoSDK as any)({
      ethereum: {
        chainId: 1,
        rpc: "https://cloudflare-eth.com",
      },
      appId,
    });
    const provider = blocto?.ethereum;
    if (!provider) return null;

    const accounts: string[] = await provider.request({ method: "eth_requestAccounts" });
    const address = accounts?.[0];
    if (!address) return null;

    return { address, provider: "porto" };
  } catch {
    return null;
  }
}

async function connectWithInjected(): Promise<ConnectResult | null> {
  try {
    const eth = (globalThis as any).ethereum;
    if (!eth) return null;
    const accounts: string[] = await eth.request({ method: "eth_requestAccounts" });
    const address = accounts?.[0];
    if (!address) return null;
    return { address, provider: "injected" };
  } catch {
    return null;
  }
}

function connectWithMock(): ConnectResult {
  // Dev/mock wallet for environments without SDKs. Persist so it looks stable.
  const cached = globalThis.localStorage?.getItem(STORAGE_KEY);
  if (cached) {
    return { address: cached, provider: "mock" };
  }
  const arr = new Uint8Array(20);
  globalThis.crypto.getRandomValues(arr);
  const hex = Array.from(arr)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  const address = `0x${hex}`;
  return { address, provider: "mock" };
}

export function WalletConnectButton(props: WalletConnectButtonProps) {
  const { className, label = "Connect Wallet" } = props;
  const [address, setAddress] = React.useState<string | null>(null);
  const [provider, setProvider] = React.useState<ConnectResult["provider"] | null>(null);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    const savedP = localStorage.getItem(STORAGE_PROVIDER_KEY) as ConnectResult["provider"] | null;
    if (saved) {
      setAddress(saved);
      setProvider(savedP ?? "mock");
    }
  }, []);

  const doConnect = React.useCallback(async () => {
    setLoading(true);
    try {
      // Try Porto (Portto / Blocto SDK) first if configured
      const porto = await connectWithPorto();
      if (porto) {
        setAddress(porto.address);
        setProvider(porto.provider);
        localStorage.setItem(STORAGE_KEY, porto.address);
        localStorage.setItem(STORAGE_PROVIDER_KEY, porto.provider);
        return;
      }

      // Fallback: injected (MetaMask etc.)
      const injected = await connectWithInjected();
      if (injected) {
        setAddress(injected.address);
        setProvider(injected.provider);
        localStorage.setItem(STORAGE_KEY, injected.address);
        localStorage.setItem(STORAGE_PROVIDER_KEY, injected.provider);
        return;
      }

      // Final fallback: mock
      const mock = connectWithMock();
      setAddress(mock.address);
      setProvider(mock.provider);
      localStorage.setItem(STORAGE_KEY, mock.address);
      localStorage.setItem(STORAGE_PROVIDER_KEY, mock.provider);
    } finally {
      setLoading(false);
    }
  }, []);

  const disconnect = React.useCallback(() => {
    setAddress(null);
    setProvider(null);
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(STORAGE_PROVIDER_KEY);
  }, []);

  if (!address) {
    return (
      <Button
        variant="outline"
        className={cn(
          "gap-2.5 bg-gradient-to-r from-emerald-25 to-emerald-50/80 border-emerald-150/50 text-emerald-700 hover:from-emerald-50 hover:to-emerald-100/70 hover:border-emerald-200/60 hover:text-emerald-800 transition-all duration-200 hover:shadow-md hover:scale-[1.02] active:scale-[0.98]",
          className
        )}
        onClick={doConnect}
        disabled={loading}
      >
        <Wallet className={cn(
          "h-4 w-4 transition-all duration-200",
          loading ? "animate-pulse text-emerald-600" : "text-emerald-700"
        )} />
        {loading ? (
          <span className="animate-pulse">Connecting...</span>
        ) : (
          label
        )}
      </Button>
    );
  }

  // If label is an empty string, it means the sidebar is collapsed, so hide the address text.
  const showAddressText = label !== "";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button 
          variant="secondary" 
          className={cn(
            "gap-2.5 bg-gradient-to-r from-emerald-500 to-emerald-600 text-white hover:from-emerald-600 hover:to-emerald-700 border-0 shadow-md hover:shadow-lg transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]",
            className
          )}
        >
          <div className="relative">
            <Wallet className="h-4 w-4" />
            <div className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-green-400 rounded-full animate-pulse border border-white" />
          </div>
          {showAddressText && (
            <>
              <span className="hidden sm:inline font-mono text-sm">{shortAddress(address)}</span>
              <span className="sm:hidden font-mono text-sm">{shortAddress(address)}</span>
            </>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="rounded-xl shadow-xl border-gray-200 min-w-[200px]">
        <div className="px-4 py-3 text-sm text-gray-600 border-b border-gray-100">
          <div className="font-medium text-gray-900 mb-1">Connected Wallet</div>
          <div className="font-mono text-xs bg-gray-50 px-2 py-1 rounded-md">{address}</div>
          <div className="text-xs mt-2 text-gray-500">
            via {provider === "porto" ? "Porto (Blocto)" : provider === "injected" ? "Injected Wallet" : "Mock Wallet"}
          </div>
        </div>
        <DropdownMenuItem 
          onClick={disconnect} 
          className="text-red-600 hover:text-red-700 hover:bg-red-50 transition-colors rounded-lg m-1"
        >
          <LogOut className="h-4 w-4 mr-2" />
          Disconnect
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default WalletConnectButton;
