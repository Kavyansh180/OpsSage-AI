from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, status
from pymongo.asynchronous.database import AsyncDatabase

from backend.app.core.dependencies import get_current_user, get_db, require_role
from backend.app.core.exceptions import ResourceNotFoundError
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.knowledge import (
    KnowledgeDocumentResponse,
    KnowledgeIndexRequest,
    KnowledgeIndexResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from backend.app.services.knowledge_indexer import KnowledgeIndexer
from backend.app.services.knowledge_retriever import KnowledgeRetrievalService

router = APIRouter(prefix="/knowledge", tags=["Historical Incident Knowledge & RAG"])


@router.post(
    "/search",
    response_model=KnowledgeSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic similarity search over historical incidents",
)
async def search_knowledge(
    payload: KnowledgeSearchRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
) -> KnowledgeSearchResponse:
    """
    Performs semantic vector search against historical incidents in the knowledge base.
    Guarantees tenant isolation: non-admins only see their own tenant's knowledge records.
    """
    retrieval_service = KnowledgeRetrievalService(db=db)

    # Determine query string
    query_text = payload.query
    incident_context = None

    if payload.incident_id:
        inc_query = {"incident_id": payload.incident_id}
        if ObjectId.is_valid(payload.incident_id):
            inc_query = {"$or": [{"incident_id": payload.incident_id}, {"_id": ObjectId(payload.incident_id)}]}

        inc_doc = await db["incidents"].find_one(inc_query)
        if not inc_doc:
            raise ResourceNotFoundError(f"Incident '{payload.incident_id}' not found.")
        if current_user.role != UserRole.ADMIN and inc_doc.get("user_id") != current_user.id:
            raise ResourceNotFoundError(f"Incident '{payload.incident_id}' not found.")
        incident_context = inc_doc
        if not query_text:
            query_text = retrieval_service.build_query_text(inc_doc)

    if not query_text:
        query_text = ""

    # Generate query embedding
    query_vector = retrieval_service._embedder.generate_embedding(query_text)

    try:
        results = await retrieval_service._search_atlas_vector_search(
            query_vector=query_vector,
            user=current_user,
            service_name=payload.service_name,
            environment=payload.environment,
            top_k=payload.top_k or 5,
            min_similarity=payload.min_similarity if payload.min_similarity is not None else 0.65,
        )
    except Exception:
        # Fallback to in-memory search if Atlas Vector Search is not enabled on this cluster
        results = await retrieval_service._search_in_memory_fallback(
            query_vector=query_vector,
            user=current_user,
            service_name=payload.service_name,
            environment=payload.environment,
            top_k=payload.top_k or 5,
            min_similarity=payload.min_similarity if payload.min_similarity is not None else 0.65,
        )

    # Map to SimilarIncidentReference
    similar_refs = []
    for doc in results:
        hist = doc.get("historical_analysis") or {}
        similar_refs.append({
            "knowledge_id": doc.get("knowledge_id", ""),
            "source_incident_id": doc.get("source_incident_id", ""),
            "similarity_score": round(float(doc.get("score", 0.0)), 4),
            "service_name": doc.get("service_name", ""),
            "environment": doc.get("environment", ""),
            "title": doc.get("title", ""),
            "has_verified_resolution": bool(doc.get("has_verified_resolution", False)),
            "confirmed_resolution": doc.get("confirmed_resolution"),
            "probable_root_cause": hist.get("probable_root_cause"),
        })

    return KnowledgeSearchResponse(
        query_text=query_text,
        total_found=len(similar_refs),
        results=similar_refs,
    )


@router.post(
    "/index",
    response_model=KnowledgeIndexResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch index historical incidents into knowledge base",
)
async def index_historical_incidents(
    payload: Optional[KnowledgeIndexRequest] = None,
    current_user: UserInDB = Depends(require_role(UserRole.ADMIN, UserRole.ENGINEER)),
    db: AsyncDatabase = Depends(get_db),
) -> KnowledgeIndexResponse:
    """
    Scans historical incidents and indexes them into the knowledge base.
    Restricted to ADMIN and ENGINEER roles. Viewers are blocked.
    """
    req = payload or KnowledgeIndexRequest()
    indexer = KnowledgeIndexer(db=db)
    return await indexer.index_incidents_batch(
        user=current_user,
        limit=req.limit,
        service_name=req.service_name,
        environment=req.environment,
        force_reindex=req.force_reindex,
    )


@router.post(
    "/index/{incident_id}",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Index an individual incident into the knowledge base",
)
async def index_single_incident(
    incident_id: str,
    force_reindex: bool = False,
    current_user: UserInDB = Depends(require_role(UserRole.ADMIN, UserRole.ENGINEER)),
    db: AsyncDatabase = Depends(get_db),
) -> KnowledgeDocumentResponse:
    """
    Builds, embeds, and indexes an individual incident.
    Restricted to ADMIN and ENGINEER roles.
    """
    indexer = KnowledgeIndexer(db=db)
    doc = await indexer.index_incident(
        incident_id=incident_id,
        user=current_user,
        force_reindex=force_reindex,
    )
    return KnowledgeDocumentResponse.model_validate(doc)


@router.get(
    "/{knowledge_id}",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a knowledge base document by its knowledge ID",
)
async def get_knowledge_document(
    knowledge_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
) -> KnowledgeDocumentResponse:
    """
    Retrieves a single knowledge base document.
    Enforces tenant isolation: users can only view their own knowledge records.
    The raw vector embedding is omitted from the public response.
    """
    kb_col = db["knowledge_base"]
    query = {"knowledge_id": knowledge_id}
    if ObjectId.is_valid(knowledge_id):
        query = {"$or": [{"knowledge_id": knowledge_id}, {"_id": ObjectId(knowledge_id)}]}

    doc = await kb_col.find_one(query)
    if not doc:
        raise ResourceNotFoundError(f"Knowledge document '{knowledge_id}' not found.")

    if current_user.role != UserRole.ADMIN and doc.get("user_id") != current_user.id:
        raise ResourceNotFoundError(f"Knowledge document '{knowledge_id}' not found.")

    return KnowledgeDocumentResponse.model_validate(doc)
