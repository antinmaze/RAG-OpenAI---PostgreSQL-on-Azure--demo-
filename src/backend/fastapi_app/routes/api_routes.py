import json
import logging
from collections.abc import AsyncGenerator
from typing import Union

import fastapi
import numpy as np
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from openai import APIError
from sqlalchemy import select, text

from fastapi_app.api_models import (
    ChatRequest,
    ErrorResponse,
    ItemCreate,
    ItemPublic,
    ItemWithDistance,
    RetrievalResponse,
    RetrievalResponseDelta,
    ItemUpdate,
)
from fastapi_app.dependencies import ChatClient, CommonDeps, DBSession, EmbeddingsClient
from fastapi_app.embeddings import compute_text_embedding
from fastapi_app.postgres_models import Item
from fastapi_app.postgres_searcher import PostgresSearcher
from fastapi_app.rag_advanced import AdvancedRAGChat
from fastapi_app.rag_simple import SimpleRAGChat

router = fastapi.APIRouter()


ERROR_FILTER = {"error": "Your message contains content that was flagged by the content filter."}


async def format_as_ndjson(r: AsyncGenerator[RetrievalResponseDelta, None]) -> AsyncGenerator[str, None]:
    """
    Format the response as NDJSON
    """
    try:
        async for event in r:
            yield event.model_dump_json() + "\n"
    except Exception as error:
        if isinstance(error, APIError) and error.code == "content_filter":
            yield json.dumps(ERROR_FILTER) + "\n"
        else:
            logging.exception("Exception while generating response stream: %s", error)
            yield json.dumps({"error": str(error)}, ensure_ascii=False) + "\n"


@router.get("/items/{id}", response_model=ItemPublic)
async def item_handler(database_session: DBSession, id: int) -> ItemPublic:
    """A simple API to get an item by ID."""
    item = (await database_session.scalars(select(Item).where(Item.id == id))).first()
    if not item:
        raise HTTPException(detail=f"Item with ID {id} not found.", status_code=404)
    return ItemPublic.model_validate(item.to_dict())


@router.post("/items", response_model=ItemPublic)
async def create_item_handler(
    database_session: DBSession, openai_embed: EmbeddingsClient, item_data: ItemCreate
) -> ItemPublic:
    """Create a new item with embeddings."""
    # Create new item
    new_item = Item(
        type=item_data.type,
        brand=item_data.brand,
        name=item_data.name,
        description=item_data.description,
        price=item_data.price,
        owner=item_data.owner,
    )

    # Add to database first to get the ID
    database_session.add(new_item)
    await database_session.commit()
    await database_session.refresh(new_item)

    try:
        # Create formatted text for embeddings (same format as in recreate_all_embeddings.py)
        text_for_embedding = (
            f"Product: {new_item.name}. "
            f"Type: {new_item.type}. "
            f"Brand/Manufacturer: {new_item.brand}. "
            f"Description: {new_item.description} "
            f"Price: ${new_item.price:.2f}. "
            f"Current Owner: {new_item.owner}."
        )

        # Generate embeddings
        embedding_3l = await compute_text_embedding(
            text_for_embedding,
            openai_embed.client,
            embed_model="text-embedding-3-large",
            embed_deployment=None,
            embedding_dimensions=1024,
        )

        embedding_nomic = await compute_text_embedding(
            text_for_embedding,
            openai_embed.client,
            embed_model="text-embedding-3-small",
            embed_deployment=None,
            embedding_dimensions=1536,
        )

        # Convert to PostgreSQL format
        embedding_3l_array = np.array(embedding_3l, dtype=np.float32)
        embedding_nomic_array = np.array(embedding_nomic, dtype=np.float32)

        # Update the item with embeddings
        await database_session.execute(
            text("""
                UPDATE items
                SET embedding_3l = :embedding_3l,
                    embedding_nomic = :embedding_nomic
                WHERE id = :item_id
            """),
            {
                "embedding_3l": embedding_3l_array.tolist(),
                "embedding_nomic": embedding_nomic_array.tolist(),
                "item_id": new_item.id,
            },
        )
        await database_session.commit()

    except Exception as e:
        logging.warning(f"Failed to generate embeddings for item {new_item.id}: {e}")
        # Item is still created, just without embeddings

    return ItemPublic.model_validate(new_item.to_dict())


