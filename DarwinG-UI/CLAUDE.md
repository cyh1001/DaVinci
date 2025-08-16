# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DaVinci is an AI-powered multi-agent e-commerce ecosystem built with Next.js 15. The system provides autonomous e-commerce operations through a sophisticated AI agent system with a chat interface for product management, marketing automation, and CRM functionality. Built for the Dynamic.xyz hackathon, the application features non-custodial wallet integration with visitor mode support and comprehensive conversation history management.

## Development Commands

```bash
# Development server
pnpm dev

# Build production
pnpm build

# Start production server
pnpm start

# Lint code
pnpm lint
```

## Technology Stack

- **Frontend**: Next.js 15 with React 19, TypeScript, App Router
- **Styling**: Tailwind CSS v4.1.9 with Radix UI components
- **Package Manager**: pnpm (use pnpm-lock.yaml)
- **AI Integration**: Dify API with OpenAI fallback via @ai-sdk/react
- **Crypto Wallet**: Dynamic.xyz SDK with multi-chain support (Ethereum, Solana, Bitcoin, Flow)
- **Wallet Connectors**: MetaMask, WalletConnect, Coinbase, Social logins, Email authentication
- **Markdown**: react-markdown with remark-gfm for chat message rendering
- **Icons**: Lucide React icons
- **Fonts**: Geist Sans and Geist Mono fonts
- **Build**: Deployed on Vercel with unoptimized images

## Architecture

### Core Components

- **Main Chat Interface** (`app/page.tsx`): Multi-tab interface with chat, products, marketing, and CRM tabs. Contains complex state management for conversations, file attachments, wallet connections, and tool execution tracking
- **Chat API Route** (`app/api/chat/route.ts`): Handles AI conversations with Dify API primary, OpenAI fallback. Supports streaming responses, tool execution events, file attachments, and comprehensive error handling
- **Messages API Route** (`app/api/messages/route.ts`): Fetches conversation history from Dify API with pagination support
- **Conversations List API Route** (`app/api/conversations/route.ts`): Retrieves conversation list from Dify API for synchronization
- **Conversation Management API Route** (`app/api/conversations/[conversation_id]/route.ts`): Handles conversation operations (rename, delete) via Dify API
- **Upload API Route** (`app/api/upload/route.ts`): Handles file uploads to Dify API with validation
- **Stop API Route** (`app/api/stop/route.ts`): Enables stopping AI generation mid-stream
- **Sidebar Navigation** (`components/sidebar.tsx`): Collapsible sidebar with expandable conversation history, real-time Dify synchronization, and integrated theme switcher
- **Message Bubbles** (`components/chat-bubbles.tsx`): Markdown-enabled chat bubbles with file attachment support and tool execution display
- **Tool Execution Display** (`components/tool-execution.tsx`): Shows real-time AI tool usage and status
- **Dynamic Wallet Connect** (`components/dynamic-wallet-connect.tsx`): Handles Dynamic.xyz wallet integration with visitor mode support
- **Theme System** (`context/theme-context.tsx`, `components/theme-switcher.tsx`): Multi-theme support (Light, Dark, Auto, DaVinci Custom)
- **Dynamic Provider** (`lib/dynamic-config.tsx`): Dynamic.xyz SDK configuration with Wagmi integration
- **Conversation Utils** (`lib/conversation.ts`): Conversation management, localStorage operations, Dify data conversion, and synchronization utilities

### Key Features

- **Dynamic.xyz Wallet Integration**: Multi-chain wallet support with visitor mode functionality
  - **Visitor Mode**: Connect wallet without signing - limited features for onboarding
  - **Authenticated Mode**: Sign message to unlock full conversation history and features
  - **Multi-Chain Support**: Ethereum, Solana, Bitcoin, Flow networks
  - **Social Authentication**: Email, Google, Twitter, GitHub login options
  - **Non-Custodial**: Users maintain full control of their private keys
