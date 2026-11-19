from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import math
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import OperationFailure

from backend.app.config import Settings, get_settings
from backend.app.core.logging import get_logger
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.knowledge import SimilarIncidentReference
from backend.app.services.embedding_service import EmbeddingService
from backend.app.services.redactor import SecretRedactor

logger = get_logger("services.knowledge_retriever")


@dataclass
class RAGRetrievalResult:
    """
    Encapsulates the result of semantic historical incident retrieval.
    """
    status: str  # "SUCCESS" | "EMPTY" | "UNAVAILABLE" | "DISABLED"
    similar_incidents: List[SimilarIncidentReference]
    records: List[Dict[str, Any]]
    error_message: Optional[str] = None
    retrieval_method: str = "NONE"  # "ATLAS_VECTOR_SEARCH" | "IN_MEMORY_FALLBACK" | "NONE"


class KnowledgeRetrievalService:
    """
    Executes semantic similarity search over historical incidents using MongoDB Atlas Vector Search.
    Guarantees tenant isolation, metadata filtering, similarity threshold enforcement,
    and safe fallback if the search index is unconfigured.
    """

    def __init__(
        self,
        db: AsyncDatabase,
        embedding_service: Optional[EmbeddingService] = None,
        settings: Optional[Settings] = None,
        allow_in_memory_fallback: bool = False,
    ):
        self._db = db
        self._settings = settings or get_settings()
        self._embedder = embedding_service or EmbeddingService(self._settings)
        self._allow_in_memory_fallback = allow_in_memory_fallback

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculates cosine similarity between two numeric vectors."""
        if len(vec1) != len(vec2) or not vec1:
            return 0.0
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        return max(0.0, min(1.0, dot / (norm1 * norm2)))

    def build_query_text(
        self,
        incident: Dict[str, Any],
        logs: Optional[List[Dict[str, Any]]] = None,
        additional_context: Optional[str] = None,
    ) -> str:
        """
        Constructs a ground-truth search query from the current incident metadata and logs.
        """
        parts = [
            f"Service: {incident.get('service_name', '')}",
            f"Environment: {incident.get('environment', '')}",
            f"Incident: {incident.get('title', '')}",
        ]

        if logs:
            top_messages = [l.get("message", "") for l in logs[:3] if l.get("message")]
            if top_messages:
                parts.append("Diagnostics: " + " ; ".join(top_messages))

        if additional_context:
            parts.append(f"Context: {additional_context.strip()}")

        raw = " | ".join(parts)
        return SecretRedactor.redact_text(raw)

    async def _search_atlas_vector_search(
        self,
        query_vector: List[float],
        user: UserInDB,
        service_name: Optional[str] = None,
        environment: Optional[str] = None,
        top_k: int = 3,
        min_similarity: float = 0.65,
    ) -> List[Dict[str, Any]]:
        """
        Queries MongoDB Atlas using the native $vectorSearch aggregation stage.
        """
        kb_col = self._db["knowledge_base"]
        index_name = self._settings.ATLAS_VECTOR_INDEX_NAME
        num_candidates = max(self._settings.RAG_NUM_CANDIDATES, top_k * 10)

        # Build tenant filter
        filter_doc: Dict[str, Any] = {}
        if user.role != UserRole.ADMIN:
            filter_doc["user_id"] = user.id

        if service_name:
            filter_doc["service_name"] = service_name
        if environment:
            filter_doc["environment"] = environment

        vector_search_stage: Dict[str, Any] = {
            "index": index_name,
            "path": "embedding",
            "queryVector": query_vector,
            "numCandidates": num_candidates,
            "limit": top_k * 2,  # Fetch extra to filter by min_similarity
        }

        if filter_doc:
            vector_search_stage["filter"] = filter_doc

        pipeline = [
            {"$vectorSearch": vector_search_stage},
            {
                "$project": {
                    "score": {"$meta": "vectorSearchScore"},
                    "knowledge_id": 1,
                    "source_incident_id": 1,
                    "user_id": 1,
                    "service_name": 1,
                    "environment": 1,
                    "error_signature": 1,
                    "title": 1,
                    "description": 1,
                    "diagnostic_summary": 1,
                    "historical_analysis": 1,
                    "confirmed_resolution": 1,
                    "has_verified_resolution": 1,
                    "source_metadata": 1,
                    "created_at": 1,
                }
            },
        ]

        cursor = await kb_col.aggregate(pipeline)
        raw_results = await cursor.to_list(length=top_k * 2)

        # Filter by min_similarity and limit to top_k
        filtered: List[Dict[str, Any]] = []
        for doc in raw_results:
            score = float(doc.get("score", 0.0))
            if score >= min_similarity:
                filtered.append(doc)
            if len(filtered) >= top_k:
                break

        return filtered

    async def _search_in_memory_fallback(
        self,
        query_vector: List[float],
        user: UserInDB,
        service_name: Optional[str] = None,
        environment: Optional[str] = None,
        top_k: int = 3,
        min_similarity: float = 0.65,
    ) -> List[Dict[str, Any]]:
        """
        Isolated in-memory cosine similarity search used ONLY during unit testing
        or when explicitly enabled for non-Atlas development databases.
        """
        kb_col = self._db["knowledge_base"]
        query: Dict[str, Any] = {}
        if user.role != UserRole.ADMIN:
            query["user_id"] = user.id
        if service_name:
            query["service_name"] = service_name
        if environment:
            query["environment"] = environment

        cursor = kb_col.find(query)
        candidates = await cursor.to_list(length=200)

        scored: List[Dict[str, Any]] = []
        for doc in candidates:
            doc_vec = doc.get("embedding")
            if not doc_vec or len(doc_vec) != len(query_vector):
                continue
            sim = self._cosine_similarity(query_vector, doc_vec)
            if sim >= min_similarity:
                doc_copy = dict(doc)
                doc_copy["score"] = sim
                scored.append(doc_copy)

        scored.sort(key=lambda d: d.get("score", 0.0), reverse=True)
        return scored[:top_k]

    async def retrieve_similar_incidents(
        self,
        incident: Dict[str, Any],
        user: UserInDB,
        logs: Optional[List[Dict[str, Any]]] = None,
        additional_context: Optional[str] = None,
        top_k: Optional[int] = None,
        min_similarity: Optional[float] = None,
        exclude_current_incident: bool = True,
    ) -> RAGRetrievalResult:
        """
        End-to-end RAG retrieval pipeline:
        1. Validates RAG is enabled.
        2. Generates query embedding.
        3. Executes $vectorSearch against Atlas.
        4. Excludes the current incident ID from results.
        5. Returns structured precedents.
        """
        if not self._settings.RAG_ENABLED:
            logger.info("RAG retrieval is disabled in application settings.")
            return RAGRetrievalResult(status="DISABLED", similar_incidents=[], records=[])

        effective_top_k = top_k or self._settings.RAG_TOP_K
        effective_min_sim = min_similarity if min_similarity is not None else self._settings.RAG_MIN_SIMILARITY

        current_incident_id = str(incident.get("incident_id", ""))

        try:
            # 1. Build query text and vector
            query_text = self.build_query_text(incident, logs, additional_context)
            query_vector = self._embedder.generate_embedding(query_text)

            # 2. Run Atlas Vector Search
            raw_docs: List[Dict[str, Any]] = []
            method: str = "NONE"
            try:
                raw_docs = await self._search_atlas_vector_search(
                    query_vector=query_vector,
                    user=user,
                    service_name=None,  # Cross-service search allows finding similar infrastructure patterns
                    environment=None,
                    top_k=effective_top_k + (1 if exclude_current_incident else 0),
                    min_similarity=effective_min_sim,
                )
                if raw_docs:
                    method = "ATLAS_VECTOR_SEARCH"
            except OperationFailure as op_err:
                # Catch missing $vectorSearch index or non-Atlas cluster
                err_msg = str(op_err)
                logger.warning(f"Atlas Vector Search stage failed: {err_msg}")
                if self._allow_in_memory_fallback:
                    logger.info("Executing in-memory fallback similarity search for test environment.")
                    raw_docs = await self._search_in_memory_fallback(
                        query_vector=query_vector,
                        user=user,
                        top_k=effective_top_k + (1 if exclude_current_incident else 0),
                        min_similarity=effective_min_sim,
                    )
                    if raw_docs:
                        method = "IN_MEMORY_FALLBACK"
                else:
                    return RAGRetrievalResult(
                        status="UNAVAILABLE",
                        similar_incidents=[],
                        records=[],
                        error_message=f"Atlas Vector Search unavailable: {err_msg}",
                        retrieval_method="NONE",
                    )

            # If Atlas returned empty and test fallback is permitted (e.g. Atlas Search index not yet configured in UI)
            if not raw_docs and self._allow_in_memory_fallback:
                logger.info("Atlas Vector Search returned no results; executing in-memory fallback for test environment.")
                raw_docs = await self._search_in_memory_fallback(
                    query_vector=query_vector,
                    user=user,
                    top_k=effective_top_k + (1 if exclude_current_incident else 0),
                    min_similarity=effective_min_sim,
                )
                if raw_docs:
                    method = "IN_MEMORY_FALLBACK"

            # 3. Filter out the current incident itself
            filtered_docs: List[Dict[str, Any]] = []
            for doc in raw_docs:
                if exclude_current_incident and doc.get("source_incident_id") == current_incident_id:
                    continue
                filtered_docs.append(doc)
                if len(filtered_docs) >= effective_top_k:
                    break

            if not filtered_docs:
                return RAGRetrievalResult(status="EMPTY", similar_incidents=[], records=[], retrieval_method="NONE")

            # 4. Format structured representations
            similar_refs: List[SimilarIncidentReference] = []
            formatted_records: List[Dict[str, Any]] = []

            for doc in filtered_docs:
                hist_analysis = doc.get("historical_analysis") or {}
                ref = SimilarIncidentReference(
                    knowledge_id=str(doc.get("knowledge_id", "")),
                    source_incident_id=str(doc.get("source_incident_id", "")),
                    similarity_score=round(float(doc.get("score", 0.0)), 4),
                    service_name=str(doc.get("service_name", "")),
                    environment=str(doc.get("environment", "")),
                    title=str(doc.get("title", "")),
                    has_verified_resolution=bool(doc.get("has_verified_resolution", False)),
                    confirmed_resolution=doc.get("confirmed_resolution"),
                    probable_root_cause=hist_analysis.get("probable_root_cause") if hist_analysis else None,
                )
                similar_refs.append(ref)

                formatted_record = {
                    "knowledge_id": ref.knowledge_id,
                    "source_incident_id": ref.source_incident_id,
                    "similarity_score": ref.similarity_score,
                    "service_name": ref.service_name,
                    "environment": ref.environment,
                    "title": ref.title,
                    "diagnostic_summary": doc.get("diagnostic_summary", ""),
                    "has_verified_resolution": ref.has_verified_resolution,
                    "confirmed_resolution": ref.confirmed_resolution,
                    "historical_hypothesis": ref.probable_root_cause,
                    "historical_explanation": hist_analysis.get("explanation"),
                    "recommended_actions": hist_analysis.get("recommended_actions", []),
                }
                formatted_records.append(formatted_record)

            logger.info(f"Retrieved {len(similar_refs)} similar historical incidents for '{current_incident_id}'.")
            return RAGRetrievalResult(
                status="SUCCESS",
                similar_incidents=similar_refs,
                records=formatted_records,
                retrieval_method=method,
            )

        except Exception as exc:
            logger.exception("Unexpected failure during RAG retrieval")
            return RAGRetrievalResult(
                status="UNAVAILABLE",
                similar_incidents=[],
                records=[],
                error_message=str(exc),
            )