@router.get("/similar", response_model=list[ItemWithDistance])
async def similar_handler(
    context: CommonDeps, database_session: DBSession, id: int, n: int = 5
) -> list[ItemWithDistance]:
    """A similarity API to find items similar to items with given ID."""
    item = (await database_session.scalars(select(Item).where(Item.id == id))).first()
    if not item:
        raise HTTPException(detail=f"Item with ID {id} not found.", status_code=404)

    closest = (
        await database_session.execute(
            text(
                f"SELECT *, {context.embedding_column} <=> :embedding as DISTANCE FROM {Item.__tablename__} "
                "WHERE id <> :item_id ORDER BY distance LIMIT :n"
            ),
            {"embedding": getattr(item, context.embedding_column), "n": n, "item_id": id},
        )
    ).fetchall()

    items = [dict(row._mapping) for row in closest]
    return [ItemWithDistance.model_validate(item) for item in items]


@router.patch("/items/{id}", response_model=ItemPublic)
async def update_item_handler(
    id: int, database_session: DBSession, openai_embed: EmbeddingsClient, item_data: ItemUpdate
) -> ItemPublic:
    """Partially update an item and regenerate embeddings.

    If no updatable fields are provided, the existing item is returned unchanged.
    Embeddings are regenerated only if any of the text/value fields affecting semantic meaning changed.
    """
    item = (await database_session.scalars(select(Item).where(Item.id == id))).first()
    if not item:
        raise HTTPException(detail=f"Item with ID {id} not found.", status_code=404)

    # Track whether something changed that should trigger re-embedding
    meaningful_fields = ["type", "brand", "name", "description", "price", "owner"]
    changed = False
    for field in meaningful_fields:
        new_value = getattr(item_data, field)
        if new_value is not None and new_value != getattr(item, field):
            setattr(item, field, new_value)
            changed = True

    await database_session.commit()
    await database_session.refresh(item)

    if changed:
        try:
            # Recreate formatted text consistent with create logic
            text_for_embedding = (
                f"Product: {item.name}. "
                f"Type: {item.type}. "
                f"Brand/Manufacturer: {item.brand}. "
                f"Description: {item.description} "
                f"Price: ${item.price:.2f}. "
                f"Current Owner: {item.owner}."
            )
            embedding_3l = await compute_text_embedding(
                text_for_embedding,
                openai_embed.client,
                embed_model="text-embedding-3-large",
                embed_deployment=None,
                embedding_dimensions=1024,
            )
            embedding_nomic = await compute_text_embedding(
                text_for_embedding,
                openai_embed.client,
                embed_model="text-embedding-3-small",
                embed_deployment=None,
                embedding_dimensions=1536,
            )
            embedding_3l_array = np.array(embedding_3l, dtype=np.float32)
            embedding_nomic_array = np.array(embedding_nomic, dtype=np.float32)
            await database_session.execute(
                text(
                    """
                UPDATE items
                SET embedding_3l = :embedding_3l,
                    embedding_nomic = :embedding_nomic
                WHERE id = :item_id
                """
                ),
                {
                    "embedding_3l": embedding_3l_array.tolist(),
                    "embedding_nomic": embedding_nomic_array.tolist(),
                    "item_id": item.id,
                },
            )
            await database_session.commit()
        except Exception as e:  # pragma: no cover - protective logging
            logging.warning(f"Failed to regenerate embeddings for item {item.id}: {e}")

    return ItemPublic.model_validate(item.to_dict())


@router.get("/search", response_model=list[ItemPublic])
async def search_handler(
    context: CommonDeps,
    database_session: DBSession,
    openai_embed: EmbeddingsClient,
    query: str,
    top: int = 5,
    enable_vector_search: bool = True,
    enable_text_search: bool = True,
) -> list[ItemPublic]:
    """A search API to find items based on a query."""
    searcher = PostgresSearcher(
        db_session=database_session,
        openai_embed_client=openai_embed.client,
        embed_deployment=context.openai_embed_deployment,
        embed_model=context.openai_embed_model,
        embed_dimensions=context.openai_embed_dimensions,
        embedding_column=context.embedding_column,
    )
    results = await searcher.search_and_embed(
        query, top=top, enable_vector_search=enable_vector_search, enable_text_search=enable_text_search
    )
    return [ItemPublic.model_validate(item.to_dict()) for item in results]


