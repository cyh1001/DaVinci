"""
数据模型定义
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Literal, Union
from dataclasses import dataclass


@dataclass
class Variation:
    """Product variation data class"""
    name: str
    values: List[str]


@dataclass
class ShippingPrice:
    """Shipping price data class"""
    country_code: str
    price: float
    currency_code: str = "USDT"


class ProductDraft:
    """产品草稿数据模型"""
    def __init__(self, 
                 draft_id: str = None,
                 user_id: str = "",
                 title: str = "",
                 description: str = "",
                 price: float = 0.0,
                 category: Literal["DIGITAL_GOODS", "DEPIN", "ELECTRONICS", "FASHION", "COLLECTIBLES", "CUSTOM", "OTHER"] = None,
                 condition: Optional[Literal["NEW", "USED"]] = None,
                 variations_data: List[Variation] = None,
                 image_file_paths: List[str] = None,
                 contact_email: str = "",
                 ship_from_country: Optional[Literal["US", "SG", "HK", "KR", "JP"]] = None,
                 ship_to_countries: Optional[List[Literal["US", "SG", "HK", "KR", "JP"]]] = None,
                 shipping_prices_data: List[ShippingPrice] = None,
                 quantity: int = 1,
                 discount_type: Optional[Literal["PERCENTAGE", "FIXED_AMOUNT"]] = None,
                 discount_value: Optional[float] = None,
                 payment_options: List[str] = None,
                 tags: List[str] = None,
                 specifications: Dict[str, Any] = None,
                 created_at: str = None,
                 updated_at: str = None,
                 version: int = 1):
        self.draft_id = draft_id or str(uuid.uuid4())
        self.user_id = user_id
        self.title = title
        self.description = description
        self.price = price
        self.category = category
        self.condition = condition
        self.variations_data = variations_data or []
        self.image_file_paths = image_file_paths or []
        self.contact_email = contact_email
        
        # Digital Goods不需要运输信息
        if category == "DIGITAL_GOODS":
            self.ship_from_country = ""
            self.ship_to_countries = []
            self.shipping_prices_data = []
        else:
            self.ship_from_country = ship_from_country
            self.ship_to_countries = ship_to_countries or []
            self.shipping_prices_data = shipping_prices_data or []
            
        self.quantity = quantity
        self.discount_type = discount_type
        self.discount_value = discount_value
        self.payment_options = payment_options or []
        self.tags = tags or []
        self.specifications = specifications or {}
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()
        self.version = version
    
    def to_dict(self) -> Dict:
        return {
            "draft_id": self.draft_id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "price": self.price,
            "category": self.category,
            "condition": self.condition,
            "variations_data": [vars(v) for v in self.variations_data] if self.variations_data else [],
            "image_file_paths": self.image_file_paths,
            "contact_email": self.contact_email,
            "ship_from_country": self.ship_from_country,
            "ship_to_countries": self.ship_to_countries,
            "shipping_prices_data": [vars(sf) for sf in self.shipping_prices_data] if self.shipping_prices_data else [],
            "quantity": self.quantity,
            "discount_type": self.discount_type,
            "discount_value": self.discount_value,
            "payment_options": self.payment_options,
            "tags": self.tags,
            "specifications": self.specifications,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ProductDraft':
        # Convert variations_data from dict to Variation objects
        variations_data = data.get('variations_data', [])
        if variations_data and isinstance(variations_data[0], dict):
            variations = [Variation(name=v['name'], values=v['values']) for v in variations_data]
            data['variations_data'] = variations
        
        # Convert shipping_prices_data from dict to ShippingPrice objects
        shipping_prices_data = data.get('shipping_prices_data', [])
        if shipping_prices_data and isinstance(shipping_prices_data[0], dict):
            shipping_prices = [
                ShippingPrice(
                    country_code=sf['country_code'],
                    price=sf['price'],
                    currency_code=sf.get('currency_code', 'USDT')
                )
                for sf in shipping_prices_data
            ]
            data['shipping_prices_data'] = shipping_prices
        
        return cls(**data)
    
    def get_variations_data_dict(self) -> List[Dict[str, Any]]:
        """Convert variations_data to dict format for serialization"""
        return [{'name': v.name, 'values': v.values} for v in self.variations_data] if self.variations_data else []
    
    def get_shipping_prices_data_dict(self) -> List[Dict[str, Any]]:
        """Convert shipping_prices_data to dict format for serialization"""
        return [
            {
                'country_code': sf.country_code,
                'price': sf.price,
                'currency_code': sf.currency_code
            }
            for sf in self.shipping_prices_data
        ] if self.shipping_prices_data else []