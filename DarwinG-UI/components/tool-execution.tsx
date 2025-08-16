"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronRight, Clock, CheckCircle, Loader2, XCircle } from 'lucide-react';

export interface ToolExecution {
  id: string;
  name: string;
  label: string;
  status: 'start' | 'success' | 'error';
  startTime: number;
  endTime?: number;
  elapsedTime?: number;
  provider?: string;
  icon?: string;
  parentId?: string;
  error?: string;
  round?: string;
}

export interface ToolExecutionDisplayProps {
  tools: ToolExecution[];
  className?: string;
}

export function ToolExecutionDisplay({ tools, className }: ToolExecutionDisplayProps) {
  const [expandedTools, setExpandedTools] = React.useState<Set<string>>(new Set());
  const [collapsingTools, setCollapsingTools] = React.useState<Set<string>>(new Set());
  const collapseTimeouts = React.useRef<Map<string, NodeJS.Timeout>>(new Map());
  const prevStatusRef = React.useRef<Map<string, string>>(new Map());

  // Auto-expand rounds when they start and auto-collapse when they complete
  React.useEffect(() => {
    const runningRounds = tools.filter(tool => 
      tool.label.startsWith('ROUND ') && tool.status === 'start'
    );
    
    const completedRounds = tools.filter(tool => 
      tool.label.startsWith('ROUND ') && (tool.status === 'success' || tool.status === 'error')
    );
    
    // Check if this is a conversation switch (all tools changed at once)
    const prevToolIds = new Set(prevStatusRef.current.keys());
    const currentToolIds = new Set(tools.map(t => t.id));
    const isConversationSwitch = prevToolIds.size > 0 && 
      [...prevToolIds].every(id => !currentToolIds.has(id));
    
    // Auto-expand running rounds immediately
    if (runningRounds.length > 0) {
      setExpandedTools(prev => {
        const newExpanded = new Set(prev);
        runningRounds.forEach(round => {
          newExpanded.add(round.id);
          // Clear any pending collapse for this round
          const existingTimeout = collapseTimeouts.current.get(round.id);
          if (existingTimeout) {
            clearTimeout(existingTimeout);
            collapseTimeouts.current.delete(round.id);
          }
        });
        return newExpanded;
      });
      
      // Remove from collapsing state if it was collapsing
      setCollapsingTools(prev => {
        const newCollapsing = new Set(prev);
        runningRounds.forEach(round => newCollapsing.delete(round.id));
        return newCollapsing;
      });
    }
    
    // Auto-collapse completed rounds with smooth animation
    // Skip auto-collapse if this is a conversation switch to prevent unwanted collapsing
    if (!isConversationSwitch) {
      // Only collapse rounds that just transitioned to completed status
      const newlyCompleted = completedRounds.filter(round => {
        const prevStatus = prevStatusRef.current.get(round.id);
        return prevStatus === 'start' && (round.status === 'success' || round.status === 'error');
      });
      
      newlyCompleted.forEach(round => {
        // Skip if already collapsing or has pending collapse
        if (collapseTimeouts.current.has(round.id)) return;
        
        console.log('🎯 Scheduling auto-collapse for:', round.label);
        
        const timeout = setTimeout(() => {
          console.log('🎯 Starting collapse animation for:', round.label);
          
          // First, mark as collapsing for visual feedback
          setCollapsingTools(prev => new Set(prev).add(round.id));
          
          // After a brief moment, actually collapse
          setTimeout(() => {
            setExpandedTools(current => {
              const updated = new Set(current);
              updated.delete(round.id);
              console.log('🎯 Collapsed round:', round.label);
              return updated;
            });
            
            // Remove from collapsing state
            setCollapsingTools(prev => {
              const newCollapsing = new Set(prev);
              newCollapsing.delete(round.id);
              return newCollapsing;
            });
            
            // Clean up timeout reference
            collapseTimeouts.current.delete(round.id);
          }, 300); // Smooth collapse animation duration
          
        }, 1000); // Wait 1 second before starting collapse
        
        collapseTimeouts.current.set(round.id, timeout);
      });
    } else {
      console.log('🔄 Conversation switch detected, skipping auto-collapse');
      // Clear any pending collapse timers from previous conversation
      collapseTimeouts.current.forEach(timeout => clearTimeout(timeout));
      collapseTimeouts.current.clear();
      setCollapsingTools(new Set());
    }

    // Update previous statuses map after processing
    const nextStatuses = new Map<string, string>();
    tools.forEach(t => nextStatuses.set(t.id, t.status));
    prevStatusRef.current = nextStatuses;
    
    // Cleanup timeouts on unmount
    return () => {
      collapseTimeouts.current.forEach(timeout => clearTimeout(timeout));
      collapseTimeouts.current.clear();
    };
  }, [tools]);

  // Group tools by round and organize hierarchy
  const organizedTools = React.useMemo(() => {
    const rounds: { [key: string]: { round: ToolExecution; children: ToolExecution[] } } = {};
    
    // First, create a map of all tools by ID for easy lookup
    const toolsById: { [id: string]: ToolExecution } = {};
    tools.forEach(tool => {
      toolsById[tool.id] = tool;
    });

    // Organize tools into rounds with their children
    tools.forEach(tool => {
      if (tool.label.startsWith('ROUND ')) {
        const roundKey = tool.label;
        if (!rounds[roundKey]) {
          rounds[roundKey] = { round: tool, children: [] };
        }
        
        // Find all tools that have this round as their parent
        const children = tools.filter(t => 
          t.parentId === tool.id && 
          (t.label.startsWith('CALL ') || t.label.includes('Thought'))
        );
        
        rounds[roundKey].children = children;
      }
    });

    return { rounds };
  }, [tools]);

  const toggleExpanded = (toolId: string) => {
    const newExpanded = new Set(expandedTools);
    if (newExpanded.has(toolId)) {
      newExpanded.delete(toolId);
    } else {
      newExpanded.add(toolId);
    }
    setExpandedTools(newExpanded);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'start':
        return <Loader2 className="h-3 w-3 animate-spin text-blue-600" />;
      case 'success':
        return <CheckCircle className="h-3 w-3 text-green-600" />;
      case 'error':
        return <XCircle className="h-3 w-3 text-red-600" />;
      default:
        return <Clock className="h-3 w-3 text-gray-400" />;
    }
  };

  const formatElapsedTime = (elapsedTime?: number) => {
    if (!elapsedTime) return '';
    return elapsedTime < 1 ? `${(elapsedTime * 1000).toFixed(0)}ms` : `${elapsedTime.toFixed(1)}s`;
  };

  if (tools.length === 0) return null;

  return (
    <div className={cn("mt-3 space-y-2", className)}>
      {/* Show rounds with their child tools */}
      {Object.entries(organizedTools.rounds).map(([roundKey, roundData]) => {
        const mainRound = roundData.round;
        const childTools = roundData.children;
        const isExpanded = expandedTools.has(mainRound.id);
        const isCollapsing = collapsingTools.has(mainRound.id);
        
        return (
          <div 
            key={mainRound.id} 
            className={cn(
              "border border-gray-200/70 rounded-xl overflow-hidden transition-all duration-300 ease-in-out shadow-sm hover:shadow-md",
              "bg-white/50 backdrop-blur-sm",
              isCollapsing && "opacity-85 scale-[0.99] border-gray-300 shadow-none",
              mainRound.status === 'start' && "border-blue-200/60 shadow-blue-100/50",
              mainRound.status === 'success' && "border-green-200/60",
              mainRound.status === 'error' && "border-red-200/60"
            )}
          >
            <button
              onClick={() => toggleExpanded(mainRound.id)}
              className={cn(
                "w-full flex items-center justify-between bg-gradient-to-r from-gray-50/80 to-gray-100/40 hover:from-gray-100/90 hover:to-gray-150/50 transition-all duration-300",
                "backdrop-blur-sm border-b border-gray-200/40",
                isExpanded ? "px-4 py-2" : "px-4 py-1", // Thinner for both states
                isCollapsing && "bg-gray-100 opacity-90",
                mainRound.status === 'start' && "from-blue-50/60 to-blue-100/30 hover:from-blue-100/70 hover:to-blue-150/40",
                mainRound.status === 'success' && "from-green-50/60 to-green-100/30 hover:from-green-100/70 hover:to-green-150/40",
                mainRound.status === 'error' && "from-red-50/60 to-red-100/30 hover:from-red-100/70 hover:to-red-150/40"
              )}
            >
              <div className="flex items-center gap-2">
                {getStatusIcon(mainRound.status)}
                <div className="flex items-center gap-1">
                  <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Round
                  </span>
                  <span className="text-xs font-medium text-gray-500 uppercase tracking-wide tabular-nums">
                    {(mainRound.status === 'error' ? roundKey.replace(' (Interrupted)', '') : roundKey)
                      .replace(/^ROUND (\d+)/, (match, number) => number)}
                  </span>
                </div>
                {mainRound.status === 'start' && (
                  <span className="text-xs text-blue-600 animate-pulse">
                    Thinking...
                  </span>
                )}
                {mainRound.status === 'error' && (
                  <span className="text-xs text-red-600 font-medium">
                    Interrupted
                  </span>
                )}
                {isCollapsing && (
                  <span className="text-xs text-orange-600 animate-pulse">
                    Collapsing...
                  </span>
                )}
                {mainRound.status === 'success' && !isCollapsing && !isExpanded && (
                  <span className="text-xs text-green-600">
                    Complete
                  </span>
                )}
                {/* Show tool count */}
                {childTools.length > 0 && (
                  <span className="text-xs text-gray-600 bg-white/60 backdrop-blur-sm px-2.5 py-1 rounded-full border border-gray-200/50 shadow-sm">
                    {childTools.filter(t => t.label.startsWith('CALL ')).length} tools
                  </span>
                )}
              </div>
              
              <div className="flex items-center gap-2">
                {mainRound.elapsedTime && mainRound.status === 'success' && (
                  <span className="text-xs text-gray-500 font-mono bg-gray-100/50 px-2 py-0.5 rounded-md">
                    {formatElapsedTime(mainRound.elapsedTime)}
                  </span>
                )}
                <ChevronDown className={cn(
                  "h-4 w-4 text-gray-500 transition-transform duration-200 ease-in-out",
                  !isExpanded && "rotate-[-90deg]",
                  isCollapsing && "text-orange-500"
                )} />
              </div>
            </button>

            <div className={cn(
              "bg-gradient-to-b from-white/95 to-gray-50/30 border-t border-gray-200/60 overflow-hidden transition-all duration-300 ease-in-out backdrop-blur-sm",
              isExpanded ? "max-h-[2000px] opacity-100" : "max-h-0 opacity-0",
              isCollapsing && "bg-gray-50"
            )}>
                {/* Show child tools */}
                {childTools.map((tool) => (
                  <div key={tool.id} className="px-6 py-3 border-b border-gray-100/60 last:border-b-0 hover:bg-white/40 transition-colors duration-200">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-2 flex-1">
                        {getStatusIcon(tool.status)}
                        <span className={cn(
                          "text-sm",
                          tool.status === 'start' ? "text-blue-700" : "text-gray-600"
                        )}>
                          {tool.label.startsWith('CALL ') 
                            ? `🔧 ${tool.label.replace('CALL ', '')}`
                            : tool.label.includes('Thought')
                            ? `💭 AI Thinking`
                            : tool.label
                          }
                        </span>
                        {tool.status === 'start' && (
                          <span className="text-xs text-blue-600 animate-pulse">
                            Running...
                          </span>
                        )}
                        {tool.status === 'error' && (
                          <span className="text-xs text-red-600 font-medium">
                            Interrupted
                          </span>
                        )}
                      </div>
                      
                      {tool.elapsedTime && tool.status === 'success' && (
                        <span className="text-xs text-gray-500 font-mono bg-gray-100/50 px-1.5 py-0.5 rounded">
                          {formatElapsedTime(tool.elapsedTime)}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
                
                {/* Round summary */}
                <div className={cn(
                  "px-4 py-3 bg-gradient-to-r from-gray-50/80 to-gray-100/40 text-xs text-gray-600 transition-colors duration-300 border-t border-gray-200/40",
                  isCollapsing && "bg-gray-100"
                )}>
                  <div className="space-y-1">
                    <div>Round: {roundKey.replace(/^ROUND (\d+)/, (match, number) => `Round ${number}`)}</div>
                    {mainRound.elapsedTime && (
                      <div>Total Duration: {formatElapsedTime(mainRound.elapsedTime)}</div>
                    )}
                    <div>Status: {
                      mainRound.status === 'success' ? 'Completed' : 
                      mainRound.status === 'error' ? 'Interrupted' : 
                      'Running'
                    }</div>
                  </div>
                </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function ToolExecutionProvider({ children }: { children: React.ReactNode }) {
  return <div className="tool-execution-context">{children}</div>;
}