- **Multi-Conversation Management**: Complete conversation history with full CRUD operations
  - Create: New conversations automatically saved with generated titles
  - Read: Load conversation history from Dify API with message conversion
  - Update: Rename conversations with real-time Dify API synchronization
  - Delete: Complete removal from both Dify API and local storage
- **Data Synchronization**: Robust dual-layer data management
  - Dify API as authoritative data source
  - localStorage for performance and offline capability
  - Automatic sync on page load, rename, and delete operations
  - Conflict resolution favoring server-side data
- **Real-time Tool Execution**: AI agent tool usage tracking with real-time status updates
- **File Upload Support**: Both local file uploads and URL-based file sharing
  - Images: jpg, jpeg, png, gif, webp, svg
  - Documents: txt, md, pdf, html, xlsx, docx, csv, xml, epub, pptx
  - Audio: mp3, m4a, wav, webm, amr
  - Video: mp4, mov, mpeg, mpga
- **Streaming Responses**: Real-time streaming from Dify API with proper SSE handling and task management
- **Stop Generation**: Ability to interrupt AI responses mid-stream
- **Conversation Persistence**: Cross-session persistence segregated by wallet address
- **Expandable UI**: Conversation list toggles within sidebar with smooth animations
- **Theme System**: Multiple theme options with custom DaVinci branding
  - Light, Dark, Auto (system preference), DaVinci Custom themes
  - Persistent theme selection across sessions
  - Smooth theme transitions with CSS variables
- **Hydration Protection**: Prevents flash of incorrect state during page load
- **Loading States**: Unified loading system with progressive state indicators
- **Error Handling**: Comprehensive error recovery with user-friendly messages
- **Visitor Mode UX**: Clear indicators and upgrade prompts for unauthenticated users

### Configuration Notes

- Build configuration in `next.config.mjs` ignores TypeScript and ESLint errors during builds
- Path aliases use `@/*` mapping to root directory
- Images are set to `unoptimized: true` for Vercel deployment
- Environment variables: 
  - `DIFY_API_KEY` and `DIFY_API_BASE_URL` for AI integration
  - `NEXT_PUBLIC_DYNAMIC_ENVIRONMENT_ID` for Dynamic.xyz wallet integration
  - `DATABASE_URL` for MongoDB Atlas database connection

### State Management

- React useState/useRef for local component state  
- Dynamic.xyz SDK for wallet state management with persistent sessions
- localStorage for conversation persistence and theme preferences
- Context API for theme management and global state
- No external state management library - uses built-in React patterns with custom hooks

### Styling Conventions

- Tailwind CSS with emerald brand color scheme
- Radix UI components for consistent design system
- Responsive design with mobile-first approach
- Multi-theme system with CSS custom properties:
  - Light theme: Clean white backgrounds with emerald accents
  - Dark theme: Dark backgrounds with vibrant emerald highlights  
  - DaVinci Custom: Branded purple-emerald gradient theme
  - Auto theme: Follows system preference
- Gradient backgrounds and hover effects throughout UI
- Smooth animations and transitions for interactive elements
- Theme-aware component styling with conditional classes

## API Integration

### Dify API Endpoints Used
- `POST /chat-messages` - Send messages and get streaming responses with tool execution
- `POST /files/upload` - Upload files to Dify for processing
- `GET /conversations` - Retrieve conversation list for synchronization
- `GET /messages` - Load conversation message history with pagination
- `POST /conversations/{id}/name` - Rename conversations
- `DELETE /conversations/{id}` - Delete conversations
- `POST /chat-messages/{task_id}/stop` - Stop ongoing AI generation

### Data Flow
1. **Message Sending**: Frontend → Next.js API → Dify API → Streaming Response → Tool Execution Updates → UI Update
2. **File Upload**: File Selection → Upload API → Dify File Upload → File ID → Include in Message
3. **Conversation Management**: UI Action → Next.js API → Dify API → Local Storage Sync → UI Refresh
4. **Data Synchronization**: Page Load → Dify API → Merge with Local Data → Update UI
5. **Tool Execution**: AI Agent → Tool Calls → Real-time Status Updates → UI Display
6. **Stop Generation**: User Action → Stop API → Dify Task Termination → UI Reset

