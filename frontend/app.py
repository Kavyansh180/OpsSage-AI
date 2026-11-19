import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st

from frontend.api_client import APIClient

# Page configuration
st.set_page_config(
    page_title="OpsSage AI — Incident Investigation & RCA",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Dark SaaS Theme Styling
st.markdown(
    """
    <style>
    .main {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    .stMetric {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 12px;
    }
    .incident-card {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .badge-critical {
        background-color: #DA3633;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8em;
    }
    .badge-high {
        background-color: #D29922;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8em;
    }
    .badge-medium {
        background-color: #1F6FEB;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8em;
    }
    .badge-low {
        background-color: #238636;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8em;
    }
    .badge-verified {
        background-color: #238636;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8em;
    }
    .badge-hypothesis {
        background-color: #8957E5;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.8em;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize Session State
if "token" not in st.session_state:
    st.session_state.token = None
if "user_info" not in st.session_state:
    st.session_state.user_info = None
if "selected_incident_id" not in st.session_state:
    st.session_state.selected_incident_id = None

client = APIClient()


def render_login():
    """Render login and registration view."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🛡️ OpsSage AI")
        st.markdown("### DevOps Incident Investigation & Root-Cause Analysis Platform")
        st.info("Log in with your credentials to access the incident response command center.")

        tab_login, tab_register = st.tabs(["Sign In", "Create Account"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Work Email", placeholder="engineer@company.com")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Sign In", use_container_width=True)

                if submit:
                    if not email or not password:
                        st.error("Please enter both email and password.")
                    else:
                        try:
                            with st.spinner("Authenticating..."):
                                data = client.login(email, password)
                                st.session_state.token = data.get("access_token")
                                st.session_state.user_info = client.get_current_user(st.session_state.token)
                                st.success("Signed in successfully!")
                                st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

        with tab_register:
            with st.form("register_form"):
                reg_name = st.text_input("Full Name", placeholder="Jane Doe")
                reg_email = st.text_input("Work Email", placeholder="jane@company.com")
                reg_password = st.text_input("Password (min 8 chars)", type="password")
                reg_submit = st.form_submit_button("Create Account", use_container_width=True)

                if reg_submit:
                    if not reg_name or not reg_email or not reg_password:
                        st.error("Please fill in all registration fields.")
                    elif len(reg_password) < 8:
                        st.error("Password must be at least 8 characters long.")
                    else:
                        try:
                            with st.spinner("Registering account..."):
                                client.register(reg_email, reg_password, reg_name)
                                st.success("Account created successfully! Please sign in.")
                        except Exception as exc:
                            st.error(str(exc))


def render_sidebar():
    """Render application branding, current user, and navigation."""
    st.sidebar.markdown("## 🛡️ **OpsSage AI**")
    st.sidebar.caption("Autonomous Incident Intelligence")

    user = st.session_state.user_info or {}
    role = user.get("role", "viewer").upper()

    st.sidebar.markdown(f"**User**: `{user.get('email', 'Unknown')}`")
    role_color = "green" if role == "ADMIN" else "blue" if role == "ENGINEER" else "orange"
    st.sidebar.markdown(f"**Role**: :{role_color}[{role}]")

    st.sidebar.divider()

    menu = [
        "1. Dashboard Overview",
        "2. Incidents",
        "3. Incident Details",
        "4. AI Root-Cause Analysis",
        "5. Historical Similar Incidents",
        "6. Knowledge Base",
        "7. Analytics",
    ]
    choice = st.sidebar.radio("Navigation", menu)

    st.sidebar.divider()
    if st.sidebar.button("Sign Out", use_container_width=True):
        st.session_state.token = None
        st.session_state.user_info = None
        st.session_state.selected_incident_id = None
        st.rerun()

    return choice


def render_dashboard_overview():
    """Page 1: KPI overview and top charts."""
    st.title("📊 Incident Response Overview")
    st.caption("Live operational telemetry and incident resolution health metrics.")

    token = st.session_state.token
    try:
        with st.spinner("Loading telemetry..."):
            analytics = client.get_analytics(token, days=30)
    except Exception as exc:
        st.error(f"Failed to fetch telemetry: {exc}")
        return

    # Metric Cards
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total Incidents", analytics.get("total_incidents", 0))
    m2.metric("Open", analytics.get("open_incidents", 0))
    m3.metric("Acknowledged", analytics.get("acknowledged_incidents", 0))
    m4.metric("Resolved", analytics.get("resolved_incidents", 0))
    m5.metric("Critical", analytics.get("critical_incidents", 0))
    m6.metric("Resolution Rate", f"{analytics.get('resolution_rate_pct', 0)}%")

    st.divider()

    # Visualizations
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Incident Volume (Last 30 Days)")
        daily_trends = analytics.get("daily_trends", [])
        if daily_trends:
            df_trends = pd.DataFrame(daily_trends)
            df_trends["date"] = pd.to_datetime(df_trends["date"])
            df_trends = df_trends.set_index("date")
            st.line_chart(df_trends["count"])
        else:
            st.info("No historical trends recorded in window.")

    with c2:
        st.subheader("Severity Breakdown")
        by_sev = analytics.get("by_severity", {})
        if by_sev and any(by_sev.values()):
            df_sev = pd.DataFrame(list(by_sev.items()), columns=["Severity", "Count"]).set_index("Severity")
            st.bar_chart(df_sev)
        else:
            st.info("No severity data available.")

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Incidents by Service")
        by_svc = analytics.get("by_service", {})
        if by_svc and any(by_svc.values()):
            df_svc = pd.DataFrame(list(by_svc.items()), columns=["Service", "Count"]).set_index("Service")
            st.bar_chart(df_svc)
        else:
            st.info("No service incidents logged.")

    with c4:
        st.subheader("Status Distribution")
        by_st = analytics.get("by_status", {})
        if by_st and any(by_st.values()):
            df_st = pd.DataFrame(list(by_st.items()), columns=["Status", "Count"]).set_index("Status")
            st.bar_chart(df_st)
        else:
            st.info("No status data available.")


def render_incidents():
    """Page 2: Incident listing with search, filters, and actions."""
    st.title("🚨 Operational Incidents")
    st.caption("Active and resolved deterministic failure groups clustered by error signature.")

    token = st.session_state.token

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        status_filter = st.selectbox("Status", ["ALL", "OPEN", "ACKNOWLEDGED", "RESOLVED"])
    with f2:
        sev_filter = st.selectbox("Severity", ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"])
    with f3:
        env_filter = st.selectbox("Environment", ["ALL", "production", "staging", "development"])
    with f4:
        search_kw = st.text_input("Search Title / Service", placeholder="e.g. timeout, redis")

    try:
        with st.spinner("Fetching incidents..."):
            res = client.list_incidents(
                token,
                status=status_filter,
                severity=sev_filter,
                environment=env_filter,
                limit=100,
            )
            items = res.get("items", [])
    except Exception as exc:
        st.error(f"Failed to query incidents: {exc}")
        return

    if search_kw:
        kw = search_kw.lower()
        items = [i for i in items if kw in i.get("title", "").lower() or kw in i.get("service_name", "").lower()]

    st.markdown(f"**Showing {len(items)} incidents** (Total: {res.get('total', 0)})")

    if not items:
        st.info("No operational incidents found matching criteria.")
        return

    for inc in items:
        with st.container():
            inc_id = inc.get("incident_id")
            sev = inc.get("severity", "LOW")
            st_val = inc.get("status", "OPEN")
            title = inc.get("title", "No Title")
            svc = inc.get("service_name", "Unknown")
            env = inc.get("environment", "Unknown")
            events = inc.get("event_count", 1)
            verified = inc.get("has_verified_resolution", False)

            col_main, col_btn = st.columns([4, 1])
            with col_main:
                sev_badge = f'<span class="badge-{sev.lower()}">{sev}</span>'
                ver_badge = '<span class="badge-verified">✓ Verified Resolution</span>' if verified else ""
                st.markdown(f"### {sev_badge} `{inc_id}` — {title} {ver_badge}", unsafe_allow_html=True)
                st.markdown(
                    f"**Service**: `{svc}` | **Environment**: `{env}` | **Status**: `{st_val}` | **Events**: `{events}`"
                )

            with col_btn:
                if st.button("Investigate →", key=f"btn_{inc_id}", use_container_width=True):
                    st.session_state.selected_incident_id = inc_id
                    st.rerun()

            st.divider()


def render_incident_details():
    """Page 3: Comprehensive incident details and management controls."""
    st.title("🔍 Incident Details & Investigation")

    token = st.session_state.token
    user = st.session_state.user_info or {}
    role = user.get("role", "viewer")
    is_viewer = role == "viewer"

    # Input or selector for incident ID
    inc_input = st.text_input(
        "Incident ID",
        value=st.session_state.selected_incident_id or "",
        placeholder="e.g. INC-20261119-A1B2C3",
    )
    if not inc_input:
        st.info("Select an incident from the Incidents list or enter an incident ID above.")
        return

    try:
        with st.spinner("Loading incident details..."):
            inc = client.get_incident(token, inc_input)
    except Exception as exc:
        st.error(str(exc))
        return

    # Metadata Banner
    inc_id = inc.get("incident_id")
    sev = inc.get("severity")
    st_val = inc.get("status")
    assigned_to = inc.get("assigned_to") or "Unassigned"

    col_meta1, col_meta2 = st.columns([3, 1])
    with col_meta1:
        st.subheader(f"[{sev}] {inc.get('title')}")
        st.markdown(f"**Incident ID**: `{inc_id}` | **Service**: `{inc.get('service_name')}` | **Env**: `{inc.get('environment')}`")
        st.markdown(f"**Error Signature**: `{inc.get('error_signature')}`")
        st.markdown(f"**First Seen**: `{inc.get('first_seen')}` | **Last Seen**: `{inc.get('last_seen')}`")

    with col_meta2:
        st.markdown(f"**Current Status**: `{st_val}`")
        st.markdown(f"**Assignee**: `{assigned_to}`")
        st.markdown(f"**Cumulative Events**: `{inc.get('event_count')}`")

    st.divider()

    # Engineer Action Controls
    st.markdown("### 🛠️ Incident Actions")
    if is_viewer:
        st.warning("⚠️ You are logged in with the 'viewer' role. Modifications and actions are disabled.")

    a_col1, a_col2, a_col3, a_col4 = st.columns(4)

    # 1. Acknowledge
    with a_col1:
        can_ack = st_val == "OPEN" and not is_viewer
        if st.button("Acknowledge Incident", disabled=not can_ack, use_container_width=True):
            try:
                client.acknowledge_incident(token, inc_id)
                st.success("Incident acknowledged.")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    # 2. Assign
    with a_col2:
        with st.popover("Assign Incident", disabled=is_viewer, use_container_width=True):
            assign_to = st.text_input("Engineer Email / ID", value=user.get("email", ""))
            if st.button("Confirm Assignment"):
                try:
                    client.assign_incident(token, inc_id, assign_to)
                    st.success("Assigned successfully.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    # 3. Update Severity
    with a_col3:
        with st.popover("Adjust Severity", disabled=is_viewer, use_container_width=True):
            new_sev = st.selectbox("New Severity", ["CRITICAL", "HIGH", "MEDIUM", "LOW"], index=["CRITICAL", "HIGH", "MEDIUM", "LOW"].index(sev))
            if st.button("Update Severity"):
                try:
                    client.update_severity(token, inc_id, new_sev)
                    st.success("Severity updated.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    # 4. Record Resolution
    with a_col4:
        with st.popover("Record Resolution", disabled=is_viewer, use_container_width=True):
            st.markdown("#### Confirm Incident Resolution")
            rc = st.text_area("Confirmed Root Cause", value=inc.get("confirmed_root_cause") or "")
            res_desc = st.text_area("Resolution Summary", value=inc.get("confirmed_resolution") or "")
            actions_raw = st.text_area("Resolution Actions (one per line)", value="\n".join(inc.get("resolution_actions") or []))
            verify_box = st.checkbox("Verify as Confirmed Solution", value=True)

            if st.button("Save & Resolve Incident"):
                if not rc or not res_desc:
                    st.error("Please provide both root cause and resolution.")
                else:
                    try:
                        actions_list = [a.strip() for a in actions_raw.splitlines() if a.strip()]
                        client.record_resolution(
                            token=token,
                            incident_id=inc_id,
                            root_cause=rc,
                            resolution=res_desc,
                            actions=actions_list,
                            is_verified=verify_box,
                        )
                        st.success("Incident marked RESOLVED and synced to Knowledge Base!")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    st.divider()

    # Resolution Card
    if inc.get("confirmed_resolution"):
        st.markdown("### 🎯 Verified Incident Resolution")
        st.success(
            f"**Confirmed Root Cause**: {inc.get('confirmed_root_cause')}\n\n"
            f"**Resolution**: {inc.get('confirmed_resolution')}\n\n"
            f"**Verified By**: `{inc.get('verified_by') or 'Engineer'}` at `{inc.get('verified_at') or inc.get('resolved_at')}`"
        )
        if inc.get("resolution_actions"):
            st.markdown("**Actions Taken**:")
            for a in inc.get("resolution_actions"):
                st.markdown(f"- {a}")

    # Investigation Notes
    st.markdown("### 📝 Investigation Notes")
    notes = inc.get("investigation_notes", [])
    if notes:
        for n in notes:
            st.markdown(f"**`{n.get('user_email')}`** at `{n.get('created_at')}`:")
            st.info(n.get("note"))
    else:
        st.caption("No investigation notes logged yet.")

    if not is_viewer:
        with st.form("add_note_form"):
            new_note = st.text_input("Add Investigation Note", placeholder="e.g. Verified thread dump shows lock contention...")
            if st.form_submit_button("Post Note") and new_note:
                try:
                    client.add_investigation_note(token, inc_id, new_note)
                    st.success("Note added.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    st.divider()

    # Audit Trail
    st.markdown("### 📜 Audit History & Timeline")
    try:
        hist = client.get_incident_history(token, inc_id)
        entries = hist.get("items", [])
        if entries:
            df_hist = pd.DataFrame(entries)[["timestamp", "action", "actor_email", "details"]]
            st.dataframe(df_hist, use_container_width=True)
        else:
            st.caption("No audit history entries recorded.")
    except Exception as e:
        st.warning(f"Could not load audit history: {e}")


def render_ai_rca():
    """Page 4: AI Root-Cause Analysis interface."""
    st.title("🤖 AI Root-Cause Analysis")
    st.caption("Deep-reasoning incident diagnostics grounded on raw telemetry, normalized logs, and historical precedents.")

    token = st.session_state.token
    user = st.session_state.user_info or {}
    role = user.get("role", "viewer")

    inc_id = st.text_input("Incident ID to Analyze", value=st.session_state.selected_incident_id or "")
    if not inc_id:
        st.info("Enter an Incident ID above to run or review AI Root-Cause Analysis.")
        return

    # Trigger RCA
    with st.expander("Trigger New Root-Cause Analysis", expanded=False):
        extra_ctx = st.text_area("Additional Human Context (optional)", placeholder="e.g. Deployed release v2.4.1 10 minutes prior")
        if st.button("Execute AI Root-Cause Analysis", disabled=(role == "viewer")):
            try:
                with st.spinner("Analyzing incident telemetry and historical precedents via Gemini..."):
                    rca_res = client.trigger_rca(token, inc_id, extra_ctx)
                    st.success("Analysis completed!")
            except Exception as e:
                st.error(str(e))

    # Fetch existing analyses
    try:
        with st.spinner("Loading diagnostic history..."):
            analyses_res = client.get_incident_analyses(token, inc_id)
            analyses = analyses_res.get("items", [])
    except Exception as exc:
        st.error(str(exc))
        return

    if not analyses:
        st.info("No AI analyses run yet for this incident. Click 'Execute AI Root-Cause Analysis' above.")
        return

    st.markdown(f"### Found {len(analyses)} Analysis Run(s)")

    # Anti-Hallucination Disclaimer
    st.warning(
        "⚠️ **Diagnostic Notice**: AI diagnoses are probabilistic hypotheses formulated from evidence. "
        "They remain hypotheses until confirmed by an authorized human engineer."
    )

    for idx, rca in enumerate(analyses):
        with st.container():
            conf = rca.get("confidence_level", "LOW")
            ts = rca.get("created_at")
            ana_id = rca.get("analysis_id")

            conf_badge = f'<span class="badge-hypothesis">{conf} CONFIDENCE</span>'
            st.markdown(f"#### Run #{idx+1} ({ana_id}) — {conf_badge} (at `{ts}`)", unsafe_allow_html=True)

            st.markdown(f"**Probable Root Cause**:")
            st.error(rca.get("probable_root_cause"))

            st.markdown(f"**Explanation**:")
            st.write(rca.get("explanation"))

            # Supporting Evidence
            ev = rca.get("supporting_evidence", [])
            if ev:
                st.markdown("**Supporting Evidence (Telemetry Logs)**:")
                for item in ev:
                    st.code(item)

            # Recommended Actions
            rec = rca.get("recommended_actions", [])
            if rec:
                st.markdown("**Recommended Remediation Actions**:")
                for step in rec:
                    st.markdown(f"- [ ] {step}")

            # Precedents Retrieved
            similar = rca.get("similar_incidents", [])
            if similar:
                st.markdown("**Historical Precedents Consulted (RAG)**:")
                for sim in similar:
                    ver_tag = "✓ Verified" if sim.get("has_verified_resolution") else "Unverified Hypothesis"
                    st.markdown(
                        f"- `{sim.get('source_incident_id')}` (Similarity: **{sim.get('similarity_score')}**) — "
                        f"*{sim.get('title')}* [{ver_tag}]"
                    )

            st.divider()


def render_historical_similar_incidents():
    """Page 5: Historical Similar Incidents Explorer."""
    st.title("📚 Historical Precedent Retrieval")
    st.caption("Inspect similar resolved operational precedents retrieved via MongoDB Atlas Vector Search.")

    token = st.session_state.token

    q = st.text_input("Diagnostic Query", placeholder="e.g. Redis timeout under connection starvation")
    c1, c2, c3 = st.columns(3)
    with c1:
        svc = st.text_input("Filter Service (Optional)", placeholder="ALL")
    with c2:
        top_k = st.slider("Top Results", min_value=1, max_value=10, value=3)
    with c3:
        min_sim = st.slider("Min Similarity Score", min_value=0.0, max_value=1.0, value=0.5, step=0.05)

    if st.button("Search Precedents", use_container_width=True) and q:
        try:
            with st.spinner("Searching Atlas Vector Search..."):
                res = client.search_knowledge_base(
                    token=token,
                    query=q,
                    service_name=svc if svc else None,
                    top_k=top_k,
                    min_similarity=min_sim,
                )
                items = res.get("results") or res.get("items", [])
                st.markdown(f"**Retrieved {len(items)} precedent(s)**")

                if not items:
                    st.info("No precedents met the similarity threshold.")
                else:
                    for doc in items:
                        with st.container():
                            is_ver = doc.get("has_verified_resolution")
                            badge = '<span class="badge-verified">✓ Confirmed Resolution</span>' if is_ver else '<span class="badge-hypothesis">AI Hypothesis</span>'
                            st.markdown(
                                f"### `{doc.get('source_incident_id')}` — {doc.get('title')} {badge}",
                                unsafe_allow_html=True,
                            )
                            st.markdown(f"**Similarity Score**: `{doc.get('score')}` | **Service**: `{doc.get('service_name')}` | **Env**: `{doc.get('environment')}`")

                            if doc.get("confirmed_resolution"):
                                st.success(f"**Verified Resolution**: {doc.get('confirmed_resolution')}")
                            elif doc.get("historical_analysis"):
                                st.info(f"**Past AI Hypothesis**: {doc['historical_analysis'].get('probable_root_cause')}")

                            st.divider()
        except Exception as e:
            st.error(str(e))


def render_knowledge_base():
    """Page 6: Knowledge Base management and search."""
    st.title("🧠 Operational Knowledge Base")
    st.caption("Persistent historical resolutions repository empowering RAG incident investigation.")

    token = st.session_state.token

    st.subheader("Semantic Knowledge Search")
    q = st.text_input("Search Knowledge Base", placeholder="e.g. database pool exhaustion, expired certificates")
    if q:
        try:
            with st.spinner("Querying vector index..."):
                res = client.search_knowledge_base(token, query=q, top_k=5, min_similarity=0.40)
                items = res.get("results") or res.get("items", [])
                if not items:
                    st.info("No knowledge base records matched query.")
                for doc in items:
                    with st.expander(f"{doc.get('knowledge_id')} — {doc.get('title')}"):
                        st.markdown(f"**Source Incident**: `{doc.get('source_incident_id')}`")
                        st.markdown(f"**Service**: `{doc.get('service_name')}` | **Environment**: `{doc.get('environment')}`")
                        st.markdown(f"**Diagnostic Summary**: {doc.get('diagnostic_summary')}")
                        if doc.get("confirmed_resolution"):
                            st.success(f"**Verified Resolution**: {doc.get('confirmed_resolution')}")
                        if doc.get("historical_analysis"):
                            st.info(f"**Historical AI Hypothesis**: {doc['historical_analysis'].get('probable_root_cause')}")
        except Exception as e:
            st.error(str(e))


def render_analytics():
    """Page 7: Analytics, MTTA, MTTR, and repeated incident patterns."""
    st.title("📈 DevOps Incident Analytics")
    st.caption("Deep telemetry metrics, MTTA/MTTR resolution velocity, and recurring failure signature detection.")

    token = st.session_state.token
    days = st.slider("Analytics Window (Days)", min_value=7, max_value=90, value=30, step=7)

    try:
        with st.spinner("Computing metrics..."):
            analytics = client.get_analytics(token, days=days)
    except Exception as exc:
        st.error(str(exc))
        return

    # Velocity Cards
    c1, c2, c3, c4 = st.columns(4)
    mtta = analytics.get("mtta_minutes")
    mttr = analytics.get("mttr_minutes")
    c1.metric("Mean Time to Acknowledge (MTTA)", f"{mtta} min" if mtta is not None else "N/A")
    c2.metric("Mean Time to Resolve (MTTR)", f"{mttr} min" if mttr is not None else "N/A")
    c3.metric("Resolution Rate", f"{analytics.get('resolution_rate_pct', 0)}%")
    c4.metric("Total Incidents", analytics.get("total_incidents", 0))

    st.divider()

    # Recurring Failure Signatures
    st.subheader("🔁 Top Recurring Failure Patterns")
    patterns = analytics.get("recurring_patterns", [])
    if patterns:
        df_pat = pd.DataFrame(patterns)[["error_signature", "title", "service_name", "severity", "count"]]
        st.dataframe(df_pat, use_container_width=True)
    else:
        st.info("No recurring error signatures detected.")

    st.divider()

    # Environment & Service Breakdown
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        st.subheader("Incidents by Environment")
        by_env = analytics.get("by_environment", {})
        if by_env:
            st.bar_chart(pd.DataFrame(list(by_env.items()), columns=["Environment", "Count"]).set_index("Environment"))

    with col_e2:
        st.subheader("Severity Distribution")
        by_sev = analytics.get("by_severity", {})
        if by_sev:
            st.bar_chart(pd.DataFrame(list(by_sev.items()), columns=["Severity", "Count"]).set_index("Severity"))


def main():
    if not st.session_state.token:
        render_login()
    else:
        choice = render_sidebar()
        if "1. Dashboard Overview" in choice:
            render_dashboard_overview()
        elif "2. Incidents" in choice:
            render_incidents()
        elif "3. Incident Details" in choice:
            render_incident_details()
        elif "4. AI Root-Cause Analysis" in choice:
            render_ai_rca()
        elif "5. Historical Similar Incidents" in choice:
            render_historical_similar_incidents()
        elif "6. Knowledge Base" in choice:
            render_knowledge_base()
        elif "7. Analytics" in choice:
            render_analytics()


if __name__ == "__main__":
    main()
