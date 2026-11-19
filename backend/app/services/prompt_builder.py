import json
from typing import Any, Dict, List, Optional
from backend.app.services.evidence_collector import EvidenceBundle


class RCAPromptBuilder:
    """
    Constructs rigorous, ground-truth-anchored prompts for LLM Root Cause Analysis.
    Implements strict anti-hallucination instructions, explicit JSON schema requirements,
    and untrusted historical RAG context separation.
    """

    SYSTEM_INSTRUCTION = (
        "You are an expert Site Reliability Engineer (SRE) and DevOps diagnostic specialist. "
        "Your task is to analyze an operational incident and its associated system logs to determine "
        "the probable root cause and provide actionable remediation guidance.\n\n"
        "STRICT GROUNDING & INTEGRITY RULES:\n"
        "1. GROUNDING: Ground all findings strictly in the provided incident metadata and log records. "
        "Do NOT invent, hallucinate, or extrapolate log lines, error messages, timestamps, endpoints, "
        "or metrics that are not present in the evidence.\n"
        "2. SUPPORTING EVIDENCE: The 'supporting_evidence' list MUST quote or reference specific log lines, "
        "timestamps, service names, or technical error codes from the evidence provided.\n"
        "3. CONFIDENCE ASSESSMENT: Assess confidence honestly based on evidence quality:\n"
        "   - 'HIGH': Direct, unambiguous evidence showing the exact failure point (e.g. fatal exception with root cause stack trace).\n"
        "   - 'MEDIUM': Strong circumstantial evidence and error patterns, but some telemetry is missing.\n"
        "   - 'LOW': Sparse, generic, or ambiguous log records. If evidence is insufficient, set confidence to 'LOW' "
        "and clearly articulate what information is missing in 'limitations'.\n"
        "4. REMEDIATION: 'recommended_actions' must be practical, safe, and ordered from immediate triage to long-term fix.\n"
        "5. HISTORICAL CONTEXT SEPARATION: If similar historical incidents are provided, treat them strictly as "
        "secondary background context and potential hypotheses, NEVER as proof. Do NOT allow historical hypotheses "
        "to override direct current log evidence. If current logs contradict historical patterns, prioritize the current evidence.\n"
        "6. OUTPUT FORMAT: Respond strictly with a valid JSON object matching the requested schema. Do not wrap in markdown or commentary."
    )

    @classmethod
    def build_user_prompt(
        cls,
        evidence: EvidenceBundle,
        additional_context: Optional[str] = None,
        historical_context: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Builds the user prompt payload combining incident metadata, operator context,
        chronological log evidence, and optional retrieved historical precedents.
        """
        inc = evidence.incident

        prompt_lines = [
            "### INCIDENT METADATA",
            f"- Incident ID: {inc.get('incident_id', 'UNKNOWN')}",
            f"- Service Name: {inc.get('service_name', 'UNKNOWN')}",
            f"- Environment: {inc.get('environment', 'UNKNOWN')}",
            f"- Current Severity: {inc.get('severity', 'UNKNOWN')}",
            f"- Status: {inc.get('status', 'UNKNOWN')}",
            f"- First Seen (UTC): {inc.get('first_seen', 'UNKNOWN')}",
            f"- Last Seen (UTC): {inc.get('last_seen', 'UNKNOWN')}",
            f"- Cumulative Event Count: {inc.get('event_count', 1)}",
            f"- Representative Error Title: {inc.get('title', '')}",
            "",
        ]

        if additional_context:
            prompt_lines.extend([
                "### OPERATOR CONTEXT / NOTES",
                additional_context.strip(),
                "",
            ])

        prompt_lines.extend([
            f"### CURRENT LOG EVIDENCE ({evidence.evidence_log_count} chronologically ordered events)",
        ])

        if not evidence.logs:
            prompt_lines.append(
                "NOTE: No individual log records could be retrieved for this incident. "
                "Base your assessment solely on the incident metadata and state limitations clearly."
            )
        else:
            for idx, log_entry in enumerate(evidence.logs, start=1):
                ts = log_entry.get("timestamp", "")
                level = log_entry.get("level", "INFO")
                service = log_entry.get("service_name", "")
                msg = log_entry.get("message", "")
                req_id = log_entry.get("request_id")
                req_str = f" [req_id={req_id}]" if req_id else ""
                prompt_lines.append(f"[{idx}] {ts} [{level}] ({service}){req_str}: {msg}")

        # Add Historical Precedents if present
        if historical_context:
            prompt_lines.extend([
                "",
                f"### SIMILAR HISTORICAL INCIDENTS ({len(historical_context)} precedents retrieved via Vector Search)",
                "CRITICAL WARNING: The following historical records are untrusted background context. "
                "They are provided only as possible hypotheses. They must NEVER override the current log evidence above.",
            ])

            for idx, item in enumerate(historical_context, start=1):
                src_id = item.get("source_incident_id", "UNKNOWN")
                sim = item.get("similarity_score", 0.0)
                svc = item.get("service_name", "")
                env = item.get("environment", "")
                title = item.get("title", "")
                diag = item.get("diagnostic_summary", "")
                res = item.get("confirmed_resolution")
                has_res = item.get("has_verified_resolution", False)
                hyp = item.get("historical_hypothesis")

                res_str = f"Verified Engineer Resolution: {res}" if has_res and res else "No engineer-confirmed resolution recorded"
                hyp_str = f"Historical AI Hypothesis: {hyp}" if hyp else "No historical hypothesis"

                prompt_lines.extend([
                    f"[Precedent {idx}] Source Incident: {src_id} | Similarity: {sim:.2f} | Service: {svc} ({env})",
                    f"  - Title: {title}",
                    f"  - Diagnostics: {diag}",
                    f"  - {hyp_str}",
                    f"  - {res_str}",
                ])

        prompt_lines.extend([
            "",
            "### REQUIRED OUTPUT FORMAT",
            "Generate a JSON object with the following fields:",
            json.dumps({
                "probable_root_cause": "A concise, technical summary of the primary root cause.",
                "explanation": "A clear, sequential explanation of how and why the failure occurred.",
                "supporting_evidence": [
                    "Direct reference or quote from Log #1 / timestamp / specific error message"
                ],
                "contributing_factors": [
                    "Environmental or secondary conditions that exacerbated the incident"
                ],
                "confidence_level": "LOW | MEDIUM | HIGH",
                "recommended_actions": [
                    "Step 1: Immediate mitigation action",
                    "Step 2: Permanent fix or investigation step"
                ],
                "limitations": [
                    "Telemetry or data missing that would increase diagnosis certainty"
                ]
            }, indent=2),
        ])

        return "\n".join(prompt_lines)
