#!/usr/bin/env python3
"""
Helper script to check if all URLs from the CSV file are present in the JSON detail file.
"""

import csv
import json
import sys
from pathlib import Path
from typing import Set, List, Dict, Any


def extract_urls_from_csv(csv_path: str) -> Set[str]:
    """Extract all non-empty URLs from the CSV file."""
    urls = set()
    
    with open(csv_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            for key, value in row.items():
                if key != 'product_id' and value and value.strip():
                    urls.add(value.strip())
    
    return urls


def extract_urls_from_json(json_path: str) -> Set[str]:
    """Extract all URLs from the JSON detail file."""
    urls = set()
    
    with open(json_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
        
        if 'products' in data:
            for product in data['products']:
                if 'url' in product:
                    urls.add(product['url'])
    
    return urls


def compare_urls(csv_urls: Set[str], json_urls: Set[str]) -> Dict[str, Any]:
    """Compare URL sets and return analysis results."""
    missing_in_json = csv_urls - json_urls
    extra_in_json = json_urls - csv_urls
    common_urls = csv_urls & json_urls
    
    return {
        'csv_total': len(csv_urls),
        'json_total': len(json_urls),
        'common_count': len(common_urls),
        'missing_in_json': missing_in_json,
        'extra_in_json': extra_in_json,
        'all_csv_urls_in_json': len(missing_in_json) == 0
    }


def main():
    """Main function to compare URLs between CSV and JSON files."""
    # Default paths
    csv_path = Path("fm_data/url/fm_url.csv")
    json_path = Path("fm_data/json/fm_detail_20250730_170122.json")
    
    # Check if files exist
    if not csv_path.exists():
        print(f"Error: CSV file not found at {csv_path}")
        sys.exit(1)
    
    if not json_path.exists():
        print(f"Error: JSON file not found at {json_path}")
        sys.exit(1)
    
    print("Extracting URLs from CSV file...")
    csv_urls = extract_urls_from_csv(str(csv_path))
    
    print("Extracting URLs from JSON file...")
    json_urls = extract_urls_from_json(str(json_path))
    
    print("Comparing URL sets...")
    results = compare_urls(csv_urls, json_urls)
    
    # Print results
    print("\n" + "="*60)
    print("URL COMPARISON RESULTS")
    print("="*60)
    print(f"Total URLs in CSV file: {results['csv_total']}")
    print(f"Total URLs in JSON file: {results['json_total']}")
    print(f"Common URLs: {results['common_count']}")
    print(f"All CSV URLs present in JSON: {'✓ YES' if results['all_csv_urls_in_json'] else '✗ NO'}")
    
    if results['missing_in_json']:
        print(f"\nURLs missing in JSON ({len(results['missing_in_json'])}):")
        for url in sorted(results['missing_in_json']):
            print(f"  - {url}")
    
    if results['extra_in_json']:
        print(f"\nExtra URLs in JSON ({len(results['extra_in_json'])}):")
        for url in sorted(results['extra_in_json']):
            print(f"  + {url}")
    
    if results['all_csv_urls_in_json']:
        print("\n✓ SUCCESS: All URLs from CSV are present in the JSON file!")
    else:
        print("\n✗ INCOMPLETE: Some URLs from CSV are missing in the JSON file.")
        sys.exit(1)


if __name__ == "__main__":
    main()