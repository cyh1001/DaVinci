#!/usr/bin/env python3
"""
Forest Market Draft MCP Server
简化的主服务器文件
"""

from fastmcp import FastMCP
from fastmcp.server.auth import StaticTokenVerifier
import os

try:
    from .tools import register_tools
except ImportError:
    from tools import register_tools

# 设置静态token认证
# 从环境变量获取token，如果没有则使用默认值
auth_token = os.getenv("MCP_AUTH_TOKEN", "DarwinGjzx-2025")
auth_verifier = StaticTokenVerifier(tokens={
    auth_token: {
        "client_id": "draft-mcp-client",
        "scopes": ["read", "write"]
    }
})

# 初始化FastMCP
# You can also add instructions for how to interact with the server
mcp = FastMCP(
    name="Forest Market Draft Manager",
    auth=auth_verifier,
    instructions="""
# Forest Market Product Draft Management System

Professional multi-user product draft management tool with complete Forest Market field support and workflow integration.

## Core Workflow
1. **Create Draft**: create_draft(user_id, title, ...) → get unique draft_id
2. **AI Optimization**: Use LLM to enhance product information
3. **Update & Refine**: update_draft(draft_id, **fields) → incremental or complete updates
4. **Export & List**: export_draft(draft_id) → generate Forest Market format

## Available Tools

### Basic Management
- `create_draft(user_id, title, ...)` - Create new draft, user_id required
- `get_draft(draft_id?, user_id?, summary_only?, batch_ids?)` - Enhanced get/summary tool
- `delete_draft(draft_id, user_id?)` - Delete draft safely

### Draft Updates
- `update_draft(draft_id, user_id?, **fields)` - Complete replacement of field values
- `add_to_draft(draft_id, user_id?, **content)` - Add items to arrays/objects without replacing existing data
- `remove_from_draft(draft_id, user_id?, **content)` - Remove specific items from arrays/objects

**Update Tool Selection Guide:**
- `update_draft`: Change price from 100 to 150, update title, replace entire tag list
- `add_to_draft`: Add Size XL to existing variations, add new image URL to existing images
- `remove_from_draft`: Remove tag "vintage" from existing tags, remove Size S from variations
- Rule: Use update_draft for scalar fields, add_to/remove_from for array/object modifications

### Search & Discovery
- `list_drafts(user_id?, query?, category?, condition?, min_price?, max_price?, limit?, offset?, with_stats?)` - Enhanced list/search/stats tool

### Export
- `export_draft(draft_id, user_id?)` - Forest Market compatible format

## Forest Market Fields

**Categories**: Digital Goods, DEPIN, Electronics, collectibles, Fashion, Custom, other
**Conditions**: New, Used
**Variations**: {"Size": ["S", "M", "L"], "Color": ["Red", "Blue", "Green"]}
**Ship From**: United States, Singapore, Hong Kong, South Korea, Japan
**Shipping Fees**: {"United States": 15.0, "Singapore": 10.0} (auto-cleared for Digital Goods)
**Discounts**: Fixed Amount (USDT) or Percentage
**Payment Methods**: ETH (Ethereum), ETH (Base), SOL (Solana), USDC (Ethereum), USDC (Base), USDC (Solana), USDT (Ethereum)

## Multi-User Isolation
- Each user can only access their own drafts
- user_id parameter provides permission control and data isolation  
- Admins can omit user_id to access all data

## Best Practices
- Always use draft_id for operations to avoid data confusion
- Digital Goods category auto-clears shipping-related fields
- Use search tools to discover existing content
- Version control is automatic - each update increments version number
- Test with get_summary before final export
    """
    )
    

# 注册所有工具
register_tools(mcp)

def main():
    """主函数入口"""
    mcp.run(transport="http")

if __name__ == "__main__":
    main()