"""
数据模型定义
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Literal, Union


class ProductDraft:
    """产品草稿数据模型"""
    def __init__(self, 
                 draft_id: str = None,
                 user_id: str = "",
                 title: str = "",
                 description: str = "",
                 price: float = 0.0,
                 category: str = "",
                 condition: str = "New",
                 variations: Dict[str, List[str]] = None,
                 images: List[str] = None,
                 contact_email: str = "",
                 ship_from: str = "",
                 ship_to: List[str] = None,
                 shipping_fees: Dict[str, float] = None,
                 quantity: int = 1,
                 discount_type: str = "",
                 discount_value: float = 0.0,
                 payout_methods: List[str] = None,
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
        self.variations = variations or {}
        self.images = images or []
        self.contact_email = contact_email
        
        # Digital Goods不需要运输信息
        if category == "Digital Goods":
            self.ship_from = ""
            self.ship_to = []
            self.shipping_fees = {}
        else:
            self.ship_from = ship_from
            self.ship_to = ship_to or []
            self.shipping_fees = shipping_fees or {}
            
        self.quantity = quantity
        self.discount_type = discount_type
        self.discount_value = discount_value
        self.payout_methods = payout_methods or []
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
            "variations": self.variations,
            "images": self.images,
            "contact_email": self.contact_email,
            "ship_from": self.ship_from,
            "ship_to": self.ship_to,
            "shipping_fees": self.shipping_fees,
            "quantity": self.quantity,
            "discount_type": self.discount_type,
            "discount_value": self.discount_value,
            "payout_methods": self.payout_methods,
            "tags": self.tags,
            "specifications": self.specifications,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ProductDraft':
        return cls(**data)