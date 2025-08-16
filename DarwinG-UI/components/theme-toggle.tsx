"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Monitor, Terminal } from "lucide-react";
import { cn } from "@/lib/utils";

export function ThemeToggle({ className }: { className?: string }) {
  const [theme, setTheme] = React.useState<'light' | 'hacker'>('light');
  const [mounted, setMounted] = React.useState(false);

  // 确保组件挂载后再显示，避免水合错误
  React.useEffect(() => {
    setMounted(true);
    const savedTheme = localStorage.getItem('davinci-theme') as 'light' | 'hacker';
    if (savedTheme) {
      setTheme(savedTheme);
      applyTheme(savedTheme);
    }
  }, []);

  const applyTheme = (newTheme: 'light' | 'hacker') => {
    document.documentElement.setAttribute('data-theme', newTheme);
    document.body.setAttribute('data-theme', newTheme);
    localStorage.setItem('davinci-theme', newTheme);
  };

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'hacker' : 'light';
    setTheme(newTheme);
    applyTheme(newTheme);
  };

  if (!mounted) {
    return null;
  }

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={toggleTheme}
      className={cn(
        "gap-2 transition-all duration-300 relative overflow-hidden",
        theme === 'hacker' 
          ? "border-[#00ff41] bg-[#00ff41]/10 text-[#00ff41] hover:bg-[#00ff41]/20 shadow-[0_0_20px_rgba(0,255,65,0.4)] hover:shadow-[0_0_30px_rgba(0,255,65,0.6)] font-mono uppercase tracking-wider"
          : "border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 shadow-sm hover:shadow-md",
        className
      )}
      style={theme === 'hacker' ? {
        animation: 'glow-pulse 2s infinite alternate'
      } : {}}
    >
      {theme === 'hacker' ? (
        <>
          <Terminal className="h-4 w-4" />
          <span className="hidden sm:inline font-mono">HACKER</span>
        </>
      ) : (
        <>
          <Monitor className="h-4 w-4" />
          <span className="hidden sm:inline">Light</span>
        </>
      )}
    </Button>
  );
}