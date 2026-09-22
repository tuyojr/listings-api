from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, set_rls_user
from app.models import Listing
from app.schemas import ListingCreate, ListingResponse, ListingUpdate
from app.security import get_current_user_id

router = APIRouter(prefix="/api/v1/listings", tags=["Listings"])

DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UUID, Depends(get_current_user_id)]


@router.post("", response_model=ListingResponse, status_code=201)
async def create_listing(body: ListingCreate, user_id: CurrentUser, db: DB):
    await set_rls_user(db, user_id)
    listing = Listing(**body.model_dump(), owner_id=user_id)
    db.add(listing)
    await db.commit()
    # No refresh: RETURNING populated created_at/updated_at, and
    # expire_on_commit=False keeps the object state intact.
    return listing


@router.get("", response_model=list[ListingResponse])
async def list_listings(
    user_id: CurrentUser,
    db: DB,
    city: Annotated[str | None, Query(max_length=100)] = None,
    listing_type: Annotated[str | None, Query()] = None,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    await set_rls_user(db, user_id)

    stmt = select(Listing).where(Listing.is_available.is_(True))
    if city:
        stmt = stmt.where(Listing.city.ilike(f"%{city}%"))
    if listing_type:
        stmt = stmt.where(Listing.listing_type == listing_type)
    if min_price is not None:
        stmt = stmt.where(Listing.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Listing.price <= max_price)

    stmt = stmt.order_by(Listing.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(listing_id: UUID, user_id: CurrentUser, db: DB):
    await set_rls_user(db, user_id)
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


@router.patch("/{listing_id}", response_model=ListingResponse)
async def update_listing(
    listing_id: UUID,
    body: ListingUpdate,
    user_id: CurrentUser,
    db: DB,
):
    await set_rls_user(db, user_id)
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(listing, field, value)

    await db.commit()
    return listing


@router.delete("/{listing_id}", status_code=204)
async def delete_listing(listing_id: UUID, user_id: CurrentUser, db: DB):
    await set_rls_user(db, user_id)
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    await db.delete(listing)
    await db.commit()
