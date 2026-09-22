from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models import ListingType, PricePeriod


class ListingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    listing_type: ListingType
    address: str = Field(min_length=1, max_length=500)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=1, max_length=20)
    bedrooms: int = Field(ge=0, le=100)
    bathrooms: float = Field(ge=0, le=100)
    square_feet: Optional[int] = Field(None, ge=0, le=1_000_000)
    price: float = Field(gt=0, le=1_000_000_000)
    price_period: PricePeriod


class ListingUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    listing_type: Optional[ListingType] = None
    address: Optional[str] = Field(None, min_length=1, max_length=500)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    state: Optional[str] = Field(None, min_length=1, max_length=100)
    postal_code: Optional[str] = Field(None, min_length=1, max_length=20)
    bedrooms: Optional[int] = Field(None, ge=0, le=100)
    bathrooms: Optional[float] = Field(None, ge=0, le=100)
    square_feet: Optional[int] = Field(None, ge=0, le=1_000_000)
    price: Optional[float] = Field(None, gt=0, le=1_000_000_000)
    price_period: Optional[PricePeriod] = None
    is_available: Optional[bool] = None


class ListingResponse(BaseModel):
    id: UUID
    owner_id: UUID
    title: str
    description: Optional[str]
    listing_type: ListingType
    address: str
    city: str
    state: str
    postal_code: str
    bedrooms: int
    bathrooms: float
    square_feet: Optional[int]
    price: float
    price_period: PricePeriod
    is_available: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
