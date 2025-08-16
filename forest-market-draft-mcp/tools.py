"""
MCP工具函数定义
"""

from typing import List, Dict, Optional, Annotated, Literal
from fastmcp import FastMCP
from pydantic import Field

try:
    from .models import ProductDraft
    from .storage import DraftStorage
except ImportError:
    from models import ProductDraft
    from storage import DraftStorage

# 初始化存储
storage = DraftStorage()

def register_tools(mcp: FastMCP):
    """注册所有MCP工具"""
    
    @mcp.tool(
        name="create_draft",
        description="Create a new Forest Market product draft with comprehensive field support"
    )
    def create_draft(
        user_id: Annotated[str, Field(description="Unique user identifier for draft ownership and access control")],
        title: Annotated[str, Field(description="Product name/title (required for meaningful draft)")] = "",
        description: Annotated[str, Field(description="Detailed product description and selling points")] = "",
        price: Annotated[float, Field(description="Product price in USDT (must be >= 0)", ge=0)] = 0.0,
        category: Annotated[Literal["Digital Goods", "DEPIN", "Electronics", "collectibles", "Fashion", "Custom", "other"], Field(description="Forest Market product category")] = "other",
        condition: Annotated[Literal["New", "Used"], Field(description="Product condition/state")] = "New",
        variations: Annotated[Optional[Dict[str, List[str]]], Field(description="Product variations: {'Size': ['S','M','L'], 'Color': ['Red','Blue']}")] = None,
        images: Annotated[Optional[List[str]], Field(description="Product image URLs (recommended for listings)")] = None,
        contact_email: Annotated[str, Field(description="Seller contact email address")] = "",
        ship_from: Annotated[Optional[Literal["United States", "Singapore", "Hong Kong", "South Korea", "Japan"]], Field(description="Shipping origin (auto-cleared for Digital Goods)")] = None,
        ship_to: Annotated[Optional[List[Literal["United States", "Singapore", "Hong Kong", "South Korea", "Japan"]]], Field(description="Shipping destinations (auto-cleared for Digital Goods)")] = None,
        shipping_fees: Annotated[Optional[Dict[str, float]], Field(description="Shipping costs by destination: {'United States': 15.0} (auto-cleared for Digital Goods)")] = None,
        quantity: Annotated[int, Field(description="Available stock quantity (minimum 1)", ge=1)] = 1,
        discount_type: Annotated[Optional[Literal["", "Fixed Amount", "Percentage"]], Field(description="Discount type (leave empty for no discount)")] = None,
        discount_value: Annotated[float, Field(description="Discount amount (USDT for fixed, 10-50% for percentage)", ge=0)] = 0.0,
        payout_methods: Annotated[Optional[List[Literal["ETH (Ethereum)", "ETH (Base)", "SOL (Solana)", "USDC (Ethereum)", "USDC (Base)", "USDC (Solana)", "USDT (Ethereum)"]]], Field(description="Accepted crypto payment methods")] = None,
        tags: Annotated[Optional[List[str]], Field(description="Search tags for better discoverability")] = None,
        specifications: Annotated[Optional[Dict[str, str]], Field(description="Technical specs: {'Brand': 'Apple', 'Model': 'iPhone 15'}")] = None
    ) -> Dict[str, any]:
        """Create a new Forest Market product draft with comprehensive field validation
        
        Automatically handles Digital Goods by clearing shipping fields.
        Creates unique draft_id and initializes version control.
        
        Returns:
            Dictionary containing draft_id, title, created_at timestamp, and status
        """
        # Auto-clear shipping fields for Digital Goods
        if category == "Digital Goods":
            ship_from = ""
            ship_to = []
            shipping_fees = {}
        
        draft = ProductDraft(
            title=title,
            user_id=user_id,
            description=description,
            price=price,
            category=category,
            condition=condition,
            variations=variations or {},
            images=images or [],
            contact_email=contact_email,
            ship_from=ship_from or "",
            ship_to=ship_to or [],
            shipping_fees=shipping_fees or {},
            quantity=quantity,
            discount_type=discount_type or "",
            discount_value=discount_value,
            payout_methods=payout_methods or [],
            tags=tags or [],
            specifications=specifications or {}
        )
        
        draft_id = storage.create_draft(draft)
        
        return {
            "draft_id": draft_id,
            "title": title,
            "created_at": draft.created_at,
            "status": "created"
        }

    @mcp.tool(
        name="get_draft",
        description="Retrieve draft information with flexible output modes: full details, summary, or batch processing"
    )
    def get_draft(
        draft_id: Annotated[Optional[str], Field(description="Draft ID to retrieve (required unless using batch_ids)")] = None,
        user_id: Annotated[Optional[str], Field(description="User ID for ownership verification and access control")] = None,
        summary_only: Annotated[bool, Field(description="Return summary instead of full draft details")] = False,
        batch_ids: Annotated[Optional[List[str]], Field(description="Multiple draft IDs for batch retrieval (overrides draft_id)")] = None
    ) -> Dict[str, any]:
        """Unified draft retrieval tool with multiple modes
        
        Supports single/batch retrieval with full details or summary-only output.
        Includes user permission validation for secure access.
        
        Args:
            draft_id: Single draft ID to retrieve
            user_id: User permission check
            summary_only: Return summary instead of full details
            batch_ids: Process multiple drafts at once
            
        Returns:
            Single draft, draft summary, or batch results based on parameters
        """
        # Batch processing mode
        if batch_ids:
            results = []
            for bid in batch_ids:
                draft = storage.get_draft(bid)
                if not draft:
                    results.append({"draft_id": bid, "error": "Not found"})
                    continue
                
                # User permission check
                if user_id and draft.user_id and draft.user_id != user_id:
                    results.append({"draft_id": bid, "error": "Access denied"})
                    continue
                
                if summary_only:
                    results.append({
                        "draft_id": draft.draft_id,
                        "user_id": draft.user_id,
                        "title": draft.title,
                        "price": draft.price,
                        "category": draft.category,
                        "condition": draft.condition,
                        "quantity": draft.quantity,
                        "ship_from": draft.ship_from,
                        "last_updated": draft.updated_at,
                        "version": draft.version
                    })
                else:
                    results.append(draft.to_dict())
            
            return {
                "total_processed": len(batch_ids),
                "successful": len([r for r in results if "error" not in r]),
                "results": results
            }
        
        # Single draft mode
        if not draft_id:
            return {"error": "draft_id is required when not using batch_ids"}
        
        draft = storage.get_draft(draft_id)
        if not draft:
            return {"error": f"Product draft {draft_id} not found"}
        
        # User permission check
        if user_id and draft.user_id and draft.user_id != user_id:
            return {"error": "Access denied: Draft belongs to different user"}
        
        # Return summary or full details
        if summary_only:
            return {
                "draft_id": draft.draft_id,
                "user_id": draft.user_id,
                "title": draft.title,
                "price": draft.price,
                "category": draft.category,
                "condition": draft.condition,
                "quantity": draft.quantity,
                "ship_from": draft.ship_from,
                "ship_to_count": len(draft.ship_to),
                "has_shipping_fees": bool(draft.shipping_fees),
                "variations_count": len(draft.variations),
                "tags_count": len(draft.tags),
                "images_count": len(draft.images),
                "payout_methods_count": len(draft.payout_methods),
                "has_description": bool(draft.description),
                "has_contact_email": bool(draft.contact_email),
                "has_discount": bool(draft.discount_type),
                "has_specifications": bool(draft.specifications),
                "last_updated": draft.updated_at,
                "version": draft.version
            }
        else:
            return draft.to_dict()

    @mcp.tool(
        name="update_draft",
        description="Update Forest Market draft with new field values - complete replacement mode"
    )
    def update_draft(
        draft_id: Annotated[str, Field(description="Draft ID to update (required)")],
        user_id: Annotated[Optional[str], Field(description="User ID for ownership verification")] = None,
        title: Annotated[Optional[str], Field(description="Updated product title/name")] = None,
        description: Annotated[Optional[str], Field(description="Updated product description")] = None,
        price: Annotated[Optional[float], Field(description="Updated price in USDT (>= 0)", ge=0)] = None,
        category: Annotated[Optional[Literal["Digital Goods", "DEPIN", "Electronics", "collectibles", "Fashion", "Custom", "other"]], Field(description="Updated Forest Market category")] = None,
        condition: Annotated[Optional[Literal["New", "Used"]], Field(description="Updated product condition")] = None,
        variations: Annotated[Optional[Dict[str, List[str]]], Field(description="Updated variations (replaces existing): {'Size': ['S','M','L']}")] = None,
        images: Annotated[Optional[List[str]], Field(description="Updated image URLs (replaces existing list)")] = None,
        contact_email: Annotated[Optional[str], Field(description="Updated seller contact email")] = None,
        ship_from: Annotated[Optional[Literal["United States", "Singapore", "Hong Kong", "South Korea", "Japan"]], Field(description="Updated shipping origin (auto-cleared for Digital Goods)")] = None,
        ship_to: Annotated[Optional[List[Literal["United States", "Singapore", "Hong Kong", "South Korea", "Japan"]]], Field(description="Updated shipping destinations (auto-cleared for Digital Goods)")] = None,
        shipping_fees: Annotated[Optional[Dict[str, float]], Field(description="Updated shipping fees (auto-cleared for Digital Goods)")] = None,
        quantity: Annotated[Optional[int], Field(description="Updated stock quantity (>= 1)", ge=1)] = None,
        discount_type: Annotated[Optional[Literal["", "Fixed Amount", "Percentage"]], Field(description="Updated discount type (empty string removes discount)")] = None,
        discount_value: Annotated[Optional[float], Field(description="Updated discount value (USDT for fixed, 10-50% for percentage)", ge=0)] = None,
        payout_methods: Annotated[Optional[List[Literal["ETH (Ethereum)", "ETH (Base)", "SOL (Solana)", "USDC (Ethereum)", "USDC (Base)", "USDC (Solana)", "USDT (Ethereum)"]]], Field(description="Updated crypto payment methods (replaces existing)")] = None,
        tags: Annotated[Optional[List[str]], Field(description="Updated search tags (replaces existing list)")] = None,
        specifications: Annotated[Optional[Dict[str, str]], Field(description="Updated technical specs (replaces existing dict)")] = None
    ) -> Dict[str, any]:
        """Update product draft information with new data
        
        Note: If updating category to Digital Goods, shipping fields will be automatically cleared.
        
        Returns:
            Update status, draft_id, new version number, and updated timestamp
        """
        draft = storage.get_draft(draft_id)
        if not draft:
            return {"error": f"Product draft {draft_id} not found"}
        
        # 验证用户权限（如果提供了user_id）
        if user_id and draft.user_id and draft.user_id != user_id:
            return {"error": "Access denied: Draft belongs to different user"}
        
        # 如果更新为Digital Goods，清除运输信息
        if category == "Digital Goods":
            ship_from = ""
            ship_to = []
            shipping_fees = {}
        
        updates = {}
        if title is not None:
            updates["title"] = title
        if description is not None:
            updates["description"] = description
        if price is not None:
            updates["price"] = price
        if category is not None:
            updates["category"] = category
        if condition is not None:
            updates["condition"] = condition
        if variations is not None:
            updates["variations"] = variations
        if images is not None:
            updates["images"] = images
        if contact_email is not None:
            updates["contact_email"] = contact_email
        if ship_from is not None:
            updates["ship_from"] = ship_from
        if ship_to is not None:
            updates["ship_to"] = ship_to
        if shipping_fees is not None:
            updates["shipping_fees"] = shipping_fees
        if quantity is not None:
            updates["quantity"] = quantity
        if discount_type is not None:
            updates["discount_type"] = discount_type
        if discount_value is not None:
            updates["discount_value"] = discount_value
        if payout_methods is not None:
            updates["payout_methods"] = payout_methods
        if tags is not None:
            updates["tags"] = tags
        if specifications is not None:
            updates["specifications"] = specifications
        
        success = storage.update_draft(draft_id, **updates)
        
        if success:
            updated_draft = storage.get_draft(draft_id)
            return {
                "status": "updated",
                "draft_id": draft_id,
                "version": updated_draft.version,
                "updated_at": updated_draft.updated_at
            }
        else:
            return {"error": "Update failed"}

    @mcp.tool(
        name="list_drafts",
        description="Unified draft discovery tool: list, search, filter, and analyze with pagination and statistics"
    )
    def list_drafts(
        user_id: Annotated[Optional[str], Field(description="User ID for filtering (empty = all users)")] = None,
        query: Annotated[Optional[str], Field(description="Text search in title, description, tags, specs")] = None,
        category: Annotated[Optional[Literal["Digital Goods", "DEPIN", "Electronics", "collectibles", "Fashion", "Custom", "other"]], Field(description="Filter by Forest Market category")] = None,
        condition: Annotated[Optional[Literal["New", "Used"]], Field(description="Filter by product condition")] = None,
        min_price: Annotated[Optional[float], Field(description="Minimum price threshold (USDT)", ge=0)] = None,
        max_price: Annotated[Optional[float], Field(description="Maximum price threshold (USDT)", ge=0)] = None,
        limit: Annotated[Optional[int], Field(description="Max results to return (pagination)", ge=1, le=100)] = None,
        offset: Annotated[Optional[int], Field(description="Results to skip (pagination start)", ge=0)] = None,
        with_stats: Annotated[bool, Field(description="Include user statistics (requires user_id)")] = False
    ) -> Dict[str, any]:
        """All-in-one draft discovery tool with search, filtering, and analytics
        
        Combines list/search/user-stats functionality with intelligent ranking.
        Supports text search with relevance scoring and comprehensive filtering.
        
        Args:
            user_id: Filter results to specific user
            query: Search text for title, description, tags, specifications  
            category: Filter by product category
            condition: Filter by product condition
            min_price: Minimum price threshold
            max_price: Maximum price threshold
            limit: Maximum results to return
            offset: Results to skip (pagination)
            with_stats: Include user statistics (requires user_id)
            
        Returns:
            Dictionary with filtered/searched drafts and optional statistics
        """
        drafts = storage.list_drafts()
        
        # 按用户ID过滤（如果提供）
        if user_id:
            drafts = [draft for draft in drafts if draft.user_id == user_id]
        
        # 按分类过滤
        if category:
            drafts = [draft for draft in drafts if draft.category == category]
        
        # 按状态过滤
        if condition:
            drafts = [draft for draft in drafts if draft.condition == condition]
        
        # 按价格过滤
        if min_price is not None:
            drafts = [draft for draft in drafts if draft.price >= min_price]
        if max_price is not None:
            drafts = [draft for draft in drafts if draft.price <= max_price]
        
        # 文本搜索（如果提供query）
        if query:
            search_results = []
            query_lower = query.lower()
            
            for draft in drafts:
                matches = []
                score = 0
                
                # 搜索标题
                if query_lower in draft.title.lower():
                    matches.append("title")
                    score += 3  # 标题匹配权重高
                
                # 搜索描述
                if query_lower in draft.description.lower():
                    matches.append("description")
                    score += 2
                
                # 搜索标签
                for tag in draft.tags:
                    if query_lower in tag.lower():
                        matches.append("tags")
                        score += 2
                        break
                
                # 搜索规格
                for spec_key, spec_value in draft.specifications.items():
                    if query_lower in spec_key.lower() or query_lower in str(spec_value).lower():
                        matches.append("specifications")
                        score += 1
                        break
                
                # 如果有匹配，添加到结果
                if matches:
                    search_results.append((draft, score, matches))
            
            # 按匹配分数排序
            search_results.sort(key=lambda x: x[1], reverse=True)
            drafts = [result[0] for result in search_results]
        
        # 分页处理
        total_count = len(drafts)
        if offset:
            drafts = drafts[offset:]
        if limit:
            drafts = drafts[:limit]
        
        # 构建返回数据
        draft_list = []
        for draft in drafts:
            draft_info = {
                "draft_id": draft.draft_id,
                "user_id": draft.user_id,
                "title": draft.title,
                "category": draft.category,
                "condition": draft.condition,
                "price": draft.price,
                "quantity": draft.quantity,
                "ship_from": draft.ship_from,
                "has_variations": len(draft.variations) > 0,
                "has_discount": bool(draft.discount_type),
                "created_at": draft.created_at,
                "updated_at": draft.updated_at,
                "version": draft.version
            }
            
            # 如果是搜索结果，添加匹配信息
            if query:
                for result in search_results:
                    if result[0].draft_id == draft.draft_id:
                        draft_info["search_score"] = result[1]
                        draft_info["search_matches"] = result[2]
                        break
            
            draft_list.append(draft_info)
        
        result = {
            "total_count": total_count,
            "returned_count": len(draft_list),
            "drafts": draft_list
        }
        
        # 添加统计信息（如果请求且有user_id）
        if with_stats and user_id:
            user_drafts = [draft for draft in storage.list_drafts() if draft.user_id == user_id]
            if user_drafts:
                categories = {}
                total_value = 0
                conditions = {}
                
                for draft in user_drafts:
                    categories[draft.category] = categories.get(draft.category, 0) + 1
                    total_value += draft.price * draft.quantity
                    conditions[draft.condition] = conditions.get(draft.condition, 0) + 1
                
                result["statistics"] = {
                    "total_inventory_value": total_value,
                    "categories": categories,
                    "conditions": conditions,
                    "avg_price": total_value / sum(draft.quantity for draft in user_drafts) if user_drafts else 0
                }
        
        return result

    @mcp.tool(
        name="delete_draft",
        description="Permanently delete a Forest Market draft with ownership verification"
    )
    def delete_draft(
        draft_id: Annotated[str, Field(description="Draft ID to delete permanently (required)")],
        user_id: Annotated[Optional[str], Field(description="User ID for ownership verification (recommended)")] = None
    ) -> Dict[str, any]:
        """Delete a specific product draft permanently
        
        Returns:
            Deletion status and draft_id, or error message if draft not found
        """
        # 验证用户权限（如果提供了user_id）
        if user_id:
            draft = storage.get_draft(draft_id)
            if not draft:
                return {"error": f"Product draft {draft_id} not found"}
            if draft.user_id and draft.user_id != user_id:
                return {"error": "Access denied: Draft belongs to different user"}
        
        success = storage.delete_draft(draft_id)
        
        if success:
            return {
                "status": "deleted",
                "draft_id": draft_id
            }
        else:
            return {
                "error": f"Product draft {draft_id} not found or deletion failed"
            }


    @mcp.tool(
        name="export_draft",
        description="Export draft in Forest Market format for listing integration and final review"
    )
    def export_draft(
        draft_id: Annotated[str, Field(description="Draft ID to export for listing (required)")],
        user_id: Annotated[Optional[str], Field(description="User ID for ownership verification")] = None,
        export_format: Annotated[Literal["forest_market", "json"], Field(description="Export format: forest_market (optimized) or json (raw)")] = "forest_market"
    ) -> Dict[str, any]:
        """Export draft data for integration with listing MCP services
        
        Args:
            export_format: Either 'forest_market' (optimized format) or 'json' (raw format)
            
        Returns:
            Formatted product data ready for listing MCP integration
        """
        draft = storage.get_draft(draft_id)
        if not draft:
            return {"error": f"Product draft {draft_id} not found"}
        
        # 验证用户权限（如果提供了user_id）
        if user_id and draft.user_id and draft.user_id != user_id:
            return {"error": "Access denied: Draft belongs to different user"}
        
        if export_format == "forest_market":

            return {
                "product_data": {
                    "title": draft.title,
                    "description": draft.description,
                    "price": draft.price,
                    "category": draft.category,
                    "condition": draft.condition,
                    "variations": draft.variations,
                    "images": draft.images,
                    "contact_email": draft.contact_email,
                    "ship_from": draft.ship_from,
                    "ship_to": draft.ship_to,
                    "shipping_fees": draft.shipping_fees,
                    "quantity": draft.quantity,
                    "discount_type": draft.discount_type,
                    "discount_value": draft.discount_value,
                    "payout_methods": draft.payout_methods,
                    "tags": draft.tags,
                    "specifications": draft.specifications
                },
                "metadata": {
                    "draft_id": draft.draft_id,
                    "version": draft.version,
                    "created_at": draft.created_at,
                    "updated_at": draft.updated_at
                },
                "export_format": "forest_market",
                "ready_for_listing": True
            }
        elif export_format == "json":
            return {
                "export_data": draft.to_dict(),
                "export_format": "json"
            }
        else:
            return {"error": f"Unsupported export format: {export_format}"}





    @mcp.tool(
        name="add_to_draft",
        description="Incrementally add new options to draft arrays and objects without replacing existing data"
    )
    def add_to_draft(
        draft_id: Annotated[str, Field(description="Draft ID to update incrementally (required)")],
        user_id: Annotated[Optional[str], Field(description="User ID for ownership verification")] = None,
        variations: Annotated[Optional[Dict[str, List[str]]], Field(description="Add variation options: {'Size': ['XXL']} (merges with existing)")] = None,
        images: Annotated[Optional[List[str]], Field(description="Add image URLs to existing list (no duplicates)")] = None,
        tags: Annotated[Optional[List[str]], Field(description="Add search tags to existing list (no duplicates)")] = None,
        specifications: Annotated[Optional[Dict[str, str]], Field(description="Add specs to existing dict: {'RAM': '32GB'} (merges keys)")] = None,
        ship_to: Annotated[Optional[List[Literal["United States", "Singapore", "Hong Kong", "South Korea", "Japan"]]], Field(description="Add shipping destinations to existing list")] = None,
        shipping_fees: Annotated[Optional[Dict[str, float]], Field(description="Add/update shipping fees: {'Canada': 20.0} (merges with existing)")] = None,
        payout_methods: Annotated[Optional[List[Literal["ETH (Ethereum)", "ETH (Base)", "SOL (Solana)", "USDC (Ethereum)", "USDC (Base)", "USDC (Solana)", "USDT (Ethereum)"]]], Field(description="Add payment methods to existing list (no duplicates)")] = None
    ) -> Dict[str, any]:
        """Add new options/items to existing draft fields
        
        This tool adds to existing data without replacing it.
        For variations, adds new options to existing variation types.
        
        Returns:
            Update status, draft_id, new version number, and updated timestamp
        """
        draft = storage.get_draft(draft_id)
        if not draft:
            return {"error": f"Product draft {draft_id} not found"}
        
        # 验证用户权限（如果提供了user_id）
        if user_id and draft.user_id and draft.user_id != user_id:
            return {"error": "Access denied: Draft belongs to different user"}
        
        updates = {}
        
        # 处理variations - 添加新选项到现有变体类型
        if variations:
            current_variations = draft.variations.copy()
            for var_name, new_options in variations.items():
                if var_name in current_variations:
                    # 合并选项，去重
                    existing_options = current_variations[var_name]
                    combined_options = list(set(existing_options + new_options))
                    current_variations[var_name] = combined_options
                else:
                    # 新的变体类型
                    current_variations[var_name] = new_options
            updates["variations"] = current_variations
        
        # 处理images - 添加到现有列表
        if images:
            current_images = draft.images.copy()
            for img in images:
                if img not in current_images:
                    current_images.append(img)
            updates["images"] = current_images
        
        # 处理tags - 添加到现有列表，去重
        if tags:
            current_tags = draft.tags.copy()
            for tag in tags:
                if tag not in current_tags:
                    current_tags.append(tag)
            updates["tags"] = current_tags
        
        # 处理specifications - 添加/更新规格
        if specifications:
            current_specs = draft.specifications.copy()
            current_specs.update(specifications)
            updates["specifications"] = current_specs
        
        # 处理ship_to - 添加新目的地
        if ship_to:
            current_ship_to = draft.ship_to.copy()
            for destination in ship_to:
                if destination not in current_ship_to:
                    current_ship_to.append(destination)
            updates["ship_to"] = current_ship_to
        
        # 处理shipping_fees - 添加新费用
        if shipping_fees:
            current_fees = draft.shipping_fees.copy()
            current_fees.update(shipping_fees)
            updates["shipping_fees"] = current_fees
        
        # 处理payout_methods - 添加新支付方式
        if payout_methods:
            current_methods = draft.payout_methods.copy()
            for method in payout_methods:
                if method not in current_methods:
                    current_methods.append(method)
            updates["payout_methods"] = current_methods
        
        if not updates:
            return {"error": "No valid fields provided to add"}
        
        success = storage.update_draft(draft_id, **updates)
        
        if success:
            updated_draft = storage.get_draft(draft_id)
            return {
                "status": "added",
                "draft_id": draft_id,
                "version": updated_draft.version,
                "updated_at": updated_draft.updated_at,
                "added_fields": list(updates.keys())
            }
        else:
            return {"error": "Add operation failed"}

    @mcp.tool(
        name="remove_from_draft",
        description="Selectively remove specific options, items, or entire sections from draft fields"
    )
    def remove_from_draft(
        draft_id: Annotated[str, Field(description="Draft ID to update selectively (required)")],
        user_id: Annotated[Optional[str], Field(description="User ID for ownership verification")] = None,
        variation_options: Annotated[Optional[Dict[str, List[str]]], Field(description="Remove specific variation options: {'Size': ['S','M']} (keeps other sizes)")] = None,
        variation_types: Annotated[Optional[List[str]], Field(description="Remove entire variation categories: ['Color'] (removes all colors)")] = None,
        images: Annotated[Optional[List[str]], Field(description="Remove specific image URLs from existing list")] = None,
        tags: Annotated[Optional[List[str]], Field(description="Remove specific tags from existing list")] = None,
        specifications: Annotated[Optional[List[str]], Field(description="Remove spec keys: ['Weight'] (removes key-value pairs)")] = None,
        ship_to: Annotated[Optional[List[Literal["United States", "Singapore", "Hong Kong", "South Korea", "Japan"]]], Field(description="Remove shipping destinations from existing list")] = None,
        shipping_fees: Annotated[Optional[List[str]], Field(description="Remove shipping fees for countries: ['Canada'] (removes fee entries)")] = None,
        payout_methods: Annotated[Optional[List[Literal["ETH (Ethereum)", "ETH (Base)", "SOL (Solana)", "USDC (Ethereum)", "USDC (Base)", "USDC (Solana)", "USDT (Ethereum)"]]], Field(description="Remove payment methods from existing list")] = None
    ) -> Dict[str, any]:
        """Remove specific options/items from existing draft fields
        
        This tool removes specific items from existing data.
        For variations, can remove specific options or entire variation types.
        
        Returns:
            Update status, draft_id, new version number, and updated timestamp
        """
        draft = storage.get_draft(draft_id)
        if not draft:
            return {"error": f"Product draft {draft_id} not found"}
        
        # 验证用户权限（如果提供了user_id）
        if user_id and draft.user_id and draft.user_id != user_id:
            return {"error": "Access denied: Draft belongs to different user"}
        
        updates = {}
        
        # 处理variation_options - 删除特定选项
        if variation_options:
            current_variations = draft.variations.copy()
            for var_name, options_to_remove in variation_options.items():
                if var_name in current_variations:
                    remaining_options = [opt for opt in current_variations[var_name] if opt not in options_to_remove]
                    if remaining_options:
                        current_variations[var_name] = remaining_options
                    else:
                        # 如果没有剩余选项，删除整个变体类型
                        del current_variations[var_name]
            updates["variations"] = current_variations
        
        # 处理variation_types - 删除整个变体类型
        if variation_types:
            current_variations = updates.get("variations", draft.variations.copy())
            for var_type in variation_types:
                if var_type in current_variations:
                    del current_variations[var_type]
            updates["variations"] = current_variations
        
        # 处理images - 删除特定图片
        if images:
            current_images = [img for img in draft.images if img not in images]
            updates["images"] = current_images
        
        # 处理tags - 删除特定标签
        if tags:
            current_tags = [tag for tag in draft.tags if tag not in tags]
            updates["tags"] = current_tags
        
        # 处理specifications - 删除特定规格
        if specifications:
            current_specs = draft.specifications.copy()
            for spec_key in specifications:
                if spec_key in current_specs:
                    del current_specs[spec_key]
            updates["specifications"] = current_specs
        
        # 处理ship_to - 删除目的地
        if ship_to:
            current_ship_to = [dest for dest in draft.ship_to if dest not in ship_to]
            updates["ship_to"] = current_ship_to
        
        # 处理shipping_fees - 删除特定目的地的费用
        if shipping_fees:
            current_fees = draft.shipping_fees.copy()
            for destination in shipping_fees:
                if destination in current_fees:
                    del current_fees[destination]
            updates["shipping_fees"] = current_fees
        
        # 处理payout_methods - 删除支付方式
        if payout_methods:
            current_methods = [method for method in draft.payout_methods if method not in payout_methods]
            updates["payout_methods"] = current_methods
        
        if not updates:
            return {"error": "No valid fields provided to remove"}
        
        success = storage.update_draft(draft_id, **updates)
        
        if success:
            updated_draft = storage.get_draft(draft_id)
            return {
                "status": "removed",
                "draft_id": draft_id,
                "version": updated_draft.version,
                "updated_at": updated_draft.updated_at,
                "modified_fields": list(updates.keys())
            }
        else:
            return {"error": "Remove operation failed"}