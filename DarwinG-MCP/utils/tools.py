import os
import pandas as pd
import urllib.parse
import requests
import csv
import uuid
import openpyxl
from typing import Any, Dict, Optional, List, Type
import json
from pydantic import BaseModel, ValidationError
from .custom_data_structure import ShippingPriceData, VariationData


def download_image_from_url(url: str) -> str:
    """Download image from URL and save to temporary file, return local path"""
    try:
        # Parse URL to get filename
        parsed_url = urllib.parse.urlparse(url)
        filename = os.path.basename(parsed_url.path)
        
        # If no filename in URL, generate one
        if not filename or '.' not in filename:
            filename = f"downloaded_image_{hash(url) % 10000}.jpg"
        
        # Create temporary file with proper extension
        temp_dir = "/tmp"
        temp_path = os.path.join(temp_dir, filename)
        
        # Download the image
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Save to temporary file
        with open(temp_path, 'wb') as f:
            f.write(response.content)
        
        print(f"Downloaded image from {url} to {temp_path}")
        return temp_path
        
    except Exception as e:
        print(f"Failed to download image from {url}: {e}")
        raise Exception(f"Failed to download image from URL: {url}")

def is_url(path: str) -> bool:
    """Check if a string is a URL"""
    return path.startswith(('http://', 'https://'))

def is_user_confirmed(confirmation_value: Any) -> bool:
    """Check if user confirmation is true, handling various input types"""
    if isinstance(confirmation_value, bool):
        return confirmation_value
    
    if isinstance(confirmation_value, str):
        lower_val = confirmation_value.lower().strip()
        return lower_val in ['true', 'yes', '1', 'confirm', 'confirmed', 'ok', 'proceed']
    
    if isinstance(confirmation_value, (int, float)):
        return confirmation_value > 0
    
    return False

