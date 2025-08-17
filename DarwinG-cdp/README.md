# DarwinG-CDP: x402 Workflow Customization for AI Agent Wallet Management

## Overview

This project customizes the x402 payment protocol workflow to create tools that enable AI agents to control and manage cryptocurrency wallets autonomously. The main goal is to bridge the gap between AI agents and blockchain payments, allowing agents to automatically purchase tokens and services (such as OpenRouter API credits) using cryptocurrency.

## Project Architecture

### Core Components

1. **buyer_agent.py** - AI Agent Simulator
   - Simulates an AI agent workflow that can supervise and monitor token balances
   - Continuously monitors OpenRouter credit balance against a low watermark threshold
   - Automatically triggers top-up purchases when balance falls below the threshold
   - Supports both EOA (Externally Owned Account) and CDP (Coinbase Developer Platform) wallet management

2. **seller_service.py** - Middle Layer Service
   - Acts as a FastAPI-based seller service that bridges x402 protocol with OpenRouter API
   - Converts OpenRouter's native payment system (which doesn't support x402) to be x402-compatible
   - Enables AI agents to purchase OpenRouter credits by paying the seller in cryptocurrency
   - The seller then performs the actual backend API calls to credit the buyer's OpenRouter account

## Key Features

- **Autonomous Wallet Management**: AI agents can monitor and maintain their own cryptocurrency balances
- **Automatic Service Payments**: Seamlessly purchase API credits and other services using crypto
- **Protocol Bridge**: Converts non-x402 services to support x402 payment protocol
- **Multi-Wallet Support**: Compatible with both private key wallets and CDP managed wallets
- **Base Network Integration**: Operates on Base mainnet for efficient transactions

## Use Case Example

An AI agent operating autonomously needs to use OpenRouter for LLM API calls. The agent:

1. Monitors its OpenRouter credit balance continuously
2. When balance drops below a threshold (e.g., $20), automatically triggers a purchase
3. Uses x402 protocol to pay cryptocurrency to the seller service
4. Seller service converts the crypto payment to OpenRouter credits
5. Agent's balance is replenished and it can continue operating

## Technical Stack

- **Payment Protocol**: x402 for cryptocurrency payments
- **Blockchain**: Base network (mainnet)
- **Wallet Management**: Coinbase Developer Platform (CDP) or EOA
- **Web Framework**: FastAPI for seller service
- **HTTP Client**: httpx with x402 integration

## Configuration

Key environment variables:
- `OPENROUTER_KEY`: OpenRouter API key
- `LOW_BALANCE_THRESHOLD`: Minimum balance before triggering top-up
- `TOPUP_AMOUNT`: Amount to purchase during top-up
- `CDP_*`: Coinbase Developer Platform credentials
- `BUYER_PRIVATE_KEY`: Alternative EOA private key

## Experimental Results

We have successfully tested this system under the following configuration:

**Testnet Environment (Base-Sepolia)**
- **Seller Wallet**: Connected to Coinbase server wallet funded with ETH currency
- **Buyer Wallet**: Connected to wallet funded with USDC tokens
- **Test Scenario**: Buyer successfully paid 0.1 USDC to seller per transaction
- **OpenRouter Integration**: Skipped during testnet (OpenRouter requires mainnet for actual credit purchases)
- **Test Duration**: Continued until buyer's 1 USDC balance was fully consumed through multiple 0.1 USDC payments

The experiment validated the core x402 payment flow, wallet-to-wallet transactions, and automated payment triggers. The system successfully demonstrated autonomous payment capabilities between buyer and seller wallets using the x402 protocol on Base testnet.

This implementation enables AI agents to operate with greater autonomy by removing the need for manual intervention in payment processes, making them truly self-sufficient in managing their operational expenses.