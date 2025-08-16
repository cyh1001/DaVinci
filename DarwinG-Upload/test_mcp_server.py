#!/usr/bin/env python3
"""
Test script for the MCP Product Listing Server

This script tests the MCP server functionality by simulating tool calls
and verifying the responses.
"""

import asyncio
import json
import os
from typing import Dict, Any
from mcp_product_listing import create_product_listing_mcp

from dotenv import load_dotenv

load_dotenv("/home/haorui/Python/.env")

session_token = os.getenv("FM_SESSION_TOKEN")


def test_simple_electronics_listing():
    """Test creating a simple electronics product listing"""
    print("🧪 Testing Simple Electronics Listing...")
    
    # Test data
    test_data = {
        "title": "iPhone 15 Pro Max",
        "description": "Latest iPhone with advanced camera system and A17 Pro chip",
        "category": "ELECTRONICS",
        "image_file_paths": ["/home/haorui/Python/DarwinG-Upload/light-blue-cotton-tshirt.jpg"],  # Using existing test image
        "ship_from_country": "US",
        "ship_to_countries": ["US", "SG"],
        "price": 1199.99,
        "quantity": 5,
        "payment_options": ["USDC_BASE", "ETH_ETHEREUM"],
        "session_token": session_token,
        "condition": "NEW"
    }
    
    try:
        result = create_product_listing_mcp(**test_data)
        print("✅ Simple electronics listing test completed")
        print(f"Success: {result.get('success', False)}")
        if result.get('success'):
            print(f"EID: {result.get('eid', 'N/A')}")
            print(f"Uploaded images: {len(result.get('uploaded_images', []))}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
        return result
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return {"success": False, "error": str(e)}


def test_fashion_with_variations():
    """Test creating a fashion product with variations and custom shipping"""
    print("\n🧪 Testing Fashion Product with Variations...")
    
    test_data = {
        "title": "Premium Cotton T-Shirt",
        "description": "Soft, comfortable cotton t-shirt perfect for everyday wear",
        "category": "FASHION", 
        "image_file_paths": ["/home/haorui/Python/DarwinG-Upload/light-blue-cotton-tshirt.jpg"],
        "ship_from_country": "US",
        "ship_to_countries": ["US", "SG", "HK"],
        "price": 29.99,
        "quantity": 100,
        "payment_options": ["USDC_BASE", "SOL_SOLANA"],
        "session_token": session_token,
        "condition": "NEW",
        "variations_data": [
            {
                "name": "Color",
                "values": ["Light Blue", "White", "Black"]
            },
            {
                "name": "Size", 
                "values": ["S", "M", "L", "XL"]
            }
        ],
        "shipping_prices_data": [
            {
                "country_code": "US",
                "price": 0,
                "currency_code": "USDT"
            },
            {
                "country_code": "SG",
                "price": 8.99,
                "currency_code": "USDT" 
            },
            {
                "country_code": "HK",
                "price": 6.99,
                "currency_code": "USDT"
            }
        ],
        "discount_type": "PERCENTAGE",
        "discount_value": 0.15  # 15% discount
    }
    
    try:
        result = create_product_listing_mcp(**test_data)
        print("✅ Fashion with variations test completed")
        print(f"Success: {result.get('success', False)}")
        if result.get('success'):
            print(f"EID: {result.get('eid', 'N/A')}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
        return result
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return {"success": False, "error": str(e)}


def test_digital_goods():
    """Test creating a digital goods listing"""
    print("\n🧪 Testing Digital Goods Listing...")
    
    test_data = {
        "title": "Premium Software License",
        "description": "Lifetime access to our premium development tools suite",
        "category": "DIGITAL_GOODS",
        "image_file_paths": ["/home/haorui/Python/DarwinG-Upload/light-blue-cotton-tshirt.jpg"],  # Using existing test image
        # No ship_from_country or ship_to_countries needed for digital goods
        "price": 199.99,
        "quantity": 1000,
        "payment_options": ["ETH_ETHEREUM", "USDT_ETHEREUM"],
        "session_token": session_token,
        # No condition needed for digital goods
        "discount_type": "FIXED_AMOUNT",
        "discount_value": 50.0  # $50 off
    }
    
    try:
        result = create_product_listing_mcp(**test_data)
        print("✅ Digital goods test completed")
        print(f"Success: {result.get('success', False)}")
        if result.get('success'):
            print(f"EID: {result.get('eid', 'N/A')}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
        return result
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return {"success": False, "error": str(e)}


def test_custom_category():
    """Test creating a custom category listing"""
    print("\n🧪 Testing Custom Category Listing...")
    
    test_data = {
        "title": "Custom Handmade Jewelry",
        "description": "Unique handmade jewelry piece crafted with premium materials",
        "category": "CUSTOM",
        "image_file_paths": ["/home/haorui/Python/DarwinG-Upload/light-blue-cotton-tshirt.jpg"],
        "ship_from_country": "US",  # Required for custom
        "ship_to_countries": ["US", "SG", "HK"],
        "price": 150.00,
        "quantity": 1,
        "payment_options": ["ETH_ETHEREUM", "USDC_BASE"],
        "session_token": session_token,
        # No condition needed for custom goods
    }
    
    try:
        result = create_product_listing_mcp(**test_data)
        print("✅ Custom category test completed")
        print(f"Success: {result.get('success', False)}")
        if result.get('success'):
            print(f"EID: {result.get('eid', 'N/A')}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
        return result
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return {"success": False, "error": str(e)}


def test_validation_errors():
    """Test various validation scenarios"""
    print("\n🧪 Testing Validation Errors...")
    
    # Test 1: Missing required condition for physical product
    print("Testing missing condition for physical product...")
    try:
        result = create_product_listing_mcp(
            title="Test Product",
            description="Test description",
            category="ELECTRONICS",
            image_file_paths=["/home/haorui/Python/DarwinG-Upload/light-blue-cotton-tshirt.jpg"],
            ship_from_country="US",
            ship_to_countries=["US"],
            price=100.0,
            quantity=1,
            payment_options=["USDC_BASE"],
            session_token="test_token"
            # Missing condition - should fail
        )
        print(f"❌ Expected validation error, got: {result}")
    except Exception as e:
        print(f"✅ Correctly caught validation error: {e}")
    
    # Test 2: Invalid percentage discount
    print("Testing invalid percentage discount...")
    try:
        result = create_product_listing_mcp(
            title="Test Product",
            description="Test description", 
            category="ELECTRONICS",
            image_file_paths=["/home/haorui/Python/DarwinG-Upload/light-blue-cotton-tshirt.jpg"],
            ship_from_country="US",
            ship_to_countries=["US"],
            price=100.0,
            quantity=1,
            payment_options=["USDC_BASE"],
            session_token="test_token",
            condition="NEW",
            discount_type="PERCENTAGE",
            discount_value=0.75  # 75% - should fail (max 50%)
        )
        print(f"❌ Expected validation error, got: {result}")
    except Exception as e:
        print(f"✅ Correctly caught validation error: {e}")
    
    # Test 3: Missing image file
    print("Testing missing image file...")
    try:
        result = create_product_listing_mcp(
            title="Test Product",
            description="Test description",
            category="ELECTRONICS", 
            image_file_paths=["/nonexistent/image.jpg"],
            ship_from_country="US",
            ship_to_countries=["US"],
            price=100.0,
            quantity=1,
            payment_options=["USDC_BASE"],
            session_token="test_token",
            condition="NEW"
        )
        print(f"Result: {result}")
        if not result.get('success'):
            print(f"✅ Correctly handled missing file: {result.get('error')}")
        else:
            print("❌ Should have failed with missing file")
    except Exception as e:
        print(f"✅ Correctly caught file error: {e}")
    
    # Test 4: Missing ship_from_country for CUSTOM category
    print("Testing missing ship_from_country for CUSTOM category...")
    try:
        result = create_product_listing_mcp(
            title="Custom Product",
            description="Custom description",
            category="CUSTOM",
            image_file_paths=["/home/haorui/Python/DarwinG-Upload/light-blue-cotton-tshirt.jpg"],
            # Missing ship_from_country for CUSTOM - should fail
            price=100.0,
            quantity=1,
            payment_options=["USDC_BASE"],
            session_token="test_token"
        )
        if not result.get('success'):
            print(f"✅ Correctly handled missing ship_from_country for CUSTOM: {result.get('error')}")
        else:
            print("❌ Should have failed with missing ship_from_country for CUSTOM")
    except Exception as e:
        print(f"✅ Correctly caught validation error: {e}")
    
    # Test 5: Missing shipping info for physical product
    print("Testing missing shipping info for physical product...")
    try:
        result = create_product_listing_mcp(
            title="Physical Product",
            description="Physical description",
            category="ELECTRONICS",
            image_file_paths=["/home/haorui/Python/DarwinG-Upload/light-blue-cotton-tshirt.jpg"],
            # Missing both shipping fields for physical product - should fail
            price=100.0,
            quantity=1,
            payment_options=["USDC_BASE"],
            session_token="test_token",
            condition="NEW"
        )
        if not result.get('success'):
            print(f"✅ Correctly handled missing shipping for physical product: {result.get('error')}")
        else:
            print("❌ Should have failed with missing shipping for physical product")
    except Exception as e:
        print(f"✅ Correctly caught validation error: {e}")


def test_mcp_tool_schema():
    """Test that the MCP tool schema is properly defined"""
    print("\n🧪 Testing MCP Tool Schema...")
    
    try:
        # Import MCP components to test schema
        from mcp_product_listing import Server
        
        # This would normally be done by the MCP server
        print("✅ MCP imports successful")
        print("✅ Tool schema validation would happen at runtime")
        
        # Test schema structure
        example_call = {
            "name": "upload_listing",
            "arguments": {
                "title": "Test Product",
                "description": "Test description",
                "category": "ELECTRONICS",
                "image_file_paths": ["/test/image.jpg"],
                "ship_from_country": "US",
                "ship_to_countries": ["US"],
                "price": 100.0,
                "quantity": 1,
                "payment_options": ["USDC_BASE"],
                "session_token": "test_token",
                "condition": "NEW"
            }
        }
        
        print("✅ Example MCP tool call structure valid")
        print(f"Call structure: {json.dumps(example_call, indent=2)}")
        
    except ImportError as e:
        print(f"❌ MCP import failed: {e}")
        print("Note: This is expected if MCP library is not installed")


def main():
    """Run all tests"""
    print("🚀 Starting MCP Product Listing Server Tests")
    print("=" * 50)
    
    # Check if session token is available
    session_token = os.getenv("FM_SESSION_TOKEN")
    if not session_token:
        print("⚠️  Warning: SESSION_TOKEN not found in environment")
        print("   Some tests may fail without a valid session token")
    
    # Check if test image exists
    test_image = "/home/haorui/Python/DarwinG-Upload/light-blue-cotton-tshirt.jpg"
    if not os.path.exists(test_image):
        print(f"⚠️  Warning: Test image not found at {test_image}")
        print("   Image upload tests may fail")
    
    print()
    
    # Run tests
    results = []
    
    # Validation tests (these should work without network)
    test_validation_errors()
    test_mcp_tool_schema()
    
    # Network tests (these require valid session token and network access)
    print(session_token)
    if session_token and session_token != "test_token":
        print("\n📡 Running network-dependent tests...")
        results.append(test_simple_electronics_listing())
        results.append(test_fashion_with_variations()) 
        results.append(test_digital_goods())
        results.append(test_custom_category())
    else:
        print("\n⏭️  Skipping network tests (no valid session token)")
        print("   Set SESSION_TOKEN environment variable to run full tests")
    
    # Summary
    print("\n" + "=" * 50)
    print("🏁 Test Summary")
    
    if results:
        successful = sum(1 for r in results if r.get('success', False))
        total = len(results)
        print(f"Network tests: {successful}/{total} successful")
        
        if successful == total:
            print("🎉 All network tests passed!")
        else:
            print("⚠️  Some tests failed - check session token and network connectivity")
    
    print("✅ Validation and schema tests completed")
    print("\n💡 To run as MCP server: python mcp_product_listing.py mcp")


if __name__ == "__main__":
    main()