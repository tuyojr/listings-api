"""initial listings schema with RLS

Revision ID: 0001
Revises:
Create Date: 2026-09-22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "listings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "listing_type",
            sa.Enum(
                "house",
                "apartment",
                "condo",
                "townhouse",
                "land",
                name="listing_type",
            ),
            nullable=False,
        ),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("postal_code", sa.String(20), nullable=False),
        sa.Column("bedrooms", sa.Integer(), nullable=False),
        sa.Column("bathrooms", sa.Numeric(3, 1), nullable=False),
        sa.Column("square_feet", sa.Integer(), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "price_period",
            sa.Enum("monthly", "annual", name="price_period"),
            nullable=False,
        ),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_listings_city", "listings", ["city"])
    op.create_index("ix_listings_owner", "listings", ["owner_id"])
    op.create_index("ix_listings_city_type", "listings", ["city", "listing_type"])
    op.create_index("ix_listings_price", "listings", ["price"])

    # Enable Row Level Security
    op.execute("ALTER TABLE listings ENABLE ROW LEVEL SECURITY;")

    # RLS policies: users can only see/modify their own listings
    op.execute("""
        CREATE POLICY listings_owner_select ON listings
        FOR SELECT
        USING (owner_id = current_setting('app.current_user_id')::uuid);
    """)
    op.execute("""
        CREATE POLICY listings_owner_insert ON listings
        FOR INSERT
        WITH CHECK (owner_id = current_setting('app.current_user_id')::uuid);
    """)
    op.execute("""
        CREATE POLICY listings_owner_update ON listings
        FOR UPDATE
        USING (owner_id = current_setting('app.current_user_id')::uuid)
        WITH CHECK (owner_id = current_setting('app.current_user_id')::uuid);
    """)
    op.execute("""
        CREATE POLICY listings_owner_delete ON listings
        FOR DELETE
        USING (owner_id = current_setting('app.current_user_id')::uuid);
    """)

    # Grant runtime role access to the new table
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'listing_rw') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON listings TO listing_rw;
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS listings_owner_delete ON listings;")
    op.execute("DROP POLICY IF EXISTS listings_owner_update ON listings;")
    op.execute("DROP POLICY IF EXISTS listings_owner_insert ON listings;")
    op.execute("DROP POLICY IF EXISTS listings_owner_select ON listings;")
    op.execute("ALTER TABLE listings DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_listings_price", table_name="listings")
    op.drop_index("ix_listings_city_type", table_name="listings")
    op.drop_index("ix_listings_owner", table_name="listings")
    op.drop_index("ix_listings_city", table_name="listings")
    op.drop_table("listings")
    op.execute("DROP TYPE IF EXISTS listing_type;")
    op.execute("DROP TYPE IF EXISTS price_period;")
