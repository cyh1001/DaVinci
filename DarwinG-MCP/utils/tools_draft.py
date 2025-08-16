"""
MCP工具函数定义
"""

from typing import List, Dict, Optional, Annotated, Literal, Any
from fastmcp import FastMCP
from pydantic import Field, BaseModel

class VariationData(BaseModel):
    name: str
    values: List[str]

class ShippingPriceData(BaseModel):
    country_code: str
    price: float
    currency_code: str = "USDT"

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
        category: Annotated[Literal["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "COLLECTIBLES", "FASHION", "CUSTOM", "OTHER"], Field(description="Forest Market product category")] = "OTHER",
        condition: Annotated[Literal["NEW", "USED"], Field(description="Product condition/state")] = "NEW",
        variations_data: Annotated[Optional[List[VariationData]], Field(description="Product variations: [{'name': 'Size', 'values': ['S','M','L']}, {'name': 'Color', 'values': ['Red','Blue']}]")] = None,
        image_file_paths: Annotated[Optional[List[str]], Field(description="Product image file paths (recommended for listings)")] = None,
        contact_email: Annotated[str, Field(description="Seller contact email address")] = "",
        ship_from_country: Annotated[Optional[Literal["US", "SG", "HK", "KR", "JP"]], Field(description="Shipping origin (auto-cleared for DIGITAL_GOODS)")] = None,
        ship_to_countries: Annotated[Optional[List[Literal["US", "SG", "HK", "KR", "JP"]]], Field(description="Shipping destinations (auto-cleared for DIGITAL_GOODS)")] = None,
        shipping_prices_data: Annotated[Optional[List[ShippingPriceData]], Field(description="Shipping costs: [{'country_code': 'US', 'price': 15.0, 'currency_code': 'USDT'}] (auto-cleared for DIGITAL_GOODS)")] = None,
        quantity: Annotated[int, Field(description="Available stock quantity (minimum 1)", ge=1)] = 1,
        discount_type: Annotated[Optional[Literal["", "FIXED_AMOUNT", "PERCENTAGE"]], Field(description="Discount type (leave empty for no discount)")] = None,
        discount_value: Annotated[float, Field(description="Discount amount (USDT for FIXED_AMOUNT, 0.1-0.5 for PERCENTAGE)", ge=0)] = 0.0,
        payment_options: Annotated[Optional[List[Literal["ETH_ETHEREUM", "ETH_BASE", "SOL_SOLANA", "USDC_ETHEREUM", "USDC_BASE", "USDC_SOLANA", "USDT_ETHEREUM"]]], Field(description="Accepted crypto payment methods")] = None,
        tags: Annotated[Optional[List[str]], Field(description="Search tags for better discoverability")] = None,
        specifications: Annotated[Optional[Dict[str, str]], Field(description="Technical specs: {'Brand': 'Apple', 'Model': 'iPhone 15'}")] = None
    ) -> Dict[str, Any]:
        """Create a new Forest Market product draft with comprehensive field validation
        
        Automatically handles Digital Goods by clearing shipping fields.
        Creates unique draft_id and initializes version control.
        
        Returns:
            Dictionary containing draft_id, title, created_at timestamp, and status
        """
        # Auto-clear shipping fields for DIGITAL_GOODS
        if category == "DIGITAL_GOODS":
            ship_from_country = ""
            ship_to_countries = []
            shipping_prices_data = []
        
        # Convert variations_data to Variation objects if provided
        variations_objects = None
        if variations_data:
            from models import Variation
            variations_objects = [Variation(name=v.name, values=v.values) for v in variations_data]
        
        # Convert shipping_prices_data to ShippingPrice objects if provided
        shipping_objects = None
        if shipping_prices_data:
            from models import ShippingPrice
            shipping_objects = [
                ShippingPrice(
                    country_code=sp.country_code,
                    price=sp.price,
                    currency_code=sp.currency_code
                )
                for sp in shipping_prices_data
            ]
        
        draft = ProductDraft(
            title=title,
            user_id=user_id,
            description=description,
            price=price,
            category=category,
            condition=condition,
            variations_data=variations_objects,
            image_file_paths=image_file_paths or [],
            contact_email=contact_email,
            ship_from_country=ship_from_country,
            ship_to_countries=ship_to_countries or [],
            shipping_prices_data=shipping_objects,
            quantity=quantity,
            discount_type=discount_type,
            discount_value=discount_value,
            payment_options=payment_options or [],
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
    ) -> Dict[str, Any]:
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
                        "ship_from_country": draft.ship_from_country,
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
                "ship_from_country": draft.ship_from_country,
                "ship_to_count": len(draft.ship_to_countries),
                "has_shipping_fees": bool(draft.shipping_prices_data),
                "variations_count": len(draft.variations_data),
                "tags_count": len(draft.tags),
                "images_count": len(draft.image_file_paths),
                "payment_options_count": len(draft.payment_options),
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
        category: Annotated[Optional[Literal["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "COLLECTIBLES", "FASHION", "CUSTOM", "OTHER"]], Field(description="Updated Forest Market category")] = None,
        condition: Annotated[Optional[Literal["NEW", "USED"]], Field(description="Updated product condition")] = None,
        variations_data: Annotated[Optional[List[VariationData]], Field(description="Updated variations (replaces existing): [{'name': 'Size', 'values': ['S','M','L']}]")] = None,
        image_file_paths: Annotated[Optional[List[str]], Field(description="Updated image file paths (replaces existing list)")] = None,
        contact_email: Annotated[Optional[str], Field(description="Updated seller contact email")] = None,
        ship_from_country: Annotated[Optional[Literal["US", "SG", "HK", "KR", "JP"]], Field(description="Updated shipping origin (auto-cleared for DIGITAL_GOODS)")] = None,
        ship_to_countries: Annotated[Optional[List[Literal["US", "SG", "HK", "KR", "JP"]]], Field(description="Updated shipping destinations (auto-cleared for DIGITAL_GOODS)")] = None,
        shipping_prices_data: Annotated[Optional[List[ShippingPriceData]], Field(description="Updated shipping fees (auto-cleared for DIGITAL_GOODS): [{'country_code': 'US', 'price': 15.0, 'currency_code': 'USDT'}]")] = None,
        quantity: Annotated[Optional[int], Field(description="Updated stock quantity (>= 1)", ge=1)] = None,
        discount_type: Annotated[Optional[Literal["", "FIXED_AMOUNT", "PERCENTAGE"]], Field(description="Updated discount type (empty string removes discount)")] = None,
        discount_value: Annotated[Optional[float], Field(description="Updated discount value (USDT for FIXED_AMOUNT, 0.1-0.5 for PERCENTAGE)", ge=0)] = None,
        payment_options: Annotated[Optional[List[Literal["ETH_ETHEREUM", "ETH_BASE", "SOL_SOLANA", "USDC_ETHEREUM", "USDC_BASE", "USDC_SOLANA", "USDT_ETHEREUM"]]], Field(description="Updated crypto payment methods (replaces existing)")] = None,
        tags: Annotated[Optional[List[str]], Field(description="Updated search tags (replaces existing list)")] = None,
        specifications: Annotated[Optional[Dict[str, str]], Field(description="Updated technical specs (replaces existing dict)")] = None
    ) -> Dict[str, Any]:
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
        
        # 如果更新为DIGITAL_GOODS，清除运输信息
        if category == "DIGITAL_GOODS":
            ship_from_country = ""
            ship_to_countries = []
            shipping_prices_data = []
        
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
        if variations_data is not None:
            # Convert to Variation objects
            from models import Variation
            variations_objects = [Variation(name=v.name, values=v.values) for v in variations_data]
            updates["variations_data"] = variations_objects
        if image_file_paths is not None:
            updates["image_file_paths"] = image_file_paths
        if contact_email is not None:
            updates["contact_email"] = contact_email
        if ship_from_country is not None:
            updates["ship_from_country"] = ship_from_country
        if ship_to_countries is not None:
            updates["ship_to_countries"] = ship_to_countries
        if shipping_prices_data is not None:
            # Convert to ShippingPrice objects
            from models import ShippingPrice
            shipping_objects = [
                ShippingPrice(
                    country_code=sp.country_code,
                    price=sp.price,
                    currency_code=sp.currency_code
                )
                for sp in shipping_prices_data
            ]
            updates["shipping_prices_data"] = shipping_objects
        if quantity is not None:
            updates["quantity"] = quantity
        if discount_type is not None:
            updates["discount_type"] = discount_type
        if discount_value is not None:
            updates["discount_value"] = discount_value
        if payment_options is not None:
            updates["payment_options"] = payment_options
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
        category: Annotated[Optional[Literal["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "COLLECTIBLES", "FASHION", "CUSTOM", "OTHER"]], Field(description="Filter by Forest Market category")] = None,
        condition: Annotated[Optional[Literal["NEW", "USED"]], Field(description="Filter by product condition")] = None,
        min_price: Annotated[Optional[float], Field(description="Minimum price threshold (USDT)", ge=0)] = None,
        max_price: Annotated[Optional[float], Field(description="Maximum price threshold (USDT)", ge=0)] = None,
        limit: Annotated[Optional[int], Field(description="Max results to return (pagination)", ge=1, le=100)] = None,
        offset: Annotated[Optional[int], Field(description="Results to skip (pagination start)", ge=0)] = None,
        with_stats: Annotated[bool, Field(description="Include user statistics (requires user_id)")] = False
    ) -> Dict[str, Any]:
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
                "ship_from_country": draft.ship_from_country,
                "has_variations": len(draft.variations_data) > 0,
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
    ) -> Dict[str, Any]:
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
        export_format: Annotated[Literal["forest_market", "json"], Field(description="Export format: forest_market (optimized) or json (raw)")] = "forest_market",
        include_mapping_info: Annotated[bool, Field(description="Include field mapping information for upload tool compatibility")] = False
    ) -> Dict[str, Any]:
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
            result = {
                "product_data": {
                    "title": draft.title,
                    "description": draft.description,
                    "price": draft.price,
                    "category": draft.category,
                    "condition": draft.condition,
                    "variations_data": draft.get_variations_data_dict(),  # Convert to dict format for upload tool
                    "image_file_paths": draft.image_file_paths,
                    "contact_email": draft.contact_email,
                    "ship_from_country": draft.ship_from_country,
                    "ship_to_countries": draft.ship_to_countries,
                    "shipping_prices_data": draft.get_shipping_prices_data_dict(),  # Convert to dict format for upload tool
                    "quantity": draft.quantity,
                    "discount_type": draft.discount_type,
                    "discount_value": draft.discount_value,
                    "payment_options": draft.payment_options,
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
                "ready_for_listing": True,
                "note": "Images exported as URLs. Convert to local file paths before using with upload_listing tool."
            }
            
            if include_mapping_info:
                result["upload_tool_mapping"] = {
                    "field_mappings": {
                        "title": "title",
                        "description": "description", 
                        "category": "category",
                        "image_file_paths": "image_file_paths",
                        "price": "price",
                        "quantity": "quantity",
                        "payment_options": "payment_options",
                        "ship_from_country": "ship_from_country",
                        "ship_to_countries": "ship_to_countries",
                        "variations_data": "variations_data (ready to use)",
                        "shipping_prices_data": "shipping_prices_data (ready to use)",
                        "condition": "condition",
                        "discount_type": "discount_type",
                        "discount_value": "discount_value"
                    },
                    "required_transformations": [
                        "Convert image URLs to local file paths for image_file_paths parameter",
                        "Ensure discount_value follows validation: PERCENTAGE (0.1-0.5), FIXED_AMOUNT (positive value)"
                    ]
                }
            
            return result
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
        variations_data: Annotated[Optional[List[VariationData]], Field(description="Add variation options: [{'name': 'Size', 'values': ['XXL']}] (merges with existing)")] = None,
        image_file_paths: Annotated[Optional[List[str]], Field(description="Add image file paths to existing list (no duplicates)")] = None,
        tags: Annotated[Optional[List[str]], Field(description="Add search tags to existing list (no duplicates)")] = None,
        specifications: Annotated[Optional[Dict[str, str]], Field(description="Add specs to existing dict: {'RAM': '32GB'} (merges keys)")] = None,
        ship_to_countries: Annotated[Optional[List[Literal["US", "SG", "HK", "KR", "JP"]]], Field(description="Add shipping destinations to existing list")] = None,
        shipping_prices_data: Annotated[Optional[List[ShippingPriceData]], Field(description="Add/update shipping fees: [{'country_code': 'Canada', 'price': 20.0, 'currency_code': 'USDT'}] (merges with existing)")] = None,
        payment_options: Annotated[Optional[List[Literal["ETH_ETHEREUM", "ETH_BASE", "SOL_SOLANA", "USDC_ETHEREUM", "USDC_BASE", "USDC_SOLANA", "USDT_ETHEREUM"]]], Field(description="Add payment methods to existing list (no duplicates)")] = None
    ) -> Dict[str, Any]:
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
        
        # 处理variations_data - 添加新选项到现有变体类型
        if variations_data:
            current_variations = [vars(v) for v in draft.variations_data]  # Convert to dict format
            for new_var in variations_data:
                var_name = new_var.name
                new_values = new_var.values
                
                # 查找现有的变体类型
                existing_var = next((v for v in current_variations if v["name"] == var_name), None)
                if existing_var:
                    # 合并选项，去重
                    combined_values = list(set(existing_var["values"] + new_values))
                    existing_var["values"] = combined_values
                else:
                    # 新的变体类型
                    current_variations.append({"name": var_name, "values": new_values})
            # Convert back to Variation objects
            from models import Variation
            variations_objects = [Variation(name=v['name'], values=v['values']) for v in current_variations]
            updates["variations_data"] = variations_objects
        
        # 处理image_file_paths - 添加到现有列表
        if image_file_paths:
            current_images = draft.image_file_paths.copy()
            for img in image_file_paths:
                if img not in current_images:
                    current_images.append(img)
            updates["image_file_paths"] = current_images
        
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
        
        # 处理ship_to_countries - 添加新目的地
        if ship_to_countries:
            current_ship_to = draft.ship_to_countries.copy()
            for destination in ship_to_countries:
                if destination not in current_ship_to:
                    current_ship_to.append(destination)
            updates["ship_to_countries"] = current_ship_to
        
        # 处理shipping_prices_data - 添加新费用
        if shipping_prices_data:
            current_fees = [vars(f) for f in draft.shipping_prices_data]  # Convert to dict format
            for new_fee in shipping_prices_data:
                country_code = new_fee.country_code
                # 查找现有的费用条目
                existing_fee = next((f for f in current_fees if f["country_code"] == country_code), None)
                if existing_fee:
                    # 更新现有费用
                    existing_fee.update(vars(new_fee))
                else:
                    # 添加新费用
                    current_fees.append(vars(new_fee))
            # Convert back to ShippingPrice objects
            from models import ShippingPrice
            shipping_objects = [
                ShippingPrice(
                    country_code=f['country_code'],
                    price=f['price'],
                    currency_code=f.get('currency_code', 'USDT')
                )
                for f in current_fees
            ]
            updates["shipping_prices_data"] = shipping_objects
        
        # 处理payment_options - 添加新支付方式
        if payment_options:
            current_methods = draft.payment_options.copy()
            for method in payment_options:
                if method not in current_methods:
                    current_methods.append(method)
            updates["payment_options"] = current_methods
        
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
        variation_options: Annotated[Optional[List[Dict[str, List[str]]]], Field(description="Remove specific variation options: [{'name': 'Size', 'values': ['S','M']}] (keeps other sizes)")] = None,
        variation_types: Annotated[Optional[List[str]], Field(description="Remove entire variation categories: ['Color'] (removes all colors)")] = None,
        image_file_paths: Annotated[Optional[List[str]], Field(description="Remove specific image file paths from existing list")] = None,
        tags: Annotated[Optional[List[str]], Field(description="Remove specific tags from existing list")] = None,
        specifications: Annotated[Optional[List[str]], Field(description="Remove spec keys: ['Weight'] (removes key-value pairs)")] = None,
        ship_to_countries: Annotated[Optional[List[Literal["US", "SG", "HK", "KR", "JP"]]], Field(description="Remove shipping destinations from existing list")] = None,
        shipping_prices_data: Annotated[Optional[List[str]], Field(description="Remove shipping fees for countries: ['Canada'] (removes fee entries)")] = None,
        payment_options: Annotated[Optional[List[Literal["ETH_ETHEREUM", "ETH_BASE", "SOL_SOLANA", "USDC_ETHEREUM", "USDC_BASE", "USDC_SOLANA", "USDT_ETHEREUM"]]], Field(description="Remove payment methods from existing list")] = None
    ) -> Dict[str, Any]:
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
            current_variations = [vars(v) for v in draft.variations_data]  # Convert to dict format
            for var_to_remove in variation_options:
                var_name = var_to_remove["name"]
                options_to_remove = var_to_remove["values"]
                
                # 查找现有的变体类型
                existing_var = next((v for v in current_variations if v["name"] == var_name), None)
                if existing_var:
                    remaining_options = [opt for opt in existing_var["values"] if opt not in options_to_remove]
                    if remaining_options:
                        existing_var["values"] = remaining_options
                    else:
                        # 如果没有剩余选项，删除整个变体类型
                        current_variations.remove(existing_var)
            # Convert back to Variation objects
            from models import Variation
            variations_objects = [Variation(name=v['name'], values=v['values']) for v in current_variations]
            updates["variations_data"] = variations_objects
        
        # 处理variation_types - 删除整个变体类型
        if variation_types:
            current_variations = updates.get("variations_data", [vars(v) for v in draft.variations_data])
            if "variations_data" in updates:
                # If already updated, work with the updated objects
                current_variations = [vars(v) for v in updates["variations_data"]]
            current_variations = [v for v in current_variations if v["name"] not in variation_types]
            # Convert back to Variation objects
            from models import Variation
            variations_objects = [Variation(name=v['name'], values=v['values']) for v in current_variations]
            updates["variations_data"] = variations_objects
        
        # 处理image_file_paths - 删除特定图片
        if image_file_paths:
            current_images = [img for img in draft.image_file_paths if img not in image_file_paths]
            updates["image_file_paths"] = current_images
        
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
        
        # 处理ship_to_countries - 删除目的地
        if ship_to_countries:
            current_ship_to = [dest for dest in draft.ship_to_countries if dest not in ship_to_countries]
            updates["ship_to_countries"] = current_ship_to
        
        # 处理shipping_prices_data - 删除特定目的地的费用
        if shipping_prices_data:
            current_fees_dict = [vars(f) for f in draft.shipping_prices_data]
            current_fees = [f for f in current_fees_dict if f["country_code"] not in shipping_prices_data]
            # Convert back to ShippingPrice objects
            from models import ShippingPrice
            shipping_objects = [
                ShippingPrice(
                    country_code=f['country_code'],
                    price=f['price'],
                    currency_code=f.get('currency_code', 'USDT')
                )
                for f in current_fees
            ]
            updates["shipping_prices_data"] = shipping_objects
        
        # 处理payment_options - 删除支付方式
        if payment_options:
            current_methods = [method for method in draft.payment_options if method not in payment_options]
            updates["payment_options"] = current_methods
        
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


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "mcp":
        # Run as MCP server
        mcp = FastMCP("Forest Market Draft Tools")
        register_tools(mcp)
        mcp.run()
    else:
        print("Usage: python tools.py mcp")
        print("Run as MCP server with 'mcp' argument")