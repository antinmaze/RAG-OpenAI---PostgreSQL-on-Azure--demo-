import argparse
import asyncio
import logging

from dotenv import load_dotenv
from sqlalchemy import text

from fastapi_app.postgres_engine import create_postgres_engine_from_args, create_postgres_engine_from_env

logger = logging.getLogger("ragapp")


async def add_owner_column(engine):
    """Add owner column to items table if it doesn't exist"""
    async with engine.begin() as conn:
        # Check if owner column already exists
        result = await conn.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'items' AND column_name = 'owner'
            """)
        )

        if result.fetchone() is None:
            logger.info("Adding owner column to items table...")
            await conn.execute(text("ALTER TABLE items ADD COLUMN owner character varying"))

            # Set default value for existing records
            await conn.execute(text("UPDATE items SET owner = 'Unknown' WHERE owner IS NULL"))

            logger.info("Owner column added successfully!")
        else:
            logger.info("Owner column already exists, skipping...")


async def main():
    parser = argparse.ArgumentParser(description="Add owner column to items table")
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

    await add_owner_column(engine)
    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logger.setLevel(logging.INFO)
    load_dotenv(override=True)
    asyncio.run(main())
