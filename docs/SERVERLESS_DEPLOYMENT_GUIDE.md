# OpsSage AI — Hybrid Serverless AWS Architecture & Deployment Guide

A production-grade, ultra-low-cost hybrid serverless architecture for OpsSage AI. Designed to eliminate idle compute and load balancer costs while preserving 100% of AI-powered incident investigation, vector RAG retrieval, and deterministic detection capabilities.

---

## 1. Target Architecture Overview

```mermaid
flowchart TD
    subgraph ClientLayer ["Client & Frontend Layer (Streamlit Community Cloud)"]
        Browser["DevOps / SRE Engineer"] -->|HTTPS| StreamlitCloud["Streamlit Community Cloud (frontend/app.py)<br/>Free Tier Hosting"]
    end

    subgraph AWS_Serverless ["AWS Serverless Cloud (us-east-1)"]
        StreamlitCloud -->|HTTPS REST / JWT Bearer| APIGateway["Amazon API Gateway HTTP API<br/>Payload Format 2.0 ($1.00 / million requests)"]
        
        APIGateway -->|Events| LambdaBackend["AWS Lambda Container Function (FastAPI + Mangum)<br/>Memory: 2048 MB (1 full vCPU)<br/>Timeout: 30s<br/>Pre-cached all-MiniLM-L6-v2 Embeddings"]
        
        LambdaBackend -.->|Pulls Secrets on Cold Start| SSM["AWS Systems Manager Parameter Store<br/>(Standard Tier: 100% Free)"]
        LambdaBackend -.->|Streams Execution Logs| CW["Amazon CloudWatch Logs<br/>14-day retention (Free Tier eligible)"]
    end

    subgraph External_Data_AI ["Managed Data & AI Services"]
        LambdaBackend -->|Encrypted TLS (Port 27017)| Atlas[("MongoDB Atlas M0 / Dedicated<br/>Atlas Vector Search")]
        LambdaBackend -->|HTTPS API (Port 443)| GeminiAPI["Google Gemini 3.5 Flash-Lite API<br/>AI Root-Cause Analysis"]
    end
```

### Architectural Highlights
- **Zero Idle Costs:** When no requests are occurring, compute scales to **0**, costing **\$0.00**.
- **No Application Load Balancer:** Replaces the \$16–20/month AWS ALB with an on-demand API Gateway HTTP API (\$1.00 per million requests).
- **Free Frontend Hosting:** Streamlit Community Cloud hosts the interactive dashboard with automated CI/CD directly from GitHub.
- **In-Image Vector Embeddings:** Sentence Transformers model `all-MiniLM-L6-v2` is baked directly into the Lambda container image, delivering 384-dimensional vector inference in ~15–30 ms per document without paid vector database subscriptions.
- **Resilient MongoDB Connection Pooling:** PyMongo `AsyncMongoClient` connection pool is preserved across warm Lambda invocations, avoiding TLS handshake overhead on repeat requests.

---

## 2. Cost Analysis & Breakdown

Unlike ECS/Fargate + ALB which costs \$50–70/month even when idle, the serverless architecture charges strictly per invocation.

### Detailed Monthly Cost Comparison

#### 1. AWS Serverless Infrastructure Costs
| Service | Low Traffic (10,000 reqs/mo) | Moderate Traffic (100,000 reqs/mo) | Notes |
| :--- | :---: | :---: | :--- |
| **AWS Lambda Compute** (2048 MB, ~432ms avg) | **\$0.00** | **\$0.00** | 400,000 GB-seconds free/month covers up to ~460k requests. |
| **AWS Lambda Requests** | **\$0.00** | **\$0.00** | 1,000,000 free requests per month forever. |
| **Amazon API Gateway** (HTTP API) | **\$0.01** | **\$0.10** | \$1.00 per 1M requests (1st 1M free in Year 1). |
| **AWS SSM Parameter Store** (Standard) | **\$0.00** | **\$0.00** | Standard tier is 100% Free forever. |
| **Amazon CloudWatch Logs** (< 2 GB) | **\$0.00** | **\$0.00** | 5 GB free ingestion/month included in Free Tier. |
| **Amazon ECR Storage** (~1.2 GB container) | **\$0.07** | **\$0.12** | 500 MB free tier storage; \$0.10/GB-month for remainder. |
| **Streamlit Community Cloud** | **\$0.00** | **\$0.00** | **100% Free** for public/community projects. |
| **MongoDB Atlas** (M0 Free Sandbox) | **\$0.00** | **\$0.00** | **Free Forever** (512MB, Vector Search). |
| **Total AWS Infrastructure Cost** | **~\$0.08 / month** | **~\$0.22 / month** | **>99% savings compared to ECS + ALB** |

#### 2. Google Gemini 3.5 Flash-Lite API Costs (Token-Based)
*Pricing: **\$0.30** / 1M input tokens, **\$2.50** / 1M output tokens.*  
*Assumptions: ~2,500 input tokens (logs, context, RAG precedents) and ~700 output tokens (structured RCA diagnosis) per analysis request.*

