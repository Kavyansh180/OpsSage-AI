from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from backend.app.config import Settings, get_settings
from backend.app.core.exceptions import ResourceNotFoundError
from backend.app.core.logging import get_logger
from backend.app.models.analysis import AnalysisInDB
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.analysis import (
    AnalysisResponse,
    PaginatedAnalysisResponse,
    RCARequest,
    StructuredRCAResponse,
)
from backend.app.services.evidence_collector import EvidenceCollector
from backend.app.services.knowledge_retriever import KnowledgeRetrievalService, RAGRetrievalResult
from backend.app.services.llm.base import LLMProvider
from backend.app.services.llm.factory import get_llm_provider
from backend.app.services.prompt_builder import RCAPromptBuilder

logger = get_logger("services.rca_service")


class RCAService:
    """
    Orchestrates the AI Root-Cause Analysis pipeline:
    1. Collects and sanitizes incident telemetry and logs.
    2. Builds an anti-hallucination prompt.
    3. Invokes the configured LLM provider for structured reasoning.
    4. Validates and persists the analysis history in MongoDB.
    """

    @classmethod
    def generate_analysis_id(cls) -> str:
        """Generates a human-readable unique analysis identifier."""
        ts_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        rand_str = uuid4().hex[:6].upper()
        return f"RCA-{ts_str}-{rand_str}"

    @classmethod
    async def analyze_incident(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        incident_id: str,
        request_data: Optional[RCARequest] = None,
        provider: Optional[LLMProvider] = None,
        retrieval_service: Optional[KnowledgeRetrievalService] = None,
        settings: Optional[Settings] = None,
    ) -> AnalysisResponse:
        """
        Executes end-to-end RCA on the target incident.
        Incorporates historical RAG retrieval, evidence sanitation, and LLM reasoning.
        Stores the resulting analysis document without overwriting previous runs.
        """
        cfg = settings or get_settings()

        # 1. Determine maximum evidence logs
        max_logs = cfg.RCA_MAX_EVIDENCE_LOGS
        additional_context = None
        if request_data:
            if request_data.max_evidence_logs is not None:
                max_logs = request_data.max_evidence_logs
            additional_context = request_data.additional_context

        # 2. Collect and redact evidence
        collector = EvidenceCollector(db)
        evidence = await collector.collect_evidence(
            incident_id=incident_id,
            user=user,
            max_evidence_logs=max_logs,
        )

        # 3. Retrieve relevant historical incidents via RAG (Module 5)
        rag_retriever = retrieval_service or KnowledgeRetrievalService(db=db, settings=cfg)
        try:
            rag_result = await rag_retriever.retrieve_similar_incidents(
                incident=evidence.incident,
                user=user,
                logs=evidence.logs,
                additional_context=additional_context,
            )
        except Exception as rag_exc:
            logger.warning(f"RAG retrieval encountered an error; proceeding with current evidence alone: {rag_exc}")
            rag_result = RAGRetrievalResult(
                status="UNAVAILABLE",
                similar_incidents=[],
                records=[],
                error_message=str(rag_exc),
            )

        # 4. Resolve LLM provider
        llm = provider or get_llm_provider(cfg)

        # 5. Construct prompt with current evidence and untrusted historical context
        system_instruction = RCAPromptBuilder.SYSTEM_INSTRUCTION
        user_prompt = RCAPromptBuilder.build_user_prompt(
            evidence=evidence,
            additional_context=additional_context,
            historical_context=rag_result.records if rag_result.records else None,
        )

        logger.info(
            f"Invoking {llm.provider_name} ({llm.model_name}) for incident {incident_id} "
            f"with {evidence.evidence_log_count} logs (redactions: {evidence.redacted_secrets_count}), "
            f"RAG status: {rag_result.status} ({len(rag_result.similar_incidents)} precedents)"
        )

        # 6. Invoke LLM provider
        structured_output, raw_text = await llm.generate_structured(
            prompt=user_prompt,
            schema_cls=StructuredRCAResponse,
            system_instruction=system_instruction,
        )

        # 7. Build persistent analysis record
        now = datetime.now(timezone.utc)
        resolved_incident_id = str(evidence.incident.get("incident_id", incident_id))
        target_user_id = str(evidence.incident.get("user_id", user.id))

        analysis_id = cls.generate_analysis_id()
        analysis_data = {
            "analysis_id": analysis_id,
            "incident_id": resolved_incident_id,
            "user_id": target_user_id,
            "probable_root_cause": structured_output.probable_root_cause,
            "explanation": structured_output.explanation,
            "supporting_evidence": structured_output.supporting_evidence,
            "contributing_factors": structured_output.contributing_factors,
            "confidence_level": structured_output.confidence_level.value,
            "recommended_actions": structured_output.recommended_actions,
            "limitations": structured_output.limitations,
            "provider": llm.provider_name,
            "model": llm.model_name,
            "evidence_log_count": evidence.evidence_log_count,
            "redacted_secrets_count": evidence.redacted_secrets_count,
            "raw_llm_response": raw_text,
            "rag_status": rag_result.status,
            "similar_incidents": [sim.model_dump() for sim in rag_result.similar_incidents],
            "created_at": now,
        }

        # 8. Persist to MongoDB 'analyses' collection
        insert_result = await db["analyses"].insert_one(analysis_data)
        analysis_data["_id"] = insert_result.inserted_id

        logger.info(f"Successfully generated and stored analysis {analysis_id} for incident {resolved_incident_id}")

        return AnalysisResponse.model_validate(analysis_data)

    @classmethod
    async def get_incident_analyses(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        incident_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedAnalysisResponse:
        """
        Retrieves historical root-cause analyses for a specific incident,
        sorted newest to oldest. Enforces tenant isolation.
        """
        # First verify incident exists and user has access
        incidents_col = db["incidents"]
        inc_query: Dict[str, Any] = {"incident_id": incident_id}
        if ObjectId.is_valid(incident_id):
            inc_query = {"$or": [{"incident_id": incident_id}, {"_id": ObjectId(incident_id)}]}

        incident_doc = await incidents_col.find_one(inc_query)
        if not incident_doc:
            raise ResourceNotFoundError(f"Incident with ID '{incident_id}' not found.")

        if user.role != UserRole.ADMIN and incident_doc.get("user_id") != user.id:
            raise ResourceNotFoundError(f"Incident with ID '{incident_id}' not found.")

        target_incident_id = incident_doc.get("incident_id", incident_id)

        query: Dict[str, Any] = {"incident_id": target_incident_id}
        if user.role != UserRole.ADMIN:
            query["user_id"] = user.id

        analyses_col = db["analyses"]
        total = await analyses_col.count_documents(query)

        cursor = analyses_col.find(query).sort("created_at", -1).skip(offset).limit(limit)
        docs = await cursor.to_list(length=limit)

        items = [AnalysisResponse.model_validate(d) for d in docs]
        return PaginatedAnalysisResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    @classmethod
    async def get_analysis_by_id(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        analysis_id: str,
    ) -> AnalysisResponse:
        """
        Retrieves a single root-cause analysis by analysis_id or MongoDB ObjectId.
        Enforces tenant isolation.
        """
        query: Dict[str, Any] = {"analysis_id": analysis_id}
        if ObjectId.is_valid(analysis_id):
            query = {"$or": [{"analysis_id": analysis_id}, {"_id": ObjectId(analysis_id)}]}

        analyses_col = db["analyses"]
        doc = await analyses_col.find_one(query)
        if not doc:
            raise ResourceNotFoundError(f"Analysis with ID '{analysis_id}' not found.")

        if user.role != UserRole.ADMIN and doc.get("user_id") != user.id:
            raise ResourceNotFoundError(f"Analysis with ID '{analysis_id}' not found.")

        return AnalysisResponse.model_validate(doc)
