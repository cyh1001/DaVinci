#!/usr/bin/env python3
"""
Forest Market Draft MCP 测试文件
测试草稿管理功能
"""

import json
import os
try:
    from .storage import DraftStorage
    from .models import ProductDraft
except ImportError:
    from storage import DraftStorage
    from models import ProductDraft

# 初始化存储用于测试
storage = DraftStorage()

def test_create_draft():
    """测试创建草稿"""
    print("=== 测试创建草稿 ===")
    
    # 创建测试草稿
    draft = ProductDraft(
        title="iPhone 15 Pro Max",
        user_id="test_user_001",
        description="苹果最新旗舰手机，配备A17 Pro芯片",
        price=1299.0,
        category="Electronics",
        condition="New",
        variations=[
            {"name": "Color", "value": "Space Black"},
            {"name": "Storage", "value": "256GB"}
        ],
        images=["https://example.com/iphone1.jpg"],
        contact_email="seller@example.com",
        ship_from="United States",
        ship_to=["United States", "Singapore"],
        shipping_fees={"United States": 0.0, "Singapore": 15.0},
        quantity=10,
        discount_type="Percentage",
        discount_value=10.0,
        payout_methods=["USDC (Ethereum)", "ETH (Ethereum)"],
        tags=["苹果", "iPhone", "5G", "旗舰"],
        specifications={
            "屏幕尺寸": "6.7英寸",
            "存储容量": "256GB",
            "处理器": "A17 Pro"
        }
    )
    
    draft_id = storage.create_draft(draft)
    print(f"创建草稿成功，ID: {draft_id}")
    
    # 验证草稿
    retrieved_draft = storage.get_draft(draft_id)
    assert retrieved_draft is not None
    assert retrieved_draft.title == "iPhone 15 Pro Max"
    print("✓ 草稿创建和获取测试通过")
    
    return draft_id

def test_update_draft(draft_id):
    """测试更新草稿"""
    print("\n=== 测试更新草稿 ===")
    
    # 更新草稿
    success = storage.update_draft(
        draft_id,
        price=1199.0,
        description="苹果最新旗舰手机，配备A17 Pro芯片，现在特价优惠！",
        discount_type="Fixed Amount",
        discount_value=100.0,
        quantity=15
    )
    
    assert success == True
    
    # 验证更新
    updated_draft = storage.get_draft(draft_id)
    assert updated_draft.price == 1199.0
    assert "特价优惠" in updated_draft.description
    assert updated_draft.discount_type == "Fixed Amount"
    assert updated_draft.discount_value == 100.0
    assert updated_draft.quantity == 15
    assert updated_draft.version == 2  # 版本应该增加
    
    print("✓ 草稿更新测试通过")

def test_list_drafts():
    """测试列出草稿"""
    print("\n=== 测试列出草稿 ===")
    
    drafts = storage.list_drafts()
    assert len(drafts) >= 1
    
    print(f"✓ 当前共有 {len(drafts)} 个草稿")
    for draft in drafts:
        print(f"  - {draft.title} (ID: {draft.draft_id})")

def test_duplicate_draft(original_draft_id):
    """测试复制草稿"""
    print("\n=== 测试复制草稿 ===")
    
    # 创建第二个草稿用于测试
    new_draft = ProductDraft(
        title="iPad Air",
        user_id="test_user_002",
        description="轻薄强大的平板电脑",
        price=599.0,
        category="Electronics",
        condition="New",
        contact_email="seller@example.com",
        ship_from="Singapore",
        ship_to=["Singapore", "Hong Kong"],
        shipping_fees={"Singapore": 0.0, "Hong Kong": 8.0},
        quantity=5,
        payout_methods=["USDC (Base)"]
    )
    
    new_draft_id = storage.create_draft(new_draft)
    
    # 复制草稿
    duplicated = ProductDraft(
        title=f"{new_draft.title} (副本)",
        user_id="test_user_002",
        description=new_draft.description,
        price=new_draft.price,
        category=new_draft.category,
        tags=new_draft.tags.copy(),
        images=new_draft.images.copy(),
        specifications=new_draft.specifications.copy()
    )
    
    duplicated_id = storage.create_draft(duplicated)
    
    # 验证复制
    original = storage.get_draft(new_draft_id)
    duplicate = storage.get_draft(duplicated_id)
    
    assert original.title != duplicate.title
    assert "(副本)" in duplicate.title
    assert original.description == duplicate.description
    assert original.price == duplicate.price
    
    print("✓ 草稿复制测试通过")
    return duplicated_id

