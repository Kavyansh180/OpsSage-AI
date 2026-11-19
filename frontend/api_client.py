import os
from typing import Any, Dict, List, Optional
import httpx


def _resolve_base_url(explicit_url: Optional[str] = None) -> str:
    """
    Resolves backend API URL with priority:
    1. Explicit parameter
    2. Streamlit secrets (for Streamlit Community Cloud)
    3. Environment variables (API_BASE_URL, BACKEND_URL)
    4. Localhost fallback
    """
    if explicit_url:
        return explicit_url

    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            if "API_BASE_URL" in st.secrets:
                return str(st.secrets["API_BASE_URL"])
            if "BACKEND_URL" in st.secrets:
                return str(st.secrets["BACKEND_URL"])
    except Exception:
        pass

    return os.getenv("API_BASE_URL") or os.getenv("BACKEND_URL") or "http://localhost:8000"


class APIClient:
    """
    Authenticated HTTP client for communicating between Streamlit frontend and FastAPI backend.
    Enforces strict separation: frontend never accesses database directly.
    """

    def __init__(self, base_url: Optional[str] = None):
        raw_url = _resolve_base_url(base_url)
        # Ensure base URL points to /api/v1
        cleaned = raw_url.rstrip("/")
        if not cleaned.endswith("/api/v1"):
            self.base_url = f"{cleaned}/api/v1"
        else:
            self.base_url = cleaned

    def _get_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def login(self, username_or_email: str, password: str) -> Dict[str, Any]:
        """Authenticates user credentials and returns JWT token payload."""
        url = f"{self.base_url}/auth/login"
        payload = {"email": username_or_email.strip(), "password": password}
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                return resp.json()
            else:
                detail = resp.json().get("detail", resp.text)
                raise Exception(f"Login failed ({resp.status_code}): {detail}")

    def register(self, email: str, password: str, full_name: str) -> Dict[str, Any]:
        """Registers a new user account."""
        url = f"{self.base_url}/auth/register"
        payload = {"email": email.strip(), "password": password, "full_name": full_name.strip()}
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code in (200, 201):
                return resp.json()
            else:
                detail = resp.json().get("detail", resp.text)
                raise Exception(f"Registration failed: {detail}")

    def get_current_user(self, token: str) -> Dict[str, Any]:
        """Fetches the authenticated user profile."""
        url = f"{self.base_url}/auth/me"
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url, headers=self._get_headers(token))
            if resp.status_code == 200:
                return resp.json()
            raise Exception("Failed to fetch user session.")

    def get_analytics(self, token: str, days: int = 30) -> Dict[str, Any]:
        """Fetches KPI metrics and analytics trends."""
        url = f"{self.base_url}/analytics/overview?days={days}"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=self._get_headers(token))
            if resp.status_code == 200:
                return resp.json()
            raise Exception(f"Analytics query failed: {resp.text}")

    def list_incidents(
        self,
        token: str,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        service_name: Optional[str] = None,
        environment: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Queries incidents with filters and pagination."""
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status and status != "ALL":
            params["status"] = status
        if severity and severity != "ALL":
            params["severity"] = severity
        if service_name and service_name != "ALL":
            params["service_name"] = service_name
        if environment and environment != "ALL":
            params["environment"] = environment

        url = f"{self.base_url}/incidents"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=self._get_headers(token), params=params)
            if resp.status_code == 200:
                return resp.json()
            raise Exception(f"Failed to list incidents: {resp.text}")

    def get_incident(self, token: str, incident_id: str) -> Dict[str, Any]:
        """Retrieves a single incident by ID."""
        url = f"{self.base_url}/incidents/{incident_id}"
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url, headers=self._get_headers(token))
            if resp.status_code == 200:
                return resp.json()
            raise Exception(f"Incident '{incident_id}' not found.")

    def acknowledge_incident(self, token: str, incident_id: str) -> Dict[str, Any]:
        """Transitions incident status to ACKNOWLEDGED."""
        url = f"{self.base_url}/incidents/{incident_id}/acknowledge"
        with httpx.Client(timeout=5.0) as client:
            resp = client.patch(url, headers=self._get_headers(token))
            if resp.status_code == 200:
                return resp.json()
            raise Exception(f"Acknowledgement failed: {resp.text}")

    def assign_incident(self, token: str, incident_id: str, assigned_to: str) -> Dict[str, Any]:
        """Assigns an incident to an engineer."""
        url = f"{self.base_url}/incidents/{incident_id}/assign"
        with httpx.Client(timeout=5.0) as client:
            resp = client.patch(url, headers=self._get_headers(token), json={"assigned_to": assigned_to})
            if resp.status_code == 200:
                return resp.json()
            raise Exception(f"Assignment failed: {resp.text}")

    def update_severity(self, token: str, incident_id: str, severity: str) -> Dict[str, Any]:
        """Updates incident priority rating."""
        url = f"{self.base_url}/incidents/{incident_id}/severity"
        with httpx.Client(timeout=5.0) as client:
            resp = client.patch(url, headers=self._get_headers(token), json={"severity": severity})
            if resp.status_code == 200:
                return resp.json()
            raise Exception(f"Severity update failed: {resp.text}")

    def add_investigation_note(self, token: str, incident_id: str, note: str) -> Dict[str, Any]:
        """Logs an investigation note."""
        url = f"{self.base_url}/incidents/{incident_id}/notes"
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, headers=self._get_headers(token), json={"note": note})
            if resp.status_code in (200, 201):
                return resp.json()
            raise Exception(f"Failed to add note: {resp.text}")

    def record_resolution(
        self,
        token: str,
        incident_id: str,
        root_cause: str,
        resolution: str,
        actions: List[str],
        is_verified: bool = True,
        rca_analysis_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Records confirmed resolution details and resolves incident."""
        url = f"{self.base_url}/incidents/{incident_id}/resolution"
        payload = {
            "confirmed_root_cause": root_cause,
            "confirmed_resolution": resolution,
            "resolution_actions": actions,
            "is_verified": is_verified,
            "rca_analysis_id": rca_analysis_id,
            "notes": notes,
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, headers=self._get_headers(token), json=payload)
            if resp.status_code == 200:
                return resp.json()
            raise Exception(f"Resolution recording failed: {resp.text}")

    def verify_resolution(self, token: str, incident_id: str, is_verified: bool, notes: Optional[str] = None) -> Dict[str, Any]:
        """Explicitly marks resolution as verified by engineer."""
        url = f"{self.base_url}/incidents/{incident_id}/verify-resolution"
        payload = {"is_verified": is_verified, "verification_notes": notes}
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, headers=self._get_headers(token), json=payload)
            if resp.status_code == 200:
                return resp.json()
            raise Exception(f"Resolution verification failed: {resp.text}")

    def get_incident_history(self, token: str, incident_id: str) -> Dict[str, Any]:
        """Fetches audit history for an incident."""
        url = f"{self.base_url}/incidents/{incident_id}/history"
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url, headers=self._get_headers(token))
            if resp.status_code == 200:
                return resp.json()
            raise Exception(f"Failed to fetch incident history: {resp.text}")

    def trigger_rca(self, token: str, incident_id: str, additional_context: Optional[str] = None) -> Dict[str, Any]:
        """Triggers AI Root-Cause Analysis for an incident."""
        url = f"{self.base_url}/incidents/{incident_id}/analyze"
        payload: Dict[str, Any] = {}
        if additional_context:
            payload["additional_context"] = additional_context
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(url, headers=self._get_headers(token), json=payload)
            if resp.status_code == 200:
                return resp.json()
            raise Exception(f"RCA generation failed: {resp.text}")

    def get_incident_analyses(self, token: str, incident_id: str) -> Dict[str, Any]:
        """Fetches historical RCA analyses for an incident."""
        url = f"{self.base_url}/incidents/{incident_id}/analyses"
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url, headers=self._get_headers(token))
            if resp.status_code == 200:
                return resp.json()
            raise Exception(f"Failed to fetch analyses: {resp.text}")

    def search_knowledge_base(
        self,
        token: str,
        query: str,
        service_name: Optional[str] = None,
        environment: Optional[str] = None,
        top_k: int = 5,
        min_similarity: float = 0.50,
    ) -> Dict[str, Any]:
        """Searches historical incident knowledge base using semantic vector retrieval."""
        url = f"{self.base_url}/knowledge/search"
        payload = {
            "query": query,
            "service_name": service_name if service_name != "ALL" else None,
            "environment": environment if environment != "ALL" else None,
            "top_k": top_k,
            "min_similarity": min_similarity,
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, headers=self._get_headers(token), json=payload)
            if resp.status_code == 200:
                return resp.json()
            raise Exception(f"Knowledge search failed: {resp.text}")

    def get_knowledge_document(self, token: str, knowledge_id: str) -> Dict[str, Any]:
        """Retrieves a specific knowledge document (omitting raw embedding vectors)."""
        url = f"{self.base_url}/knowledge/{knowledge_id}"
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url, headers=self._get_headers(token))
            if resp.status_code == 200:
                return resp.json()
            raise Exception(f"Knowledge document '{knowledge_id}' not found.")