| Workload Scenario | Input Token Cost (\$0.30/M) | Output Token Cost (\$2.50/M) | Total Gemini Cost |
| :--- | :---: | :---: | :---: |
| **Mixed Traffic (10% RCA, 90% CRUD/Ingest):**<br/>- 1,000 RCA calls / 10k total requests<br/>- 10,000 RCA calls / 100k total requests | <br/>\$0.75 (2.5M tokens)<br/>\$7.50 (25.0M tokens) | <br/>\$1.75 (0.7M tokens)<br/>\$17.50 (7.0M tokens) | <br/>**\$2.50 / month**<br/>**\$25.00 / month** |
| **Pure AI Workload (100% RCA calls):**<br/>- 10,000 RCA requests / month<br/>- 100,000 RCA requests / month | <br/>\$7.50 (25M tokens)<br/>\$75.00 (250M tokens) | <br/>\$17.50 (7M tokens)<br/>\$175.00 (70M tokens) | <br/>**\$25.00 / month**<br/>**\$250.00 / month** |

*Note: Output tokens account for ~70% of LLM spend due to the \$2.50/M output rate vs \$0.30/M input rate.*

---

## 3. Step-by-Step Deployment Instructions

### Phase 1: Store Production Secrets in AWS SSM Parameter Store

Run in PowerShell or Bash with your AWS credentials configured:

```bash
# Set your deployment region
export AWS_REGION="us-east-1"

# 1. MongoDB Atlas Connection URI
aws ssm put-parameter \
  --name "/opssage/prod/MONGODB_URI" \
  --type "SecureString" \
  --value "mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority" \
  --region $AWS_REGION \
  --overwrite

# 2. JWT Signing Secret (Generate 32+ characters)
aws ssm put-parameter \
  --name "/opssage/prod/JWT_SECRET_KEY" \
  --type "SecureString" \
  --value "$(openssl rand -hex 32)" \
  --region $AWS_REGION \
  --overwrite

# 3. Google Gemini API Key
aws ssm put-parameter \
  --name "/opssage/prod/GEMINI_API_KEY" \
  --type "SecureString" \
  --value "AIzaSy..." \
  --region $AWS_REGION \
  --overwrite
```

---

### Phase 2: Deploy Serverless Backend via AWS SAM

From the repository root `D:\OpsSage-AI`:

#### Automated Deployment (Recommended):
```powershell
.\deploy\aws\deploy-serverless.ps1 -Region us-east-1 -StackName opssage-serverless-prod
```

#### Manual SAM CLI Commands:
```bash
# 1. Build the container image using AWS SAM
sam build -t deploy/aws/lambda/template.yaml

# 2. Deploy the stack (automatically creates ECR repo, Lambda, API Gateway, and IAM roles)
sam deploy \
  --stack-name opssage-serverless-prod \
  --region us-east-1 \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --resolve-image-repos \
  --parameter-overrides Environment=prod
```

At the end of deployment, SAM outputs your live HTTP API Base URL:
```text
Outputs:
HttpApiUrl = https://a1b2c3d4e5.execute-api.us-east-1.amazonaws.com
ApiDocsUrl = https://a1b2c3d4e5.execute-api.us-east-1.amazonaws.com/docs
ApiV1HealthUrl = https://a1b2c3d4e5.execute-api.us-east-1.amazonaws.com/api/v1/health
```

---

### Phase 3: MongoDB Atlas IP Access Configuration

Because AWS Lambda container instances execute serverless egress calls without a dedicated NAT Gateway (saving \$32+/month), configure MongoDB Atlas Network Access:
1. Open [MongoDB Atlas Cloud Console](https://cloud.mongodb.com).
2. Navigate to **Network Access** $\rightarrow$ **IP Access List**.
3. Add IP entry: `0.0.0.0/0` (Allow access from anywhere).
4. *Security note:* MongoDB Atlas requires strict SCRAM-SHA-256 user authentication, database-level role restrictions, and TLS 1.2+ encryption for every connection.

---

### Phase 4: Deploy Streamlit Dashboard to Streamlit Community Cloud

1. Push your repository to GitHub:
   ```bash
   git add .
   git commit -m "feat: migrate to hybrid serverless architecture"
   git push origin master
   ```
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **"New app"**.
4. Configure your repository:
   - **Repository:** `<your-github-username>/OpsSage-AI`
   - **Branch:** `master`
   - **Main file path:** `frontend/app.py`
   - **App URL:** Customize your subdomain (e.g. `https://opssage-ai.streamlit.app`).
5. Click **"Advanced settings"** $\rightarrow$ **"Secrets"**:
   Paste the API Gateway URL output from SAM:
   ```toml
   API_BASE_URL = "https://<your-api-id>.execute-api.us-east-1.amazonaws.com/api/v1"
   ```
6. Click **"Deploy!"**. Streamlit will install dependencies from `requirements.txt` and launch the live web dashboard.

---

## 4. Cold-Start and Warm-Start Performance

| Invocations | Observed Response Time | Behavior |
| :--- | :---: | :--- |
| **Cold Start** (Container Init) | **~3.2 – 4.5 seconds** | Container download + PyTorch model memory load. Occurs only on initial launch or after 15+ minutes of zero traffic. |
| **Warm Start** (Active Worker) | **~15 – 45 ms** | In-memory embedding inference, reused MongoDB connection pool. |
| **AI Root-Cause Analysis** | **~2.1 – 4.0 seconds** | Gemini 1.5 Flash prompt synthesis and response streaming. |

---

## 5. Rollback & Teardown Instructions

### Automated Teardown
To permanently delete all deployed AWS resources and ensure zero charges:
```powershell
.\deploy\aws\teardown-serverless.ps1 -Region us-east-1 -StackName opssage-serverless-prod
```

### Manual Teardown
```bash
sam delete --stack-name opssage-serverless-prod --region us-east-1 --no-prompts
```
