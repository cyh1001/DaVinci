#!/usr/bin/env python3
"""
Simple MCP client to test the FastMCP product listing tool
"""

import asyncio
import json
import os
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from openai import OpenAI


def parse_unstructured_data_for_llm(user_input: str, data_type: str) -> str:
    """
    Parse unstructured user input and provide guidance for LLM to structure it properly
    
    Args:
        user_input: Raw user input describing variations or shipping
        data_type: Either 'variations' or 'shipping_prices'
    
    Returns:
        Formatted prompt section with examples based on user input
    """
    if data_type == 'variations':
        return f"""
        Based on user input: "{user_input}"
        
        Format variations_data as: [{"name": "VariationName", "values": ["option1", "option2", "option3"]}]
        
        Examples:
        - "Size small medium large" → [{"name": "Size", "values": ["Small", "Medium", "Large"]}]
        - "Color red blue, Material cotton polyester" → [{"name": "Color", "values": ["Red", "Blue"]}, {"name": "Material", "values": ["Cotton", "Polyester"]}]
        - "No variations" → null (omit variations_data field)
        """
    
    elif data_type == 'shipping_prices':
        return f"""
        Based on user input: "{user_input}"
        
        Format shipping_prices_data as: [{"country_code": "US", "price": 10.0, "currency_code": "USDT"}]
        
        Examples:
        - "US $10, Singapore $15" → [{"country_code": "US", "price": 10.0}, {"country_code": "SG", "price": 15.0}]
        - "Free shipping to US" → [{"country_code": "US", "price": 0.0}]
        - "Standard shipping" → null (omit shipping_prices_data field, will use defaults)
        """
    
    return ""


def create_enhanced_prompt_with_examples(tool_schema, task_description, variations_input="", shipping_input=""):
    """Create an enhanced prompt with real examples for structured data"""
    
    base_prompt = create_tool_prompt(tool_schema, task_description)
    
    # Add structured data examples if provided
    additional_guidance = ""
    
    if variations_input:
        additional_guidance += parse_unstructured_data_for_llm(variations_input, 'variations')
    
    if shipping_input:
        additional_guidance += parse_unstructured_data_for_llm(shipping_input, 'shipping_prices')
    
    if additional_guidance:
        enhanced_prompt = base_prompt + "\n\nADDITIONAL GUIDANCE FOR STRUCTURED DATA:\n" + additional_guidance
        return enhanced_prompt
    
    return base_prompt


def extract_tool_schema(tool):
    """Extract schema information from an MCP tool"""
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": tool.inputSchema
    }


def create_tool_prompt(tool_schema, task_description):
    """Create a prompt for LLM to generate tool parameters"""
    
    # Add specific validation rules for upload_listing tool
    validation_rules = ""
    if tool_schema['name'] == 'upload_listing':
        validation_rules = """
    
    IMPORTANT VALIDATION RULES:
    1. Category-specific shipping requirements:
       - DIGITAL_GOODS: ship_from_country and ship_to_countries are OPTIONAL
       - CUSTOM and OTHER: ship_from_country and ship_to_countries are REQUIRED  
       - Physical goods (DEPIN, ELECTRONICS, FASHION, COLLECTIBLES): ship_from_country and ship_to_countries are REQUIRED
    
    2. Condition requirements:
       - DIGITAL_GOODS and CUSTOM: condition is OPTIONAL (do not include)
       - All other categories: condition is REQUIRED (must be "NEW" or "USED")
    
    3. Discount validation:
       - If discount_type is "PERCENTAGE": discount_value must be between 0.1 and 0.5 (representing 10% to 50%)
       - If discount_type is "FIXED_AMOUNT": discount_value should be a specific dollar amount (e.g., 50.0 for $50)
       - If no discount, omit both discount_type and discount_value
    
    4. Payment options available: ETH_ETHEREUM, ETH_BASE, SOL_SOLANA, USDC_ETHEREUM, USDC_BASE, USDC_SOLANA, USDT_ETHEREUM
    
    5. Country codes available: US, SG, HK, KR, JP
    
    6. Structured data formats:
       - variations_data: Array of objects with "name" and "values" fields
         Example: [{"name": "Size", "values": ["S", "M", "L"]}, {"name": "Color", "values": ["Red", "Blue"]}]
       
       - shipping_prices_data: Array of objects with "country_code", "price", and optional "currency_code" fields
         Example: [{"country_code": "US", "price": 10.0, "currency_code": "USDT"}, {"country_code": "SG", "price": 15.0}]
    
    7. Image paths: Use realistic file paths like ["/path/to/product/image1.jpg", "/path/to/product/image2.png"]
    """
    
    return f"""
    You need to call the following tool: {task_description}
    
    Tool: {tool_schema['name']}
    Description: {tool_schema['description']}
    
    Input Schema:
    {json.dumps(tool_schema['inputSchema'], indent=2)}
    {validation_rules}
    
    Generate appropriate parameters based on this schema and validation rules.
    Respond with a JSON object containing only the parameters defined in the schema.
    Do not include any explanatory text, just the JSON object.
    """


