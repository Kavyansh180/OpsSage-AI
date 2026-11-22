# OpsSage AI — React + Vite Production Frontend

A high-performance, dark-themed DevOps incident response and autonomous root-cause analysis command center. Rebuilt completely from Streamlit to React 19, Vite, TypeScript, and Tailwind CSS.

---

## 🚀 Key Features Recreated

1. **Enterprise Authentication & RBAC**:
   - JWT-based authentication with dual-tab Sign In and Account Creation.
   - Strict role-based permission rendering (`admin`, `engineer`, `viewer`).
   - Secure token storage with reactive unauthorized event listeners.
2. **Executive Incident Telemetry & Dashboard**:
   - 30-day KPI cards: Total, Open, Acknowledged, Resolved, Critical, and Resolution Rate %.
   - Interactive Recharts visualizations: Incident Volume Area Trend, Severity Breakdown, Microservice Distribution, and Lifecycle Status.
3. **Deterministic Operational Incidents Command Center**:
   - Incident listing with multi-attribute filtering (Status, Severity, Environment, Keyword Search).
   - Instant client-side search across incident title, service name, and error signature hash.
4. **Deep Investigation & Incident Lifecycle Management**:
   - Detail view with error signature hash, first seen/last seen timestamps, and event counts.
   - Interactive engineer actions: Acknowledge (`OPEN` &rarr; `ACKNOWLEDGED`), Assign Engineer, Adjust Severity Rating, and Confirm & Record Resolution.
   - Verified solution badge with knowledge base synchronization.
5. **Gemini-Powered AI Root-Cause Analysis (RCA)**:
   - Dedicated diagnostic command center powered by Google Gemini 3.5 Flash Lite (`gemini-3.5-flash-lite`).
   - Formulated probable root causes, step-by-step failure mechanism narratives, and raw supporting telemetry logs.
   - Recommended remediation checklist and historical RAG precedents consulted.
   - Prominent Anti-Hallucination policy disclaimer.
6. **Historical Precedent Retrieval (RAG Explorer)**:
   - Semantic vector similarity search across 384-dimensional incident embeddings.
   - Microservice filtering, top results slider, and minimum cosine similarity score tuning.
7. **Operational Knowledge Base**:
   - Repository of verified incident resolutions and diagnostic summaries empowering continuous RAG grounding.
8. **DevOps SRE Velocity Analytics**:
   - Mean Time to Acknowledge (MTTA) and Mean Time to Resolve (MTTR).
   - Recurring failure pattern detection grouped by error signature hash.
   - Analytics window selector (7, 14, 30, 60, 90 days).
9. **Log Stream & Batch Ingestion Tester**:
   - Live telemetry viewer with severity level and service filtering.
   - Ingest modal allowing SREs to simulate single or batch error logs to trigger automated incident clustering.

---

## 🛠️ Tech Stack

- **Runtime & Framework**: React 19, TypeScript 5.8
- **Build Tool**: Vite 6+
- **Routing**: React Router v7
- **Styling**: Tailwind CSS v3 (Dark SaaS Theme)
- **Data Visualization**: Recharts
- **Iconography**: Lucide React
- **HTTP Client**: Axios with centralized request/response interceptors
- **Testing**: Vitest, React Testing Library, JSDOM

---

## 📦 Getting Started Locally

### 1. Prerequisites
- Node.js `v20+` or `v22+`
- npm `v10+`

### 2. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Ensure `VITE_API_BASE_URL` points to your active backend (defaults to the deployed AWS production API Gateway):
```env
VITE_API_BASE_URL=https://iulno515v4.execute-api.ap-south-1.amazonaws.com/api/v1
```

### 3. Installation
```bash
cd frontend-react
npm install
```

### 4. Run Development Server
```bash
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### 5. Run Automated Tests
```bash
npm test
```

### 6. Production Build
```bash
npm run build
```
Build output will be generated in `frontend-react/dist/`.

---

## 🌐 Production Deployment

The static assets generated in `dist/` can be deployed to any modern edge hosting service:

- **AWS S3 + CloudFront**:
  ```bash
  aws s3 sync dist/ s3://<your-bucket-name> --delete
  aws cloudfront create-invalidation --distribution-id <id> --paths "/*"
  ```
- **Vercel**:
  ```bash
  npx vercel --prod
  ```
- **Netlify**:
  ```bash
  npx netlify deploy --prod --dir=dist
  ```