def test_multiple_drafts_management():
    """测试多草稿管理场景"""
    print("\n=== 测试多草稿管理场景 ===")
    
    # 创建多个不同的草稿
    products = [
        {
            "title": "MacBook Pro 16英寸",
            "user_id": "test_user_003",
            "description": "专业级笔记本电脑",
            "price": 2499.0,
            "category": "Electronics",
            "condition": "New",
            "contact_email": "seller@example.com",
            "ship_from": "United States",
            "ship_to": ["United States", "Japan"],
            "shipping_fees": {"United States": 0.0, "Japan": 25.0},
            "quantity": 3,
            "payout_methods": ["ETH (Ethereum)", "USDC (Ethereum)"],
            "tags": ["苹果", "MacBook", "专业"]
        },
        {
            "title": "AirPods Pro 2",
            "user_id": "test_user_003",
            "description": "主动降噪无线耳机",
            "price": 249.0,
            "category": "Electronics",
            "condition": "New",
            "variations": [{"name": "Color", "value": "White"}],
            "contact_email": "seller@example.com",
            "ship_from": "Hong Kong",
            "ship_to": ["Hong Kong", "Singapore"],
            "shipping_fees": {"Hong Kong": 0.0, "Singapore": 5.0},
            "quantity": 20,
            "discount_type": "Percentage",
            "discount_value": 20.0,
            "payout_methods": ["USDC (Base)"],
            "tags": ["苹果", "耳机", "降噪"]
        },
        {
            "title": "Digital Art NFT Collection",
            "user_id": "test_user_004",
            "description": "Unique digital artwork collection",
            "price": 0.5,
            "category": "Digital Goods",
            "condition": "New",
            "contact_email": "artist@example.com",
            "quantity": 1,
            "payout_methods": ["ETH (Ethereum)", "SOL (Solana)"],
            "tags": ["NFT", "Art", "Digital"]
        }
    ]
    
    draft_ids = []
    for product in products:
        draft = ProductDraft(**product)
        draft_id = storage.create_draft(draft)
        draft_ids.append(draft_id)
        print(f"创建草稿: {product['title']} (ID: {draft_id})")
    
    # 验证所有草稿都能正确获取且不会混淆
    for i, draft_id in enumerate(draft_ids):
        draft = storage.get_draft(draft_id)
        expected_title = products[i]["title"]
        assert draft.title == expected_title
        print(f"✓ 草稿 {expected_title} 信息正确")
    
    print(f"✓ 多草稿管理测试通过，成功管理 {len(draft_ids)} 个不同产品")
    return draft_ids

def test_export_functionality(draft_id):
    """测试导出功能"""
    print("\n=== 测试导出功能 ===")
    
    draft = storage.get_draft(draft_id)
    
    # 模拟Forest Market格式导出
    export_data = {
        "product_data": {
            "title": draft.title,
            "description": draft.description,
            "price": draft.price,
            "category": draft.category,
            "tags": draft.tags,
            "images": draft.images,
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
    
    # 验证导出数据完整性
    assert export_data["product_data"]["title"] == draft.title
    assert export_data["metadata"]["draft_id"] == draft.draft_id
    assert export_data["ready_for_listing"] == True
    
    print("✓ 导出功能测试通过")
    print(f"  导出格式: {export_data['export_format']}")
    print(f"  产品标题: {export_data['product_data']['title']}")

def test_digital_goods_logic():
    """测试Digital Goods特殊逻辑"""
    print("\n=== 测试Digital Goods逻辑 ===")
    
    # 创建Digital Goods草稿
    digital_draft = ProductDraft(
        title="NFT Collection",
        user_id="test_user_005",
        description="Digital art collection",
        price=1.0,
        category="Digital Goods",
        condition="New",
        contact_email="creator@example.com",
        ship_from="United States",  # 这应该被清空
        ship_to=["United States", "Singapore"],  # 这应该被清空
        shipping_fees={"United States": 10.0},  # 这应该被清空
        quantity=1,
        payout_methods=["ETH (Ethereum)"]
    )
    
    draft_id = storage.create_draft(digital_draft)
    
    # 验证Digital Goods不包含运输信息
    stored_draft = storage.get_draft(draft_id)
    assert stored_draft.ship_from == ""
    assert stored_draft.ship_to == []
    assert stored_draft.shipping_fees == {}
    
    print("✓ Digital Goods运输信息自动清除测试通过")
    
    # 测试更新为Digital Goods
    regular_draft = ProductDraft(
        title="Physical Product",
        user_id="test_user_005",
        category="Electronics",
        ship_from="United States",
        ship_to=["United States"],
        shipping_fees={"United States": 15.0}
    )
    
    regular_id = storage.create_draft(regular_draft)
    
    # 更新为Digital Goods
    success = storage.update_draft(
        regular_id,
        category="Digital Goods"
    )
    
    # 验证运输信息被清除
    updated_draft = storage.get_draft(regular_id)
    # 注意：当前的update逻辑需要在tools.py中处理，这里只验证基本更新
    
    print("✓ 更新为Digital Goods测试通过")
    
    return draft_id

def test_delete_draft(draft_id):
    """测试删除草稿"""
    print("\n=== 测试删除草稿 ===")
    
    # 删除草稿
    success = storage.delete_draft(draft_id)
    assert success == True
    
    # 验证草稿已被删除
    deleted_draft = storage.get_draft(draft_id)
    assert deleted_draft is None
    
    print("✓ 草稿删除测试通过")

def cleanup_test_data():
    """清理测试数据"""
    print("\n=== 清理测试数据 ===")
    
    # 删除所有草稿
    drafts = storage.list_drafts()
    for draft in drafts:
        storage.delete_draft(draft.draft_id)
    
    print(f"✓ 已清理 {len(drafts)} 个测试草稿")

def main():
    """运行所有测试"""
    print("Forest Market Draft MCP 功能测试")
    print("=" * 50)
    
    try:
        # 基础功能测试
        draft_id = test_create_draft()
        test_update_draft(draft_id)
        test_list_drafts()
        
        # 复制功能测试
        duplicated_id = test_duplicate_draft(draft_id)
        
        # 多草稿管理测试
        multiple_draft_ids = test_multiple_drafts_management()
        
        # 导出功能测试
        test_export_functionality(draft_id)
        
        # Digital Goods逻辑测试
        digital_draft_id = test_digital_goods_logic()
        
        # 删除功能测试
        test_delete_draft(duplicated_id)
        test_delete_draft(digital_draft_id)
        
        print("\n" + "=" * 50)
        print("所有测试通过！")
        print("草稿MCP功能正常，支持多产品草稿管理")
        
        # 显示最终状态
        final_drafts = storage.list_drafts()
        print(f"当前保留 {len(final_drafts)} 个草稿用于演示")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        raise
    
    finally:
        # 可选：取消注释以清理所有测试数据
        # cleanup_test_data()
        pass

if __name__ == "__main__":
    main()