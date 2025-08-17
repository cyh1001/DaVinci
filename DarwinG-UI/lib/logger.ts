// Centralized logging utility with correlation IDs and conditional output
import { generateSKU } from './blockchain';

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogContext {
  walletAddress?: string;
  conversationId?: string;
  messageId?: string;
  toolName?: string;
  sku?: string;
  correlationId?: string;
}

class Logger {
  private correlationId: string;
  private isDevelopment: boolean;

  constructor() {
    this.correlationId = this.generateCorrelationId();
    this.isDevelopment = process.env.NODE_ENV === 'development';
  }

  private generateCorrelationId(): string {
    return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
  }

  private formatMessage(level: LogLevel, message: string, context?: LogContext): string {
    const timestamp = new Date().toISOString();
    const corrId = context?.correlationId || this.correlationId;
    
    let contextStr = '';
    if (context) {
      const parts = [];
      if (context.walletAddress) parts.push(`wallet:${context.walletAddress.slice(0, 6)}...${context.walletAddress.slice(-4)}`);
      if (context.conversationId) parts.push(`conv:${context.conversationId.slice(0, 8)}`);
      if (context.messageId) parts.push(`msg:${context.messageId.slice(0, 8)}`);
      if (context.toolName) parts.push(`tool:${context.toolName}`);
      if (context.sku) parts.push(`sku:${context.sku}`);
      if (parts.length > 0) {
        contextStr = ` [${parts.join(',')}]`;
      }
    }

    return `[${timestamp}] [${level.toUpperCase()}] [${corrId}]${contextStr} ${message}`;
  }

  debug(message: string, context?: LogContext): void {
    if (this.isDevelopment) {
      console.log(this.formatMessage('debug', message, context));
    }
  }

  info(message: string, context?: LogContext): void {
    console.info(this.formatMessage('info', message, context));
  }

  warn(message: string, context?: LogContext): void {
    console.warn(this.formatMessage('warn', message, context));
  }

  error(message: string, error?: Error, context?: LogContext): void {
    const errorMsg = error ? `${message}: ${error.message}` : message;
    console.error(this.formatMessage('error', errorMsg, context));
    if (error && this.isDevelopment) {
      console.error('Stack trace:', error.stack);
    }
  }

  // Specialized methods for common scenarios
  blockchainSync(message: string, context: LogContext & { sku: string }): void {
    this.info(`🔗 BLOCKCHAIN: ${message}`, context);
  }

  toolExecution(message: string, context: LogContext & { toolName: string }): void {
    this.debug(`🔧 TOOL: ${message}`, context);
  }

  conversationFlow(message: string, context: LogContext): void {
    this.debug(`💬 CONVERSATION: ${message}`, context);
  }

  stateChange(message: string, context: LogContext): void {
    this.debug(`🔄 STATE: ${message}`, context);
  }

  // Create child logger with persistent context
  withContext(context: LogContext): Logger {
    const childLogger = new Logger();
    childLogger.correlationId = context.correlationId || this.correlationId;
    
    // Override methods to include persistent context
    const originalDebug = childLogger.debug.bind(childLogger);
    const originalInfo = childLogger.info.bind(childLogger);
    const originalWarn = childLogger.warn.bind(childLogger);
    const originalError = childLogger.error.bind(childLogger);

    childLogger.debug = (message: string, additionalContext?: LogContext) => {
      originalDebug(message, { ...context, ...additionalContext });
    };

    childLogger.info = (message: string, additionalContext?: LogContext) => {
      originalInfo(message, { ...context, ...additionalContext });
    };

    childLogger.warn = (message: string, additionalContext?: LogContext) => {
      originalWarn(message, { ...context, ...additionalContext });
    };

    childLogger.error = (message: string, error?: Error, additionalContext?: LogContext) => {
      originalError(message, error, { ...context, ...additionalContext });
    };

    return childLogger;
  }
}

// Export singleton instance
export const logger = new Logger();

// Export factory for child loggers
export const createLogger = (context: LogContext) => logger.withContext(context);

// Export types for external use
export type { LogContext, LogLevel };