from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models import ListingType, PricePeriod


class ListingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    listing_type: ListingType
    address: str = Field(min_length=1, max_length=500)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=1, max_length=20)
    bedrooms: int = Field(ge=0, le=100)
    bathrooms: float = Field(ge=0, le=100)
    square_feet: int | None = Field(None, ge=0, le=1_000_000)
    price: float = Field(gt=0, le=1_000_000_000)
    price_period: PricePeriod


class ListingUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    listing_type: ListingType | None = None
    address: str | None = Field(None, min_length=1, max_length=500)
    city: str | None = Field(None, min_length=1, max_length=100)
    state: str | None = Field(None, min_length=1, max_length=100)
    postal_code: str | None = Field(None, min_length=1, max_length=20)
    bedrooms: int | None = Field(None, ge=0, le=100)
    bathrooms: float | None = Field(None, ge=0, le=100)
    square_feet: int | None = Field(None, ge=0, le=1_000_000)
    price: float | None = Field(None, gt=0, le=1_000_000_000)
    price_period: PricePeriod | None = None
    is_available: bool | None = None


class ListingResponse(BaseModel):
    id: UUID
    owner_id: UUID
    title: str
    description: str | None
    listing_type: ListingType
    address: str
    city: str
    state: str
    postal_code: str
    bedrooms: int
    bathrooms: float
    square_feet: int | None
    price: float
    price_period: PricePeriod
    is_available: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