## Development Notes

When working on this codebase:
- Always use pnpm for package management
- The chat API prefers Dify but falls back to OpenAI - ensure both integrations work
- **Conversation Operations**: Always call Dify API first, then update local storage on success
- **Data Consistency**: Use `syncConversationsFromDify()` after any CRUD operations
- **Error Handling**: Gracefully fallback to local storage if Dify API is unavailable
- **File Upload Validation**: Ensure proper MIME type detection and file size limits
- **Tool Execution**: Tool status updates are streamed in real-time via SSE
- **State Management**: Complex state interactions between messages, tools, and conversations
- **Wallet Integration**: All functionality is gated behind wallet connection
- Markdown rendering in chat bubbles uses react-markdown with remark-gfm
- **Streaming Architecture**: Handle both text streaming and metadata events from Dify
- **Testing Checklist**:
  - Rename conversation → refresh page → title should persist
  - Delete conversation → refresh page → conversation should be gone
  - Create new conversation → should appear in sidebar immediately
  - Wallet disconnect/reconnect → should preserve correct user's conversations
  - File upload → verify file is included in message and processed correctly
  - Tool execution → check real-time status updates display properly
  - Stop generation → verify AI stops mid-stream and UI resets correctly
- Make sure all the code are modularization for future modification and easy debugging

## Important Implementation Details

### Tool Execution System
- Tool executions are tracked per message with unique IDs
- Status updates stream from Dify via agent_log events
- Tools are stored in localStorage for persistence across sessions
- Tool data is keyed by conversation + message position for reliability

### File Handling
- Supports both local file uploads and remote URL files
- File validation occurs on both client and server side
- Dify API expects specific file format: `{ type, transfer_method, upload_file_id/url }`
- File previews are handled differently for images vs. documents

### Streaming Implementation
- Uses Server-Sent Events (SSE) for real-time communication
- Handles multiple event types: message, agent_log, workflow_finished, error
- Metadata (conversation_id, task_id) is captured during streaming
- Tool execution events are converted to AI SDK compatible format

### Wallet Integration (Dynamic.xyz)
- **Non-Custodial Architecture**: Users retain full control of private keys
- **Multi-Chain Support**: Ethereum, Solana, Bitcoin, Flow networks
- **Visitor Mode**: Connect wallet without signing for onboarding experience
- **Authentication Flow**: Sign message to unlock full features and persistent data
- **User Identification**: Wallet address used for data segregation and user sessions
- **Connection Methods**: MetaMask, WalletConnect, Coinbase, social logins, email
- **State Management**: Dynamic SDK handles wallet state with React hooks integration
- **Error Handling**: Graceful fallbacks for connection failures and network issues
- **Wagmi Integration**: Ethereum interactions via Wagmi for enhanced DeFi compatibility

## Hackathon Integration - Dynamic.xyz

### Competition Category
- **"Best App Involving AI Built on Dynamic - $3,333"**
- Showcases Dynamic.xyz's non-custodial wallet infrastructure
- Demonstrates visitor mode for seamless user onboarding
- Multi-chain support for diverse user base

### Dynamic.xyz Features Implemented
- **Visitor Mode**: Users can connect wallets without signing for initial experience
- **Progressive Authentication**: Upgrade to full features via message signing
- **Multi-Chain Wallet Support**: Ethereum, Solana, Bitcoin, Flow
- **Social Authentication**: Email, Google, Twitter, GitHub login options
- **Enterprise Security**: Dynamic's infrastructure ensures secure key management
- **Real-time State Management**: Seamless wallet state across app lifecycle

### Technical Integration
- Environment ID: `0b7822a0-f446-4987-87f9-83b179f422e1`
- SDK Version: Latest Dynamic.xyz React SDK
- Wagmi Integration: For Ethereum ecosystem compatibility
- Custom UI Components: Branded wallet connection interface
- Progressive Enhancement: Visitor → Authenticated user journey