@router.post("/chat", response_model=Union[RetrievalResponse, ErrorResponse])
async def chat_handler(
    context: CommonDeps,
    database_session: DBSession,
    openai_embed: EmbeddingsClient,
    openai_chat: ChatClient,
    chat_request: ChatRequest,
):
    try:
        searcher = PostgresSearcher(
            db_session=database_session,
            openai_embed_client=openai_embed.client,
            embed_deployment=context.openai_embed_deployment,
            embed_model=context.openai_embed_model,
            embed_dimensions=context.openai_embed_dimensions,
            embedding_column=context.embedding_column,
        )
        rag_flow: Union[SimpleRAGChat, AdvancedRAGChat]
        if chat_request.context.overrides.use_advanced_flow:
            rag_flow = AdvancedRAGChat(
                messages=chat_request.messages,
                overrides=chat_request.context.overrides,
                searcher=searcher,
                openai_chat_client=openai_chat.client,
                chat_model=context.openai_chat_model,
                chat_deployment=context.openai_chat_deployment,
            )
        else:
            rag_flow = SimpleRAGChat(
                messages=chat_request.messages,
                overrides=chat_request.context.overrides,
                searcher=searcher,
                openai_chat_client=openai_chat.client,
                chat_model=context.openai_chat_model,
                chat_deployment=context.openai_chat_deployment,
            )

        items, thoughts = await rag_flow.prepare_context()
        response = await rag_flow.answer(items=items, earlier_thoughts=thoughts)
        return response
    except Exception as e:
        if isinstance(e, APIError) and e.code == "content_filter":
            return ERROR_FILTER
        else:
            logging.exception("Exception while generating response: %s", e)
            return {"error": str(e)}


@router.post("/chat/stream")
async def chat_stream_handler(
    context: CommonDeps,
    database_session: DBSession,
    openai_embed: EmbeddingsClient,
    openai_chat: ChatClient,
    chat_request: ChatRequest,
):
    searcher = PostgresSearcher(
        db_session=database_session,
        openai_embed_client=openai_embed.client,
        embed_deployment=context.openai_embed_deployment,
        embed_model=context.openai_embed_model,
        embed_dimensions=context.openai_embed_dimensions,
        embedding_column=context.embedding_column,
    )

    rag_flow: Union[SimpleRAGChat, AdvancedRAGChat]
    if chat_request.context.overrides.use_advanced_flow:
        rag_flow = AdvancedRAGChat(
            messages=chat_request.messages,
            overrides=chat_request.context.overrides,
            searcher=searcher,
            openai_chat_client=openai_chat.client,
            chat_model=context.openai_chat_model,
            chat_deployment=context.openai_chat_deployment,
        )
    else:
        rag_flow = SimpleRAGChat(
            messages=chat_request.messages,
            overrides=chat_request.context.overrides,
            searcher=searcher,
            openai_chat_client=openai_chat.client,
            chat_model=context.openai_chat_model,
            chat_deployment=context.openai_chat_deployment,
        )

    try:
        # Intentionally do search we stream down the answer, to avoid using database connections during stream
        # See https://github.com/tiangolo/fastapi/discussions/11321
        items, thoughts = await rag_flow.prepare_context()
        result = rag_flow.answer_stream(items, thoughts)
        return StreamingResponse(content=format_as_ndjson(result), media_type="application/x-ndjson")
    except Exception as e:
        if isinstance(e, APIError) and e.code == "content_filter":
            return StreamingResponse(
                content=json.dumps(ERROR_FILTER) + "\n",
                media_type="application/x-ndjson",
            )
        else:
            logging.exception("Exception while generating response: %s", e)
            return StreamingResponse(
                content=json.dumps({"error": str(e)}, ensure_ascii=False) + "\n",
                media_type="application/x-ndjson",
            )