def get_presigned_url(file_name: str, file_type: str, session_token: str) -> Dict[str, Any]:
    """Get presigned URL from the tRPC API for S3 upload"""
    
    url = "https://forestmarket.net/api/trpc/upload.getPresignedUrl?batch=1"
    
    payload = {
        "0": {
            "json": {
                "fileName": file_name,
                "fileType": file_type
            }
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "trpc-accept": "application/json",
    }
    
    cookies = {
        "__Secure-next-auth.session-token": session_token
    }
    
    response = requests.post(url, json=payload, headers=headers, cookies=cookies)
    
    if response.status_code == 200:
        result = response.json()
        return result[0]["result"]["data"]["json"]
    else:
        raise Exception(f"Failed to get presigned URL: {response.status_code} - {response.text}")

def upload_file_to_s3(file_path: str, presigned_url: str, file_type: str) -> bool:
    """Upload file directly to S3 using presigned URL"""
    
    with open(file_path, 'rb') as file:
        headers = {
            "Content-Type": file_type,
        }
        
        response = requests.put(
            presigned_url,
            data=file,
            headers=headers
        )
        
        return response.status_code in [200, 204]


def process_excel_with_images(
    excel_path: str,
    output_dir: str = None,
    image_column_name: str = '图片',
    image_file_paths_column: str = 'image_file_paths',
    sheet_name: str = None
) -> 'pd.DataFrame':
    """
    Processes an Excel file, extracts floating images, saves them to disk, and adds/replaces a column with image file paths.
    Args:
        excel_path: Path to the Excel file.
        output_dir: Directory to save extracted images. Defaults to '<excel_path>_images'.
        image_column_name: Name of the column expected to contain images (for checking existence).
        image_file_paths_column: Name of the column to add/replace with image file paths.
        sheet_name: Sheet to process. Defaults to the first sheet.
    Returns:
        pd.DataFrame with image_file_paths_column containing paths to extracted images (or None if no image for row).
    """
    import os
    import pandas as pd
    import openpyxl
    from PIL import Image as PILImage
    from io import BytesIO

    # Load DataFrame
    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    if isinstance(df, dict):
        # If multiple sheets, pick the first one
        df = list(df.values())[0]

    # Load workbook and worksheet
    wb = openpyxl.load_workbook(excel_path)
    ws = wb[sheet_name] if sheet_name else wb.active

    # Prepare output directory
    if output_dir is None:
        output_dir = os.path.splitext(excel_path)[0] + '_images'
    os.makedirs(output_dir, exist_ok=True)

    # Check if there are any images in the worksheet
    images = getattr(ws, '_images', [])
    has_images = bool(images)

    # Check if the image column exists
    has_image_column = image_column_name in df.columns

    # Map row index (Excel row) to image file path(s)
    row_to_images = {}
    for idx, image in enumerate(images):
        anchor = getattr(image, 'anchor', None)
        if anchor is not None and hasattr(anchor, '_from'):
            row = anchor._from.row + 1  # openpyxl uses 0-based index
            col = anchor._from.col + 1
            # Save image
            img_path = os.path.join(output_dir, f"row{row}_img{idx+1}.png")
            img_data = image._data()
            img = PILImage.open(BytesIO(img_data))
            img.save(img_path)
            row_to_images.setdefault(row, []).append(img_path)

    # Map DataFrame index to Excel row (assuming header is row 1)
    def get_image_paths_for_row(idx):
        # DataFrame index 0 -> Excel row 2
        excel_row = idx + 2
        return row_to_images.get(excel_row, None)

    # Add/replace the image_file_paths column
    df[image_file_paths_column] = df.index.map(get_image_paths_for_row)

    return df

def extract_price(price_val) -> float:
    """Extract numeric price from various formats"""
    if pd.isna(price_val):
        return 0.0
    
    price_str = str(price_val).replace('$', '').replace(',', '').replace('¥', '').replace('€', '').strip()
    try:
        return float(price_str)
    except:
        return 0.0

def normalize_category(cat_val) -> str:
    """Normalize category to valid values"""
    if pd.isna(cat_val):
        return 'OTHER'
    
    cat_str = str(cat_val).upper().strip()
    valid_cats = ["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "COLLECTIBLES", "FASHION", "CUSTOM", "OTHER"]
    
    if cat_str in valid_cats:
        return cat_str
    else:
        return 'OTHER'

def parse_array_field(field_val) -> List[str]:
    """Parse array-like fields"""
    # Handle None values first
    if field_val is None:
        return []
    
    # Handle pandas Series, numpy arrays safely
    try:
        # Check if it's a scalar NA value
        if pd.api.types.is_scalar(field_val) and pd.isna(field_val):
            return []
    except (ValueError, TypeError):
        # If pd.isna() fails on arrays, continue processing
        pass
    
    # Handle numpy arrays or pandas Series
    if hasattr(field_val, '__iter__') and not isinstance(field_val, str):
        try:
            # Convert to list and check if it's empty
            field_list = list(field_val)
            if len(field_list) == 0:
                return []
            return field_list
        except:
            return []
    
    if isinstance(field_val, list):
        return field_val
    
    field_str = str(field_val).strip()
    if not field_str or field_str.lower() in ['nan', 'none', 'null']:
        return []
        
    if field_str.startswith('[') and field_str.endswith(']'):
        try:
            return json.loads(field_str)
        except:
            # Try converting single quotes to double quotes for Python-style lists
            try:
                fixed_str = field_str.replace("'", '"')
                return json.loads(fixed_str)
            except:
                # Last resort: try using ast.literal_eval for Python-style lists
                try:
                    import ast
                    return ast.literal_eval(field_str)
                except:
                    return []
    else:
        return [item.strip() for item in field_str.split(',') if item.strip()]

def parse_object_field(field_val) -> Dict:
    """Parse object-like fields"""
    if pd.isna(field_val):
        return {}
    
    if isinstance(field_val, dict):
        return field_val
    
    field_str = str(field_val).strip()
    if field_str.startswith('{') and field_str.endswith('}'):
        try:
            return json.loads(field_str)
        except:
            return {}
    
    return {}

def validate_product_row(row_data: Dict[str, Any], row_index: int) -> Dict[str, Any]:
    """Validate and clean a single product row"""
    errors = []
    warnings = []
    cleaned_data = {}
    
    # Required fields validation
    required_fields = ['title', 'description', 'price', 'category']
    for field in required_fields:
        if field not in row_data or not str(row_data[field]).strip():
            errors.append(f"Missing required field: {field}")
        else:
            cleaned_data[field] = str(row_data[field]).strip()
    
    # Price validation
    try:
        if 'price' in row_data:
            price_val = str(row_data['price']).replace('$', '').replace(',', '').strip()
            cleaned_data['price'] = float(price_val)
            if cleaned_data['price'] < 0:
                errors.append("Price must be >= 0")
    except (ValueError, TypeError):
        errors.append("Invalid price format")
    
    # Category validation
    valid_categories = ["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "COLLECTIBLES", "FASHION", "CUSTOM", "OTHER"]
    if 'category' in cleaned_data:
        category_upper = cleaned_data['category'].upper()
        if category_upper not in valid_categories:
            warnings.append(f"Invalid category '{cleaned_data['category']}', defaulting to 'OTHER'")
            cleaned_data['category'] = 'OTHER'
        else:
            cleaned_data['category'] = category_upper
    
    # Quantity validation
    try:
        if 'quantity' in row_data and row_data['quantity']:
            cleaned_data['quantity'] = int(float(str(row_data['quantity'])))
            if cleaned_data['quantity'] < 1:
                errors.append("Quantity must be >= 1")
        else:
            cleaned_data['quantity'] = 1  # Default
    except (ValueError, TypeError):
        warnings.append("Invalid quantity format, defaulting to 1")
        cleaned_data['quantity'] = 1
    
    # Condition validation
    if 'condition' in row_data and row_data['condition']:
        condition_upper = str(row_data['condition']).upper()
        if condition_upper in ['NEW', 'USED']:
            cleaned_data['condition'] = condition_upper
        else:
            warnings.append(f"Invalid condition '{row_data['condition']}', defaulting to 'NEW'")
            cleaned_data['condition'] = 'NEW'
    else:
        cleaned_data['condition'] = 'NEW'
    
    # Optional fields with defaults
    optional_fields = {
        'contact_email': 'seller@example.com',
        'ship_from_country': None,
        'discount_type': None,
        'discount_value': 0.0
    }
    
    for field, default_val in optional_fields.items():
        if field in row_data and row_data[field] and str(row_data[field]).strip():
            cleaned_data[field] = str(row_data[field]).strip()
        else:
            if default_val is not None:
                cleaned_data[field] = default_val
    
    # Handle arrays and objects (tags, specifications, etc.)
    array_fields = ['tags', 'payment_options', 'ship_to_countries', 'image_file_paths']
    for field in array_fields:
        if field in row_data and row_data[field]:
            try:
                if isinstance(row_data[field], str):
                    # Try to parse as JSON first
                    if row_data[field].strip().startswith('['):
                        cleaned_data[field] = json.loads(row_data[field])
                    else:
                        # Split by comma
                        cleaned_data[field] = [item.strip() for item in str(row_data[field]).split(',') if item.strip()]
                elif isinstance(row_data[field], list):
                    cleaned_data[field] = row_data[field]
            except json.JSONDecodeError:
                warnings.append(f"Invalid JSON format for {field}, treating as comma-separated")
                cleaned_data[field] = [item.strip() for item in str(row_data[field]).split(',') if item.strip()]
    
    # Handle specifications
    if 'specifications' in row_data and row_data['specifications']:
        try:
            if isinstance(row_data['specifications'], str):
                cleaned_data['specifications'] = json.loads(row_data['specifications'])
            elif isinstance(row_data['specifications'], dict):
                cleaned_data['specifications'] = row_data['specifications']
        except json.JSONDecodeError:
            warnings.append("Invalid JSON format for specifications, skipping")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'cleaned_data': cleaned_data,
        'row_index': row_index
    }

class DifyParamParser:
    """
    Comprehensive parser for converting Dify's stringified parameters 
    back to proper Python types.
    """
    
    # Valid literal values for validation
    VALID_CATEGORIES = ["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "COLLECTIBLES", "FASHION", "CUSTOM", "OTHER"]
    VALID_CONDITIONS = ["NEW", "USED"]
    VALID_COUNTRIES = ["US", "SG", "HK", "KR", "JP"]
    VALID_PAYMENT_OPTIONS = ["ETH_ETHEREUM", "ETH_BASE", "SOL_SOLANA", "USDC_ETHEREUM", "USDC_BASE", "USDC_SOLANA", "USDT_ETHEREUM"]
    VALID_DISCOUNT_TYPES = ["", "FIXED_AMOUNT", "PERCENTAGE"]
    
    @staticmethod
    def _is_empty_param(param_str: Optional[str]) -> bool:
        """Check if parameter is empty/null"""
        return not param_str or param_str.lower().strip() in ['null', 'none', '', '[]', '{}']
    
    @staticmethod
    def _clean_string(s: str) -> str:
        """Clean string by removing quotes and extra whitespace"""
        return s.strip().strip('"\'').strip()
    
    @staticmethod
    def parse_string_list(param_str: Optional[str], param_name: str = "parameter") -> Optional[List[str]]:
        """
        Parse string to List[str] - handles various formats:
        - JSON array: '["item1", "item2"]'
        - Comma-separated: 'item1,item2,item3'
        - Single item: 'item1'
        """
        if DifyParamParser._is_empty_param(param_str):
            return None
            
        try:
            # Try JSON array format first
            if param_str.strip().startswith('[') and param_str.strip().endswith(']'):
                parsed = json.loads(param_str)
                if not isinstance(parsed, list):
                    raise ValueError(f"Expected list, got {type(parsed)}")
                return [DifyParamParser._clean_string(str(item)) for item in parsed if item]
            
            # Handle comma-separated values
            if ',' in param_str:
                items = []
                for item in param_str.split(','):
                    clean_item = DifyParamParser._clean_string(item)
                    if clean_item:
                        items.append(clean_item)
                return items if items else None
            
            # Single item
            clean_item = DifyParamParser._clean_string(param_str)
            return [clean_item] if clean_item else None
            
        except Exception as e:
            raise ValueError(f"Failed to parse {param_name} as string list: {e}")
    
    @staticmethod
    def parse_variation_data(param_str: Optional[str]) -> Optional[List[VariationData]]:
        """
        Parse string to List[VariationData]
        Expected format: '[{"name": "Size", "values": ["S", "M", "L"]}]'
        """
        if DifyParamParser._is_empty_param(param_str):
            return None
            
        try:
            data = json.loads(param_str)
            
            if not isinstance(data, list):
                raise ValueError(f"Expected list, got {type(data)}")
            
            variations = []
            for item in data:
                if not isinstance(item, dict):
                    raise ValueError(f"Each variation must be an object, got {type(item)}")
                
                # Validate required fields
                if 'name' not in item or 'values' not in item:
                    raise ValueError("Each variation must have 'name' and 'values' fields")
                
                variations.append(VariationData(**item))
            
            return variations if variations else None
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format for variations_data: {e}")
        except ValidationError as e:
            raise ValueError(f"Invalid VariationData format: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse variations_data: {e}")
    
    @staticmethod
    def parse_shipping_price_data(param_str: Optional[str]) -> Optional[List[ShippingPriceData]]:
        """
        Parse string to List[ShippingPriceData]
        Expected format: '[{"country_code": "US", "price": 0.0, "currency_code": "USDT"}]'
        """
        if DifyParamParser._is_empty_param(param_str):
            return None
            
        try:
            data = json.loads(param_str)
            
            if not isinstance(data, list):
                raise ValueError(f"Expected list, got {type(data)}")
            
            shipping_prices = []
            for item in data:
                if not isinstance(item, dict):
                    raise ValueError(f"Each shipping price must be an object, got {type(item)}")
                
                # Validate country code
                if 'country_code' not in item:
                    raise ValueError("Each shipping price must have 'country_code' field")
                
                if item['country_code'] not in DifyParamParser.VALID_COUNTRIES:
                    raise ValueError(f"Invalid country_code: {item['country_code']}. Must be one of {DifyParamParser.VALID_COUNTRIES}")
                
                shipping_prices.append(ShippingPriceData(**item))
            
            return shipping_prices if shipping_prices else None
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format for shipping_prices_data: {e}")
        except ValidationError as e:
            raise ValueError(f"Invalid ShippingPriceData format: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse shipping_prices_data: {e}")
    
    @staticmethod
    def parse_specifications(param_str: Optional[str]) -> Optional[Dict[str, str]]:
        """
        Parse string to Dict[str, str] for specifications
        Expected format: '{"Brand": "Apple", "Model": "iPhone 15"}'
        """
        if DifyParamParser._is_empty_param(param_str):
            return None
            
        try:
            data = json.loads(param_str)
            
            if not isinstance(data, dict):
                raise ValueError(f"Expected dict, got {type(data)}")
            
            # Convert all values to strings
            specs = {}
            for key, value in data.items():
                specs[str(key)] = str(value)
            
            return specs if specs else None
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format for specifications: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse specifications: {e}")
    
    @staticmethod
    def parse_literal_list(param_str: Optional[str], valid_values: List[str], param_name: str) -> Optional[List[str]]:
        """
        Parse string to List[Literal] with validation
        For parameters like ship_to_countries, payment_options
        """
        parsed_list = DifyParamParser.parse_string_list(param_str, param_name)
        
        if not parsed_list:
            return None
        
        # Validate each value against allowed literals
        validated_list = []
        for item in parsed_list:
            if item not in valid_values:
                raise ValueError(f"Invalid {param_name} value: '{item}'. Must be one of {valid_values}")
            validated_list.append(item)
        
        return validated_list if validated_list else None
    
    @staticmethod
    def parse_tags(param_str: Optional[str]) -> Optional[List[str]]:
        """Parse tags - wrapper for string list parsing"""
        return DifyParamParser.parse_string_list(param_str, "tags")
    
    @staticmethod
    def parse_image_file_paths(param_str: Optional[str]) -> Optional[List[str]]:
        """Parse image file paths - wrapper for string list parsing"""
        return DifyParamParser.parse_string_list(param_str, "image_file_paths")
    
    @staticmethod
    def parse_ship_to_countries(param_str: Optional[str]) -> Optional[List[str]]:
        """Parse ship_to_countries with country validation"""
        return DifyParamParser.parse_literal_list(param_str, DifyParamParser.VALID_COUNTRIES, "ship_to_countries")
    
    @staticmethod
    def parse_payment_options(param_str: Optional[str]) -> Optional[List[str]]:
        """Parse payment_options with validation"""
        return DifyParamParser.parse_literal_list(param_str, DifyParamParser.VALID_PAYMENT_OPTIONS, "payment_options")