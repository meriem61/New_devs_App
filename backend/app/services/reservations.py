from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List

from app.core.database_pool import db_pool
from sqlalchemy import text
from zoneinfo import ZoneInfo


async def calculate_monthly_revenue(
    property_id: str,
    tenant_id: str,
    month: int,
    year: int,
) -> Decimal:

    if not db_pool.session_factory:
        await db_pool.initialize()

    async with db_pool.get_session() as session:

        # 1. Find the property's timezone.
        result = await session.execute(
            text("""
                SELECT timezone
                FROM properties
                WHERE id = :property_id
                  AND tenant_id = :tenant_id
            """),
            {
                "property_id": property_id,
                "tenant_id": tenant_id,
            },
        )

        timezone_name = result.scalar_one_or_none()

        if timezone_name is None:
            raise ValueError("Property not found for this tenant")

        # 2. Calculate the beginning and end of the month
        # in the property's local timezone.
        local_timezone = ZoneInfo(timezone_name)

        start_local = datetime(
            year, month, 1,
            tzinfo=local_timezone,
        )

        if month == 12:
            end_local = datetime(
                year + 1, 1, 1,
                tzinfo=local_timezone,
            )
        else:
            end_local = datetime(
                year, month + 1, 1,
                tzinfo=local_timezone,
            )

        # 3. Convert those boundaries to UTC.
        start_utc = start_local.astimezone(ZoneInfo("UTC"))
        end_utc = end_local.astimezone(ZoneInfo("UTC"))

        # 4. Calculate revenue from reservations.
        result = await session.execute(
            text("""
                SELECT COALESCE(SUM(total_amount), 0)
                FROM reservations
                WHERE property_id = :property_id
                  AND tenant_id = :tenant_id
                  AND check_in_date >= :start_date
                  AND check_in_date < :end_date
            """),
            {
                "property_id": property_id,
                "tenant_id": tenant_id,
                "start_date": start_utc,
                "end_date": end_utc,
            },
        )

        total = result.scalar_one()

        return Decimal(str(total))


async def calculate_total_revenue(
    property_id: str,
    tenant_id: str,
):
    if not db_pool.session_factory:
        await db_pool.initialize()

    async with db_pool.get_session() as session:
        result = await session.execute(
            text("""
                SELECT
                    COALESCE(SUM(total_amount), 0) AS total_revenue,
                    COUNT(*) AS reservation_count,
                    COUNT(DISTINCT currency) AS currency_count,
                    MIN(currency) AS currency
                FROM reservations
                WHERE property_id = :property_id
                  AND tenant_id = :tenant_id
            """),
            {
                "property_id": property_id,
                "tenant_id": tenant_id,
            },
        )

        row = result.mappings().one()

        # Never combine amounts from different currencies.
        if row["currency_count"] > 1:
            raise ValueError(
                "Cannot calculate a single revenue total for multiple currencies"
            )

        return {
            "property_id": property_id,
            "total": Decimal(str(row["total_revenue"])),
            "currency": row["currency"],
            "count": row["reservation_count"],
        }