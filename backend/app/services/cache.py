from decimal import Decimal
import json
import redis.asyncio as redis
from typing import Dict, Any
import os

# Initialize Redis client (typically configured centrally).
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

async def get_revenue_summary(
    property_id: str,
    tenant_id: str,
) -> Dict[str, Any]:

    cache_key = f"revenue:tenant:{tenant_id}:property:{property_id}"

    cached = await redis_client.get(cache_key)

    if cached:
        return json.loads(cached)

    from app.services.reservations import calculate_total_revenue

    result = await calculate_total_revenue(property_id, tenant_id)

    # Convert Decimal to string for exact JSON representation.
    cache_data = {
        key: str(value) if isinstance(value, Decimal) else value
        for key, value in result.items()
    }

    await redis_client.setex(
        cache_key,
        300,
        json.dumps(cache_data),
    )

    # Return the same structure as a cache hit.
    return cache_data