"""
Knowledge Base Service - Vectorización y gestión de assets.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AssetType
from app.models.knowledge_asset import KnowledgeAsset
from app.services.ai_engine import AIEngineConfig

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024

ALLOWED_MIME_TYPES: dict[str, AssetType] = {
    "text/plain": AssetType.TEXT,
    "application/pdf": AssetType.PDF,
    "image/jpeg": AssetType.IMAGE,
    "image/png": AssetType.IMAGE,
    "image/gif": AssetType.IMAGE,
    "video/mp4": AssetType.VIDEO,
    "video/quicktime": AssetType.VIDEO,
    "audio/mpeg": AssetType.AUDIO,
    "audio/wav": AssetType.AUDIO,
    "audio/ogg": AssetType.AUDIO,
}


class KnowledgeServiceError(Exception):
    """Base exception for knowledge service."""
    pass


class FileTooLargeError(KnowledgeServiceError):
    """Raised when file exceeds size limit."""
    pass


class UnsupportedFileTypeError(KnowledgeServiceError):
    """Raised when file type is not supported."""
    pass


def get_asset_type_from_mime(mime_type: str) -> AssetType:
    """Get AssetType from MIME type string."""
    return ALLOWED_MIME_TYPES.get(mime_type.lower())


async def create_text_asset(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    title: str,
    description: str | None = None,
    content: str,
) -> KnowledgeAsset:
    """
    Create a text knowledge asset and vectorize it.
    """
    asset = KnowledgeAsset(
        id=uuid4(),
        tenant_id=tenant_id,
        asset_type=AssetType.TEXT,
        title=title,
        description=description,
        content=content,
        is_vectorized=False,
        mime_type="text/plain",
    )
    session.add(asset)
    await session.flush()
    await session.refresh(asset)
    return asset


async def upload_file_asset(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    file_content: bytes,
    file_name: str,
    mime_type: str,
    title: str,
    description: str | None = None,
) -> KnowledgeAsset:
    """
    Process a file upload and create a knowledge asset.
    """
    if len(file_content) > MAX_FILE_SIZE:
        raise FileTooLargeError(f"File exceeds maximum size of {MAX_FILE_SIZE} bytes")

    asset_type = get_asset_type_from_mime(mime_type)
    if asset_type is None:
        raise UnsupportedFileTypeError(f"MIME type {mime_type} is not supported")

    file_url = f"/knowledge/files/{uuid4()}/{file_name}"

    asset = KnowledgeAsset(
        id=uuid4(),
        tenant_id=tenant_id,
        asset_type=asset_type,
        title=title,
        description=description,
        file_name=file_name,
        file_url=file_url,
        file_size=len(file_content),
        mime_type=mime_type,
        is_vectorized=False,
    )

    if asset_type == AssetType.TEXT:
        asset.content = file_content.decode("utf-8", errors="replace")

    session.add(asset)
    await session.flush()
    await session.refresh(asset)

    return asset


async def process_asset(
    session: AsyncSession,
    asset_id: UUID,
) -> bool:
    """
    Vectorize a knowledge asset based on its type.
    """
    result = await session.execute(
        select(KnowledgeAsset).where(KnowledgeAsset.id == asset_id)
    )
    asset = result.scalar_one_or_none()

    if not asset:
        raise KnowledgeServiceError(f"Asset {asset_id} not found")

    if asset.is_vectorized:
        logger.info(f"Asset {asset_id} already vectorized, skipping")
        return True

    try:
        if asset.asset_type == AssetType.TEXT and asset.content:
            chunks = _split_text_chunks(asset.content)
            await _vectorize_text_chunks(session, asset, chunks)

        elif asset.asset_type == AssetType.PDF:
            chunks = await _extract_pdf_chunks(asset.file_url)
            await _vectorize_text_chunks(session, asset, chunks)

        else:
            await _vectorize_metadata_only(session, asset)

        asset.is_vectorized = True
        await session.flush()
        logger.info(f"Asset {asset_id} vectorized successfully")
        return True

    except Exception as e:
        logger.exception(f"Failed to vectorize asset {asset_id}: {e}")
        raise KnowledgeServiceError(f"Vectorization failed: {e}") from e


def _split_text_chunks(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into chunks using RecursiveCharacterTextSplitter."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
    )
    return splitter.split_text(text)


async def _extract_pdf_chunks(file_url: str) -> list[str]:
    """Extract text from PDF and split into chunks."""
    try:
        from langchain_community.document_loaders import PyPDFLoader
    except ImportError:
        raise KnowledgeServiceError("langchain_community required for PDF processing")

    if not file_url:
        return []

    file_path = file_url.replace("/knowledge/files/", "")
    if not os.path.isabs(file_path):
        file_path = os.path.join("./knowledge_files", os.path.basename(file_path))

    if not os.path.exists(file_path):
        logger.warning(f"PDF file not found: {file_path}")
        return []

    loader = PyPDFLoader(file_path)
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=len,
    )
    chunks = splitter.split_documents(docs)

    return [doc.page_content for doc in chunks]


async def _vectorize_text_chunks(
    session: AsyncSession,
    asset: KnowledgeAsset,
    chunks: list[str],
) -> list[str]:
    """Vectorize text chunks and store in Qdrant."""
    config = AIEngineConfig()
    vector_ids: list[str] = []

    if not chunks:
        return vector_ids

    try:
        embeddings = OllamaEmbeddings(
            model=config.ollama_embedding_model,
            base_url=config.ollama_base_url,
        )
    except Exception as e:
        logger.warning(f"Ollama not available, using Qdrant cloud inference: {e}")
        embeddings = None

    qdrant = AsyncQdrantClient(
        url=config.qdrant_url,
        api_key=config.qdrant_api_key,
    )

    await _ensure_collection_exists(qdrant, config.qdrant_collection)

    metadata = {
        "tenant_id": str(asset.tenant_id),
        "asset_id": str(asset.id),
        "title": asset.title,
        "description": asset.description or "",
        "asset_type": asset.asset_type.value,
        "file_url": asset.file_url or "",
        "created_at": asset.created_at.isoformat() if asset.created_at else "",
    }

    try:
        for i, chunk in enumerate(chunks):
            point_id = str(uuid4())
            vector_ids.append(point_id)

            if embeddings:
                try:
                    vector = await embeddings.aembed_query(chunk)
                except Exception:
                    logger.debug("Falling back to Qdrant cloud inference")
                    vector_result = await qdrant.query_points(
                        collection_name=config.qdrant_collection,
                        query=qdrant_models.Document(
                            text=chunk,
                            model=config.qdrant_embedding_model,
                        ),
                        limit=1,
                        with_payload=False,
                    )
                    if vector_result.points:
                        vector = list(vector_result.points[0].vector)
                    else:
                        vector = [0.0] * 384
            else:
                vector_result = await qdrant.query_points(
                    collection_name=config.qdrant_collection,
                    query=qdrant_models.Document(
                        text=chunk,
                        model=config.qdrant_embedding_model,
                    ),
                    limit=1,
                    with_payload=False,
                )
                if vector_result.points:
                    vector = list(vector_result.points[0].vector)
                else:
                    vector = [0.0] * 384

            await qdrant.upsert(
                collection_name=config.qdrant_collection,
                points=[
                    qdrant_models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "text": chunk,
                            **metadata,
                        },
                    )
                ],
            )

        logger.info(f"Vectorized {len(chunks)} chunks for asset {asset.id}")
        return vector_ids

    except Exception as e:
        logger.exception(f"Failed to upsert to Qdrant: {e}")
        raise KnowledgeServiceError(f"Qdrant upsert failed: {e}") from e


async def _vectorize_metadata_only(
    session: AsyncSession,
    asset: KnowledgeAsset,
) -> str:
    """Vectorize only title and description for multimedia assets."""
    config = AIEngineConfig()
    vector_id = str(uuid4())

    text_to_vectorize = f"{asset.title}. {asset.description or ''}"

    try:
        embeddings = OllamaEmbeddings(
            model=config.ollama_embedding_model,
            base_url=config.ollama_base_url,
        )
        vector = await embeddings.aembed_query(text_to_vectorize)
    except Exception:
        logger.debug("Falling back to Qdrant cloud inference")
        qdrant = AsyncQdrantClient(
            url=config.qdrant_url,
            api_key=config.qdrant_api_key,
        )
        await _ensure_collection_exists(qdrant, config.qdrant_collection)

        vector_result = await qdrant.query_points(
            collection_name=config.qdrant_collection,
            query=qdrant_models.Document(
                text=text_to_vectorize,
                model=config.qdrant_embedding_model,
            ),
            limit=1,
            with_payload=False,
        )
        if vector_result.points:
            vector = list(vector_result.points[0].vector)
        else:
            vector = [0.0] * 384

    metadata = {
        "tenant_id": str(asset.tenant_id),
        "asset_id": str(asset.id),
        "title": asset.title,
        "description": asset.description or "",
        "asset_type": asset.asset_type.value,
        "file_url": asset.file_url or "",
        "payload": json.dumps(asset.payload) if asset.payload else "{}",
        "created_at": asset.created_at.isoformat() if asset.created_at else "",
    }

    qdrant = AsyncQdrantClient(
        url=config.qdrant_url,
        api_key=config.qdrant_api_key,
    )

    await _ensure_collection_exists(qdrant, config.qdrant_collection)

    await qdrant.upsert(
        collection_name=config.qdrant_collection,
        points=[
            qdrant_models.PointStruct(
                id=vector_id,
                vector=vector,
                payload=metadata,
            )
        ],
    )

    logger.info(f"Vectorized metadata for asset {asset.id}")
    return vector_id


async def _ensure_collection_exists(client: AsyncQdrantClient, collection_name: str) -> None:
    """Ensure Qdrant collection exists with proper configuration."""
    try:
        collections = await client.get_collections()
        exists = any(c.name == collection_name for c in collections.collections)
        if not exists:
            await client.create_collection(
                collection_name=collection_name,
                vectors_config=qdrant_models.VectorParams(
                    size=384,
                    distance=qdrant_models.Distance.COSINE,
                ),
            )
            logger.info(f"Created Qdrant collection: {collection_name}")
    except Exception as e:
        logger.debug(f"Collection might already exist: {e}")


async def delete_asset_vectors(
    session: AsyncSession,
    asset_id: UUID,
    tenant_id: UUID,
) -> bool:
    """Delete all vectors associated with an asset from Qdrant."""
    config = AIEngineConfig()

    try:
        qdrant = AsyncQdrantClient(
            url=config.qdrant_url,
            api_key=config.qdrant_api_key,
        )

        filter_condition = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="asset_id",
                    match=qdrant_models.MatchValue(value=str(asset_id)),
                ),
                qdrant_models.FieldCondition(
                    key="tenant_id",
                    match=qdrant_models.MatchValue(value=str(tenant_id)),
                ),
            ]
        )

        await qdrant.delete(
            collection_name=config.qdrant_collection,
            points_selector=qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="asset_id",
                        match=qdrant_models.MatchValue(value=str(asset_id)),
                    )
                ]
            ),
        )

        logger.info(f"Deleted vectors for asset {asset_id}")
        return True

    except Exception as e:
        logger.warning(f"Failed to delete vectors from Qdrant: {e}")
        return False


async def get_asset(session: AsyncSession, asset_id: UUID) -> KnowledgeAsset | None:
    """Get a knowledge asset by ID."""
    result = await session.execute(
        select(KnowledgeAsset).where(KnowledgeAsset.id == asset_id)
    )
    return result.scalar_one_or_none()


async def list_assets(
    session: AsyncSession,
    tenant_id: UUID,
    asset_type: AssetType | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[KnowledgeAsset], int]:
    """List knowledge assets for a tenant."""
    query = select(KnowledgeAsset).where(KnowledgeAsset.tenant_id == tenant_id)

    if asset_type:
        query = query.where(KnowledgeAsset.asset_type == asset_type)

    count_result = await session.execute(
        select(KnowledgeAsset.id).where(KnowledgeAsset.tenant_id == tenant_id)
    )
    total = len(count_result.all())

    query = query.order_by(KnowledgeAsset.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(query)
    assets = list(result.scalars().all())

    return assets, total


async def delete_asset(session: AsyncSession, asset_id: UUID, tenant_id: UUID) -> bool:
    """Delete a knowledge asset and its vectors."""
    asset = await get_asset(session, asset_id)
    if not asset or asset.tenant_id != tenant_id:
        return False

    await delete_asset_vectors(session, asset_id, tenant_id)

    await session.delete(asset)
    await session.flush()

    logger.info(f"Deleted asset {asset_id}")
    return True


async def search_knowledge(
    session: AsyncSession,
    tenant_id: UUID,
    query: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Search knowledge base for a tenant.
    Returns relevant chunks with metadata.
    """
    config = AIEngineConfig()

    try:
        embeddings = OllamaEmbeddings(
            model=config.ollama_embedding_model,
            base_url=config.ollama_base_url,
        )
        vector = await embeddings.aembed_query(query)
    except Exception:
        logger.debug("Falling back to Qdrant cloud inference for search")
        vector = None

    qdrant = AsyncQdrantClient(
        url=config.qdrant_url,
        api_key=config.qdrant_api_key,
    )

    tenant_filter = qdrant_models.Filter(
        must=[
            qdrant_models.FieldCondition(
                key="tenant_id",
                match=qdrant_models.MatchValue(value=str(tenant_id)),
            )
        ]
    )

    try:
        if vector:
            result = await qdrant.search(
                collection_name=config.qdrant_collection,
                query_vector=vector,
                query_filter=tenant_filter,
                limit=limit,
                with_payload=True,
            )
        else:
            result = await qdrant.query_points(
                collection_name=config.qdrant_collection,
                query=qdrant_models.Document(
                    text=query,
                    model=config.qdrant_embedding_model,
                ),
                query_filter=tenant_filter,
                limit=limit,
                with_payload=True,
            )

        results = []
        for point in result.points:
            payload = point.payload or {}
            results.append({
                "text": payload.get("text", payload.get("title", "")),
                "title": payload.get("title", ""),
                "description": payload.get("description", ""),
                "file_url": payload.get("file_url", ""),
                "asset_type": payload.get("asset_type", ""),
                "score": getattr(point, "score", 1.0),
            })

        return results

    except Exception as e:
        logger.warning(f"Search failed: {e}")
        return []