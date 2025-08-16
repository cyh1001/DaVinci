from pydantic import BaseModel
from typing import List
from dataclasses import dataclass

class VariationData(BaseModel):
    name: str
    values: List[str]

class ShippingPriceData(BaseModel):
    country_code: str
    price: float
    currency_code: str = "USDT"

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