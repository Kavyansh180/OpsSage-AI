# OpsSage AI — Serverless Backend Deployment (AWS Lambda + SAM)

This directory contains the AWS Serverless Application Model (SAM) configuration for deploying the OpsSage AI backend as a containerized Lambda function behind Amazon API Gateway HTTP API.

---

## Architecture Overview

```
Streamlit Community Cloud (Frontend)
             │
             ▼  HTTPS
  Amazon API Gateway HTTP API ($1.00/M requests)
             │  (Payload Format 2.0)
             ▼
  AWS Lambda Container (2048 MB, 30s timeout)
             │
      FastAPI + Mangum
             ├── MongoDB Atlas (native AsyncMongoClient, pooled)
             ├── Sentence Transformers (all-MiniLM-L6-v2, pre-cached)
             └── Google Gemini 1.5 Flash (AI RCA Engine)
```

---

## Key Serverless Design Decisions

1. **Lambda Container Image:**
   - Sentence Transformers and PyTorch require ~1.5 GB uncompressed, exceeding the 250 MB zip limit.
   - Using a Lambda container image (`public.ecr.aws/lambda/python:3.10`) supports up to 10 GB images.
   - The model `sentence-transformers/all-MiniLM-L6-v2` is downloaded into the image during `docker build`, eliminating runtime network latency on cold starts.
2. **2048 MB Memory Allocation:**
   - Allocating 2048 MB provides 1 full vCPU, allowing embedding vector generation in ~15–30 ms per document.
3. **Database Connection Reuse:**
   - Native asynchronous PyMongo `AsyncMongoClient` reuses connection sockets across warm invocations.
   - `minPoolSize=0` and `maxPoolSize=5` prevent socket accumulation when Lambdas freeze.
   - `maxIdleTimeMS=30000` automatically discards stale connections.
4. **Secrets via SSM Parameter Store:**
   - Credentials (`MONGODB_URI`, `JWT_SECRET_KEY`, `GEMINI_API_KEY`) are stored in AWS Systems Manager Parameter Store as `SecureString` (free standard tier).
   - Zero plaintext secrets in code or CloudFormation templates.

---

## Local Build & Test Instructions

### Prerequisites
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) installed.
- Docker Desktop or Docker Engine running.

### 1. Build Container Image
From the repository root:
```bash
sam build -t deploy/aws/lambda/template.yaml
```

### 2. Test API Locally
```bash
sam local start-api --port 8000
```
Then query:
```bash
curl http://localhost:8000/api/v1/health
```

---

## Production Deployment

Refer to [docs/SERVERLESS_DEPLOYMENT_GUIDE.md](../../../docs/SERVERLESS_DEPLOYMENT_GUIDE.md) or run the automated deployment script:
```powershell
.\deploy\aws\deploy-serverless.ps1
```