async def test_fastmcp_connection():
    """Test connection to the FastMCP server"""
    print("🔗 Testing FastMCP Server Connection...")
    
    try:
        # Connect to your MCP server
        server_params = StdioServerParameters(
            command="python",
            args=["/home/haorui/Python/DarwinG-Upload/mcp_product_listing.py", "mcp"]
        )
        async with stdio_client(server_params) as (read, write):
            
            async with ClientSession(read, write) as session:
                print("✅ Connected to FastMCP server")
                
                # Initialize
                await session.initialize()
                print("✅ Session initialized")
                
                # List available tools
                tools_response = await session.list_tools()
                tool_names = []
                for tool in tools_response.tools:
                    tool_names.append(tool.name)
                print(f"📋 Available tools: {tool_names}")
                
                # Test tool call with session token from environment
                print("\n🧪 Testing tool call...")
                
                # Load session token from environment
                load_dotenv("../.env")
                session_token = os.getenv("FM_SESSION_TOKEN")
                
                if not session_token:
                    print("⚠️  No SESSION_TOKEN found in environment, using test token")
                    session_token = "test_token"
                else:
                    print("✅ Using session token from environment")
                
                result = await session.call_tool("upload_listing", {
                    "title": "FastMCP Test Product",
                    "description": "Testing FastMCP tool integration with improved error handling",
                    "category": "DIGITAL_GOODS",
                    "image_file_paths": ["/home/haorui/Python/DarwinG-Upload/light-blue-cotton-tshirt.jpg"],
                    "price": 99.99,
                    "quantity": 1,
                    "payment_options": ["USDC_BASE"],
                    "session_token": session_token
                })
                
                print("📄 Tool result:")
                for content in result.content:
                    if hasattr(content, 'text'):
                        try:
                            result_data = json.loads(content.text)
                            print(json.dumps(result_data, indent=2))
                        except json.JSONDecodeError:
                            print(content.text)
                
                return True
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_llm_upload_listing():
    """Test using OpenAI model to call the upload_listing tool"""
    print("🤖 Testing LLM-driven upload_listing tool call...")
    
    try:
        # Load environment variables
        load_dotenv("../.env")
        
        # Initialize OpenAI client
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Connect to MCP server
        server_params = StdioServerParameters(
            command="python",
            args=["/home/haorui/Python/DarwinG-Upload/mcp_product_listing.py", "mcp"]
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                print("✅ Connected to MCP server")
                
                # Initialize session
                await session.initialize()
                
                # Get available tools
                tools_response = await session.list_tools()
                upload_tool = None
                
                for tool in tools_response.tools:
                    if tool.name == "upload_listing":
                        upload_tool = tool
                        break
                
                if not upload_tool:
                    print("❌ upload_listing tool not found")
                    return False
                
                print("✅ Found upload_listing tool")
                
                # Extract tool schema using helper function
                tool_schema = extract_tool_schema(upload_tool)
                
                print(f"📋 Tool schema extracted:")
                print(json.dumps(tool_schema, indent=2))
                
                # Test with different product types to demonstrate validation rules
                test_cases = [
                    {
                        "name": "Digital Product (E-book)",
                        "description": "to create a product listing for a digital photography e-book",
                        "category": "DIGITAL_GOODS",
                        "variations_input": "",
                        "shipping_input": ""
                    },
                    {
                        "name": "Physical Product with Variations (Vintage Jacket)", 
                        "description": "to create a product listing for a vintage leather jacket",
                        "category": "FASHION",
                        "variations_input": "Size small medium large, Color black brown",
                        "shipping_input": "US $10, Singapore $15, free shipping to Hong Kong"
                    },
                    {
                        "name": "Custom Product with Complex Data",
                        "description": "to create a product listing for a custom-made wooden table",
                        "category": "CUSTOM",
                        "variations_input": "Wood type oak pine cherry, Size 4ft 6ft 8ft, Finish natural stained glossy",
                        "shipping_input": "US $50 express, Korea $75 standard"
                    }
                ]
                
                # Test the second case to demonstrate structured data handling
                test_case = test_cases[1]  # Test fashion product with variations
                print(f"\n--- Testing: {test_case['name']} ---")
                print(f"Unstructured variations input: '{test_case['variations_input']}'")
                print(f"Unstructured shipping input: '{test_case['shipping_input']}'")
                
                # Create enhanced prompt with unstructured data guidance
                task_description = f"{test_case['description']} (Category: {test_case['category']})"
                prompt = create_enhanced_prompt_with_examples(
                    tool_schema, 
                    task_description,
                    test_case['variations_input'],
                    test_case['shipping_input']
                )
                
                # Get LLM response
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that generates product listing parameters in JSON format. Follow all validation rules strictly."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7
                )
                
                # Parse LLM response
                llm_content = response.choices[0].message.content
                print(f"🧠 LLM generated parameters: {llm_content}")
                
                try:
                    # Extract JSON from LLM response
                    start_idx = llm_content.find('{')
                    end_idx = llm_content.rfind('}') + 1
                    json_str = llm_content[start_idx:end_idx]
                    llm_params = json.loads(json_str)
                    
                    # Add session token
                    session_token = os.getenv("FM_SESSION_TOKEN")
                    if not session_token:
                        session_token = "test_token"
                    llm_params["session_token"] = session_token
                    
                    print(f"📋 Calling upload_listing with LLM-generated params:")
                    print(json.dumps(llm_params, indent=2))
                    
                    # Validate the parameters match the category rules
                    category = llm_params.get("category", "")
                    print(f"\n✅ Validation check for category '{category}':")
                    
                    if category == "DIGITAL_GOODS":
                        ship_from = llm_params.get("ship_from_country")
                        ship_to = llm_params.get("ship_to_countries")
                        condition = llm_params.get("condition")
                        print(f"   - ship_from_country: {ship_from} (optional for digital goods)")
                        print(f"   - ship_to_countries: {ship_to} (optional for digital goods)")
                        print(f"   - condition: {condition} (should be omitted for digital goods)")
                    elif category == "FASHION":
                        condition = llm_params.get("condition")
                        variations = llm_params.get("variations_data")
                        shipping = llm_params.get("shipping_prices_data")
                        print(f"   - condition: {condition} (required for physical goods)")
                        print(f"   - variations_data: {variations}")
                        print(f"   - shipping_prices_data: {shipping}")
                        
                        # Validate structured data format
                        if variations:
                            print(f"   ✅ Variations properly structured: {len(variations)} variation types")
                            for var in variations:
                                if 'name' in var and 'values' in var:
                                    print(f"      - {var['name']}: {var['values']}")
                                else:
                                    print(f"      ❌ Invalid variation format: {var}")
                        
                        if shipping:
                            print(f"   ✅ Shipping prices properly structured: {len(shipping)} countries")
                            for ship in shipping:
                                if 'country_code' in ship and 'price' in ship:
                                    currency = ship.get('currency_code', 'USDT')
                                    print(f"      - {ship['country_code']}: {ship['price']} {currency}")
                                else:
                                    print(f"      ❌ Invalid shipping format: {ship}")
                    
                    # Call the tool with LLM-generated parameters
                    result = await session.call_tool("upload_listing", llm_params)
                    
                    print("📄 Tool result:")
                    for content in result.content:
                        if hasattr(content, 'text'):
                            try:
                                result_data = json.loads(content.text)
                                print(json.dumps(result_data, indent=2))
                            except json.JSONDecodeError:
                                print(content.text)
                    
                    return True
                    
                except json.JSONDecodeError as e:
                    print(f"❌ Failed to parse LLM response as JSON: {e}")
                    print(f"LLM response: {llm_content}")
                    return False
                
    except Exception as e:
        print(f"❌ Error in LLM test: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("🚀 FastMCP Client Test")
    print("=" * 40)
    
    # Test basic MCP connection
    success = await test_fastmcp_connection()
    
    if success:
        print("\n🎉 Basic MCP server test passed!")
    else:
        print("\n❌ Basic MCP server test failed")
        print("   Check that your FastMCP server is properly configured")
        return
    
    # Test LLM integration
    print("\n" + "=" * 40)
    print("🤖 Testing LLM Integration")
    print("=" * 40)
    
    llm_success = await test_llm_upload_listing()
    
    if llm_success:
        print("\n🎉 LLM integration test passed!")
        print("\n💡 Your MCP server can be used with LLMs to:")
        print("   - Generate dynamic product parameters")
        print("   - Create listings from natural language descriptions")
        print("   - Automate product catalog management")
    else:
        print("\n❌ LLM integration test failed")
        print("   Check your OpenAI API key configuration")
    
    print("\n💡 To use with Claude Desktop:")
    print("   Add this server to your claude_desktop_config.json")
    print("\n💡 To use with other agents:")
    print("   Use the MCP client pattern shown in this script")


if __name__ == "__main__":
    asyncio.run(main())