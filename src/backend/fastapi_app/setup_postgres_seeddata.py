import argparse
import asyncio
import json
import logging
import os

import sqlalchemy.exc
from dotenv import load_dotenv
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from fastapi_app.postgres_engine import (
    create_postgres_engine_from_args,
    create_postgres_engine_from_env,
)
from fastapi_app.postgres_models import Item

logger = logging.getLogger("ragapp")


async def seed_data(engine):
    # Check if Item table exists
    async with engine.begin() as conn:
        table_name = Item.__tablename__
        result = await conn.execute(
            text(
                f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{table_name}')"  # noqa
            )
        )
        if not result.scalar():
            logger.error(f" {table_name} table does not exist. Please run the database setup script first.")
            return

    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        # Insert the objects from the JSON file into the database
        current_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(current_dir, "seed_data.json")) as f:
            seed_data_objects = json.load(f)
            for seed_data_object in seed_data_objects:
                db_item = await session.execute(select(Item).filter(Item.id == seed_data_object["id"]))
                if db_item.scalars().first():
                    continue
                attrs = {key: value for key, value in seed_data_object.items()}
                # Ensure owner exists (older seed files may not have it)
                if "owner" not in attrs or attrs["owner"] in (None, "null"):
                    attrs["owner"] = "Unknown"
                # Store embeddings as plain Python lists; SQLAlchemy pgvector adapter will coerce
                # Avoid passing raw numpy arrays which asyncpg sees as text parameter and errors.
                attrs["embedding_3l"] = (
                    list(seed_data_object["embedding_3l"]) if seed_data_object.get("embedding_3l") else None
                )
                raw_nomic = seed_data_object.get("embedding_nomic")
                if raw_nomic and len(raw_nomic) not in (1536,):
                    # Legacy dimension (e.g., 768). Skip so it can be regenerated later.
                    attrs["embedding_nomic"] = None
                else:
                    attrs["embedding_nomic"] = list(raw_nomic) if raw_nomic else None
                column_names = ", ".join(attrs.keys())
                values = ", ".join([f":{key}" for key in attrs.keys()])
                await session.execute(text(f"INSERT INTO {table_name} ({column_names}) VALUES ({values})"), attrs)
            try:
                await session.commit()
            except sqlalchemy.exc.IntegrityError:
                pass

    # Ensure sequence is advanced to avoid duplicate key errors when future inserts omit ID
    async with engine.begin() as conn:
        try:
            # Directly interpolate table name (trusted internal constant)
            # pg_get_serial_sequence requires the relation name literal
            await conn.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table_name}), 1), true)"
                )
            )
        except Exception as e:  # pragma: no cover
            logger.warning(f"Could not advance sequence for {table_name}: {e}")

    logger.info(f"{table_name} table seeded successfully.")


async def main():
    parser = argparse.ArgumentParser(description="Create database schema")
    parser.add_argument("--host", type=str, help="Postgres host")
    parser.add_argument("--username", type=str, help="Postgres username")
    parser.add_argument("--password", type=str, help="Postgres password")
    parser.add_argument("--database", type=str, help="Postgres database")
    parser.add_argument("--sslmode", type=str, help="Postgres sslmode")
    parser.add_argument("--tenant-id", type=str, help="Azure tenant ID", default=None)

    # if no args are specified, use environment variables
    args = parser.parse_args()
    if args.host is None:
        engine = await create_postgres_engine_from_env()
    else:
        engine = await create_postgres_engine_from_args(args)

    await seed_data(engine)

    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logger.setLevel(logging.INFO)
    load_dotenv(override=True)
    asyncio.run(main())
