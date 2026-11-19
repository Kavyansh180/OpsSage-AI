from datetime import datetime, timezone
import pytest
from backend.app.services.evidence_collector import EvidenceBundle
from backend.app.services.prompt_builder import RCAPromptBuilder


def test_system_instruction_contains_grounding_and_confidence_rules():
    instruction = RCAPromptBuilder.SYSTEM_INSTRUCTION
    assert "STRICT GROUNDING & INTEGRITY RULES" in instruction
    assert "Do NOT invent, hallucinate, or extrapolate" in instruction
    assert "CONFIDENCE ASSESSMENT" in instruction
    assert "'HIGH'" in instruction
    assert "'MEDIUM'" in instruction
    assert "'LOW'" in instruction
    assert "JSON object" in instruction


def test_user_prompt_formats_incident_metadata():
    bundle = EvidenceBundle(
        incident={
            "incident_id": "INC-20261118-TEST1",
            "service_name": "payment-gateway",
            "environment": "production",
            "severity": "CRITICAL",
            "status": "OPEN",
            "first_seen": datetime(2026, 11, 18, 10, 0, 0, tzinfo=timezone.utc),
            "last_seen": datetime(2026, 11, 18, 10, 5, 0, tzinfo=timezone.utc),
            "event_count": 42,
            "title": "Connection refused to payment cluster",
        },
        logs=[],
        evidence_log_count=0,
        redacted_secrets_count=0,
    )

    prompt = RCAPromptBuilder.build_user_prompt(bundle)
    assert "INC-20261118-TEST1" in prompt
    assert "payment-gateway" in prompt
    assert "production" in prompt
    assert "CRITICAL" in prompt
    assert "Cumulative Event Count: 42" in prompt
    assert "Connection refused to payment cluster" in prompt
    assert "No individual log records could be retrieved" in prompt


def test_user_prompt_formats_chronological_logs():
    bundle = EvidenceBundle(
        incident={
            "incident_id": "INC-20261118-TEST2",
            "service_name": "order-service",
            "environment": "staging",
            "severity": "HIGH",
            "status": "OPEN",
            "title": "Database transaction timeout",
        },
        logs=[
            {
                "timestamp": "2026-11-18 10:00:00",
                "level": "ERROR",
                "service_name": "order-service",
                "message": "Acquiring pool connection timeout after 30s",
                "request_id": "req-1234",
            },
            {
                "timestamp": "2026-11-18 10:00:05",
                "level": "CRITICAL",
                "service_name": "order-service",
                "message": "Connection pool exhausted (size=50)",
                "request_id": "req-5678",
            },
        ],
        evidence_log_count=2,
        redacted_secrets_count=0,
    )

    prompt = RCAPromptBuilder.build_user_prompt(bundle)
    assert "[1] 2026-11-18 10:00:00 [ERROR] (order-service) [req_id=req-1234]: Acquiring pool connection timeout after 30s" in prompt
    assert "[2] 2026-11-18 10:00:05 [CRITICAL] (order-service) [req_id=req-5678]: Connection pool exhausted (size=50)" in prompt
    assert "probable_root_cause" in prompt
    assert "supporting_evidence" in prompt


def test_user_prompt_with_additional_context():
    bundle = EvidenceBundle(
        incident={"incident_id": "INC-001", "service_name": "auth", "title": "Crash"},
        logs=[],
        evidence_log_count=0,
        redacted_secrets_count=0,
    )
    prompt = RCAPromptBuilder.build_user_prompt(
        bundle, additional_context="Deployment v2.4.1 rolled out 5 minutes prior to failures."
    )
    assert "OPERATOR CONTEXT / NOTES" in prompt
    assert "Deployment v2.4.1 rolled out 5 minutes prior" in prompt
