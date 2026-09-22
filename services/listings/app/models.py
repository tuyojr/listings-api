from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    Boolean,
    DateTime,
    Text,
    Enum as SAEnum,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func
import enum
import uuid


class Base(DeclarativeBase):
    pass


class ListingType(str, enum.Enum):
    HOUSE = "house"
    APARTMENT = "apartment"
    CONDO = "condo"
    TOWNHOUSE = "townhouse"
    LAND = "land"


class PricePeriod(str, enum.Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


def _enum_values(enum_cls):
    """Return the .value of each enum member"""
    return [e.value for e in enum_cls]


class Listing(Base):
    __tablename__ = "listings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    listing_type = Column(
        SAEnum(
            ListingType,
            name="listing_type",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    address = Column(String(500), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    state = Column(String(100), nullable=False)
    postal_code = Column(String(20), nullable=False)
    bedrooms = Column(Integer, nullable=False)
    bathrooms = Column(Numeric(3, 1), nullable=False)
    square_feet = Column(Integer, nullable=True)
    price = Column(Numeric(12, 2), nullable=False)
    price_period = Column(
        SAEnum(
            PricePeriod,
            name="price_period",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    is_available = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_listings_city_type", "city", "listing_type"),
        Index("ix_listings_price", "price"),
        Index("ix_listings_owner", "owner_id"),
    )
