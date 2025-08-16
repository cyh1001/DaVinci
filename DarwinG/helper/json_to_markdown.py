#!/usr/bin/env python3
"""
Helper script to convert Forest Market JSON product data to Markdown format.
Each product is separated by "---" for easy reading.
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any


def format_list_items(items: List[Any], max_items: int = 5) -> str:
    """Format list items for markdown display"""
    if not items:
        return "None"
    
    # Filter out empty items
    filtered_items = [str(item).strip() for item in items if item and str(item).strip()]
    
    if not filtered_items:
        return "None"
    
    # Limit number of items shown
    display_items = filtered_items[:max_items]
    if len(filtered_items) > max_items:
        display_items.append(f"... and {len(filtered_items) - max_items} more")
    
    return ", ".join(display_items)


def format_product_to_markdown(product: Dict[str, Any], index: int) -> str:
    """Convert a single product to simple format with --- separators"""
    md_content = []
    
    # Product title
    title = product.get('product_title', 'Untitled Product')
    md_content.append(f"Product {index + 1}: {title}")
    
    # Basic product information
    if product.get('product_description'):
        md_content.append(f"Description: {product['product_description']}")
    
    # Price and currency information
    price = product.get('price', 'N/A')
    currency = product.get('currency', '')
    if price != 'N/A' and currency:
        md_content.append(f"Price: {price} {currency}")
    elif price != 'N/A':
        md_content.append(f"Price: {price}")
    
    discount_price = product.get('discount_price')
    if discount_price:
        md_content.append(f"Discount Price: {discount_price}")
    
    # Product details
    if product.get('product_condition'):
        md_content.append(f"Condition: {product['product_condition']}")
    
    if product.get('seller_name'):
        md_content.append(f"Seller: {product['seller_name']}")
    
    if product.get('source_country'):
        md_content.append(f"Source Country: {product['source_country']}")
    
    if product.get('product_id'):
        md_content.append(f"Product ID: {product['product_id']}")
    
    
    # Availability across countries
    availability_info = []
    for country in ['en-US', 'en-SG', 'en-HK', 'en-KR', 'en-JP']:
        available_key = f"{country}_available"
        if available_key in product:
            status = "✅" if product[available_key] else "❌"
            country_name = {
                'en-US': 'United States',
                'en-SG': 'Singapore', 
                'en-HK': 'Hong Kong',
                'en-KR': 'South Korea',
                'en-JP': 'Japan'
            }.get(country, country)
            availability_info.append(f"{status} {country_name}")
    
    if availability_info:
        md_content.append(f"Availability: {', '.join(availability_info)}")
    
    # Product variants - Show ALL without limits
    sizes = product.get('sizes', [])
    colors = product.get('colors', [])
    
    if sizes:
        md_content.append(f"Available Sizes: {format_list_items(sizes, max_items=999)}")
    if colors:
        md_content.append(f"Available Colors: {format_list_items(colors, max_items=999)}")
    
    # Payment methods - Show ALL
    payment_methods = product.get('payment_methods', [])
    if payment_methods:
        md_content.append(f"Payment Methods: {format_list_items(payment_methods, max_items=999)}")
    
    # Shipping and return details
    if product.get('shipping_details'):
        md_content.append(f"Shipping: {product['shipping_details']}")
    
    if product.get('return_details'):
        md_content.append(f"Return Policy: {product['return_details']}")
    
    # Additional fields that might exist - catch all other data
    excluded_fields = {
        'product_title', 'product_description', 'price', 'currency', 'discount_price',
        'product_condition', 'seller_name', 'source_country', 'product_id',
        'main_image', 'product_images', 'image_alts', 'sizes', 'colors',
        'payment_methods', 'shipping_details', 'return_details', 'url', 'crawled_at'
    } | {f"{country}_available" for country in ['en-US', 'en-SG', 'en-HK', 'en-KR', 'en-JP']}
    
    for key, value in product.items():
        if key not in excluded_fields and value is not None:
            if isinstance(value, list):
                if value:  # Only show non-empty lists
                    formatted_value = format_list_items(value, max_items=999)
                    md_content.append(f"{key.replace('_', ' ').title()}: {formatted_value}")
            elif isinstance(value, (str, int, float, bool)):
                if str(value).strip():  # Only show non-empty values
                    md_content.append(f"{key.replace('_', ' ').title()}: {value}")
    
    # Technical details
    md_content.append(f"Source URL: {product.get('url', 'N/A')}")
    
    return "\n".join(md_content)


def convert_json_to_markdown(json_file_path: str, output_file_path: str = None, max_products: int = None) -> str:
    """Convert JSON product data to markdown format"""
    
    # Read JSON file
    try:
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"JSON file not found: {json_file_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON file: {e}")
    
    # Extract products and metadata
    products = data.get('products', [])
    metadata = data.get('metadata', {})
    
    if not products:
        raise ValueError("No products found in JSON file")
    
    # Limit products if specified
    if max_products:
        products = products[:max_products]
    
    # Generate markdown content
    md_content = []
    
    # Convert each product with --- separators
    for i, product in enumerate(products):
        md_content.append("---")
        product_md = format_product_to_markdown(product, i)
        md_content.append(product_md)
    
    # Final separator
    md_content.append("---")
    
    final_markdown = "\n".join(md_content)
    
    # Save to file if output path specified
    if output_file_path:
        with open(output_file_path, 'w', encoding='utf-8') as file:
            file.write(final_markdown)
        print(f"Markdown saved to: {output_file_path}")
    
    return final_markdown


def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(
        description='Convert Forest Market JSON product data to Markdown format',
        epilog="""
Examples:
  %(prog)s --input fm_data/json/fm_detail_20250730_170122.json
  %(prog)s --input fm_data/json/fm_detail_20250730_170122.json --output products.md
  %(prog)s --input fm_data/json/fm_detail_20250730_170122.json --max-products 10
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--input', '-i', required=True, 
                       help='Input JSON file path')
    parser.add_argument('--output', '-o', 
                       help='Output markdown file path (default: {input_name}.md)')
    parser.add_argument('--max-products', '-m', type=int,
                       help='Maximum number of products to include')
    parser.add_argument('--print', '-p', action='store_true',
                       help='Print markdown to console instead of saving to file')
    
    args = parser.parse_args()
    
    # Validate input file
    if not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)
    
    # Generate output filename if not provided
    if not args.output and not args.print:
        input_path = Path(args.input)
        args.output = str(input_path.parent / f"{input_path.stem}.md")
    
    try:
        # Convert JSON to markdown
        markdown_content = convert_json_to_markdown(
            args.input, 
            args.output if not args.print else None,
            args.max_products
        )
        
        # Print to console if requested
        if args.print:
            print(markdown_content)
        
        print(f"Successfully converted {args.input} to markdown!")
        if args.max_products:
            print(f"Limited to first {args.max_products} products")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()