import argparse
import asyncio
import logging
import random

from dotenv import load_dotenv
from sqlalchemy import text

from fastapi_app.postgres_engine import create_postgres_engine_from_args, create_postgres_engine_from_env

logger = logging.getLogger("ragapp")

# Liste d'exemples de propriétaires
SAMPLE_OWNERS = [
    "OutdoorGear Inc.",
    "Adventure Equipment Co.",
    "Mountain Sports Ltd.",
    "Hiking Central",
    "Trail Blazers Supply",
    "Nature Explorer",
    "Summit Outfitters",
    "Wilderness Warehouse",
    "Outdoor Living",
    "Explorer's Den",
    "Peak Performance",
    "Adventure Seekers",
    "Mountain View Sports",
    "Trail Master",
    "Outdoor Zone",
]


async def update_owner_data(engine):
    """Update existing items with random owner values"""
    async with engine.begin() as conn:
        # Get all items that have NULL or 'Unknown' owner
        result = await conn.execute(text("SELECT id FROM items WHERE owner IS NULL OR owner = 'Unknown'"))

        item_ids = [row[0] for row in result.fetchall()]

        if not item_ids:
            logger.info("No items need owner updates.")
            return

        logger.info(f"Updating owner for {len(item_ids)} items...")

        # Update each item with a random owner
        for item_id in item_ids:
            random_owner = random.choice(SAMPLE_OWNERS)
            await conn.execute(
                text("UPDATE items SET owner = :owner WHERE id = :id"), {"owner": random_owner, "id": item_id}
            )

        logger.info(f"Successfully updated {len(item_ids)} items with owner information!")


async def main():
    parser = argparse.ArgumentParser(description="Update items with owner information")
    parser.add_argument("--host", type=str, help="Postgres host")
    parser.add_argument("--username", type=str, help="Postgres username")
    parser.add_argument("--password", type=str, help="Postgres password")
    parser.add_argument("--database", type=str, help="Postgres database")
    parser.add_argument("--sslmode", type=str, help="Postgres sslmode")
    parser.add_argument("--tenant-id", type=str, help="Azure tenant ID", default=None)

    # if no args are specified, use environment variables
    args = parser.parse_args()
    if args.host is None:
        from fastapi_app.dependencies import get_azure_credential

        azure_credential = await get_azure_credential()
        engine = await create_postgres_engine_from_env(azure_credential=azure_credential)
    else:
        engine = await create_postgres_engine_from_args(args)

    await update_owner_data(engine)
    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logger.setLevel(logging.INFO)
    load_dotenv(override=True)
    asyncio.run(main())
