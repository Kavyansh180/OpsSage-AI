# Archived: ECS Fargate Task Definitions

These task definition templates (`ecs-backend-task-def.json` and `ecs-frontend-task-def.json`) represent the previous AWS ECS/Fargate architecture.

The project has migrated to a cost-optimized **Hybrid Serverless Architecture**:
- **Backend:** AWS Lambda + FastAPI + Mangum + API Gateway HTTP API (see `deploy/aws/lambda/`).
- **Frontend:** Streamlit Community Cloud (free hosting for `frontend/app.py`).

These templates are retained solely for historical reference.
