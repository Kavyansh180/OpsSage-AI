# OpsSage AI — AWS Production Deployment Guide

A cost-conscious, production-ready AWS deployment architecture for OpsSage AI. Designed specifically for portfolio projects, tech demos, and lean production teams.

---

## 1. Target Architecture Overview

```mermaid
flowchart TD
    Client["Client Browser / DevOps Engineer"] -->|HTTPS / HTTP Port 80/443| ALB["AWS Application Load Balancer"]
    
    subgraph VPC ["AWS Virtual Private Cloud (VPC)"]
        subgraph PublicSubnets ["Public Subnets (AZ-a & AZ-b)"]
            ALB
        end
        
        subgraph PrivateSubnets ["Private Subnets (or Fargate Public IP w/ SG)"]
            FrontendTask["ECS Fargate Task: Streamlit Frontend (0.5 vCPU / 1GB RAM) Port 8501"]
            BackendTask["ECS Fargate Task: FastAPI Backend (1.0 vCPU / 2GB RAM) Port 8000"]
        end
        
        CW["Amazon CloudWatch Logs"]
        SSM["AWS Systems Manager Parameter Store"]
    end
    
    ALB -->|Path: /api/*| BackendTask
    ALB -->|Path: /* (Default)| FrontendTask
    FrontendTask -.->|Internal API calls| BackendTask
    
    BackendTask -->|Encrypted TLS (Port 27017)| Atlas[("MongoDB Atlas M0 / Dedicated")]
    BackendTask -->|HTTPS API (Port 443)| Gemini["Google Gemini API (gemini-3.5-flash-lite)"]
    BackendTask -.->|Pulls Secrets at Launch| SSM
    BackendTask -.->|Streams Logs| CW
    FrontendTask -.->|Streams Logs| CW
```

### Architecture Highlights
1. **Serverless Compute (ECS Fargate):** No EC2 instances to patch, monitor, or pay for idle capacity.
2. **Single Application Load Balancer (Path-Based Routing):**
   - Forward `/api/*` traffic to the FastAPI backend Target Group (Port 8000).
   - Forward all other traffic `/*` to the Streamlit frontend Target Group (Port 8501).
   - Saves ~$16-20/month compared to running two separate load balancers.
3. **External Managed Data Stores:**
   - **MongoDB Atlas:** Free M0 sandbox cluster or dedicated cluster with encrypted TLS connection.
   - **Google Gemini 1.5 Flash:** Managed AI root-cause analysis.
   - **Sentence Transformers (In-Process):** Pre-downloaded inside the backend image; zero external vector DB subscription costs required.
4. **AWS Systems Manager (SSM) Parameter Store:** Standard tier is 100% free (saving \$0.40/secret/month over AWS Secrets Manager).

---

## 2. Prerequisites

1. **AWS CLI v2** installed and configured:
   ```bash
   aws configure
   ```
2. **Docker** installed locally or access to GitHub Actions.
3. **MongoDB Atlas Cluster** accessible over the internet with IP Access list configured.
4. **Google Gemini API Key**.
5. Set common deployment variables in your terminal:
   ```bash
   export AWS_REGION="us-east-1"
   export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
   export PROJECT_NAME="opssage"
   ```

---

## 3. Step-by-Step Deployment Instructions

### Step 3.1: Create Amazon ECR Repositories

Create private container repositories for backend and frontend images:

```bash
# Backend repository
aws ecr create-repository \
  --repository-name opssage-backend \
  --image-scanning-configuration scanOnPush=true \
  --region $AWS_REGION

# Frontend repository
aws ecr create-repository \
  --repository-name opssage-frontend \
  --image-scanning-configuration scanOnPush=true \
  --region $AWS_REGION
```

### Step 3.2: Build and Push Docker Images to ECR

```bash
# Authenticate Docker to your Amazon ECR registry
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# 1. Build and push backend image
docker build -f Dockerfile.backend -t opssage-backend:latest .
docker tag opssage-backend:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/opssage-backend:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/opssage-backend:latest

# 2. Build and push frontend image
docker build -f Dockerfile.frontend -t opssage-frontend:latest .
docker tag opssage-frontend:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/opssage-frontend:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/opssage-frontend:latest
```

---

### Step 3.3: Store Secrets in SSM Parameter Store (Free Tier)

Store production credentials securely as `SecureString` parameters:

```bash
# 1. MongoDB Atlas Connection URI
aws ssm put-parameter \
  --name "/opssage/prod/MONGODB_URI" \
  --type "SecureString" \
  --value "mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority" \
  --overwrite

# 2. JWT Signing Secret (Generate 32+ characters)
aws ssm put-parameter \
  --name "/opssage/prod/JWT_SECRET_KEY" \
  --type "SecureString" \
  --value "$(openssl rand -hex 32)" \
  --overwrite

# 3. Google Gemini API Key
aws ssm put-parameter \
  --name "/opssage/prod/GEMINI_API_KEY" \
  --type "SecureString" \
  --value "AIzaSy..." \
  --overwrite
```

---

### Step 3.4: Configure IAM Roles for ECS Fargate

Create the ECS execution role and grant it permission to read SSM parameters:

```bash
# 1. Create Trust Policy document
cat <<EOF > /tmp/ecs-trust-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ecs-tasks.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# 2. Create Execution Role
aws iam create-role \
  --role-name opssage-ecs-execution-role \
  --assume-role-policy-document file:///tmp/ecs-trust-policy.json

# 3. Attach standard AWS execution role policy
aws iam attach-role-policy \
  --role-name opssage-ecs-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# 4. Attach SSM Parameter Store decryption policy
cat <<EOF > /tmp/ssm-decrypt-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameters",
        "ssm:GetParameter"
      ],
      "Resource": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/opssage/prod/*"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name opssage-ecs-execution-role \
  --policy-name OpsSageSSMReadPolicy \
  --policy-document file:///tmp/ssm-decrypt-policy.json
```

---

### Step 3.5: Configure Networking & Security Groups

```bash
# Get Default VPC ID and Subnets
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text)
SUBNET_1=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query "Subnets[0].SubnetId" --output text)
SUBNET_2=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query "Subnets[1].SubnetId" --output text)

# 1. Create ALB Security Group (Allows Inbound HTTP on Port 80)
ALB_SG=$(aws ec2 create-security-group \
  --group-name opssage-alb-sg \
  --description "Security group for OpsSage ALB" \
  --vpc-id $VPC_ID \
  --query "GroupId" --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $ALB_SG \
  --protocol tcp --port 80 --cidr 0.0.0.0/0

# 2. Create ECS Task Security Group (Allows traffic only from ALB)
ECS_SG=$(aws ec2 create-security-group \
  --group-name opssage-ecs-sg \
  --description "Security group for OpsSage ECS containers" \
  --vpc-id $VPC_ID \
  --query "GroupId" --output text)

# Inbound 8000 (Backend) from ALB SG
aws ec2 authorize-security-group-ingress \
  --group-id $ECS_SG \
  --protocol tcp --port 8000 --source-group $ALB_SG

# Inbound 8501 (Frontend) from ALB SG
aws ec2 authorize-security-group-ingress \
  --group-id $ECS_SG \
  --protocol tcp --port 8501 --source-group $ALB_SG
```

---

### Step 3.6: Create Application Load Balancer & Target Groups

```bash
# 1. Create ALB
ALB_ARN=$(aws elbv2 create-load-balancer \
  --name opssage-alb \
  --subnets $SUBNET_1 $SUBNET_2 \
  --security-groups $ALB_SG \
  --query "LoadBalancers[0].LoadBalancerArn" --output text)

ALB_DNS=$(aws elbv2 describe-load-balancers \
  --load-balancer-arns $ALB_ARN \
  --query "LoadBalancers[0].DNSName" --output text)

echo "Application Load Balancer DNS: $ALB_DNS"

# 2. Create Frontend Target Group (Port 8501, Health check /_stcore/health)
TG_FRONTEND_ARN=$(aws elbv2 create-target-group \
  --name opssage-frontend-tg \
  --protocol HTTP \
  --port 8501 \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path /_stcore/health \
  --query "TargetGroups[0].TargetGroupArn" --output text)

# 3. Create Backend Target Group (Port 8000, Health check /api/v1/health)
TG_BACKEND_ARN=$(aws elbv2 create-target-group \
  --name opssage-backend-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path /api/v1/health \
  --query "TargetGroups[0].TargetGroupArn" --output text)

# 4. Create ALB Listener on Port 80 (Default route -> Frontend)
LISTENER_ARN=$(aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=$TG_FRONTEND_ARN \
  --query "Listeners[0].ListenerArn" --output text)

# 5. Add Path Rule for /api/* -> Backend
aws elbv2 create-rule \
  --listener-arn $LISTENER_ARN \
  --priority 10 \
  --conditions Field=path-pattern,Values='/api/*' \
  --actions Type=forward,TargetGroupArn=$TG_BACKEND_ARN
```

---

### Step 3.7: Register ECS Task Definitions & Create Services

```bash
# 1. Create ECS Cluster
aws ecs create-cluster --cluster-name opssage-cluster

# 2. Register Backend Task Definition (replacing account ID & region placeholders)
sed -e "s/<AWS_ACCOUNT_ID>/$AWS_ACCOUNT_ID/g" \
    -e "s/<AWS_REGION>/$AWS_REGION/g" \
    deploy/aws/ecs-backend-task-def.json > /tmp/backend-def.json

aws ecs register-task-definition --cli-input-json file:///tmp/backend-def.json

# 3. Register Frontend Task Definition
sed -e "s/<AWS_ACCOUNT_ID>/$AWS_ACCOUNT_ID/g" \
    -e "s/<AWS_REGION>/$AWS_REGION/g" \
    -e "s/<ALB_DNS_OR_SERVICE_NAME>/$ALB_DNS/g" \
    deploy/aws/ecs-frontend-task-def.json > /tmp/frontend-def.json

aws ecs register-task-definition --cli-input-json file:///tmp/frontend-def.json

# 4. Create Backend ECS Service
aws ecs create-service \
  --cluster opssage-cluster \
  --service-name opssage-backend-service \
  --task-definition opssage-backend \
  --launch-type FARGATE \
  --desired-count 1 \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_1,$SUBNET_2],securityGroups=[$ECS_SG],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=$TG_BACKEND_ARN,containerName=backend,containerPort=8000"

# 5. Create Frontend ECS Service
aws ecs create-service \
  --cluster opssage-cluster \
  --service-name opssage-frontend-service \
  --task-definition opssage-frontend \
  --launch-type FARGATE \
  --desired-count 1 \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_1,$SUBNET_2],securityGroups=[$ECS_SG],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=$TG_FRONTEND_ARN,containerName=frontend,containerPort=8501"
```

---

## 4. Cost Breakdown (Monthly Estimate)

| Service | Configuration | Monthly Cost (USD) | Notes |
| :--- | :--- | :--- | :--- |
| **AWS ECS Fargate (Backend)** | 1.0 vCPU, 2GB RAM (1 Task, 730 hrs) | \$35.80 | Model inference memory requirement |
| **AWS ECS Fargate (Frontend)** | 0.5 vCPU, 1GB RAM (1 Task, 730 hrs) | \$17.90 | Streamlit dashboard UI |
| **Application Load Balancer** | 1 ALB (Path-based routing) | \$16.20 | Single ALB routes `/api/*` and `/*` |
| **Amazon ECR** | ~2 GB container images | \$0.20 | $0.10/GB-month storage |
| **AWS SSM Parameter Store** | Standard tier (3 parameters) | \$0.00 | **100% Free** |
| **Amazon CloudWatch** | Up to 5 GB ingestion & logs | \$0.00 | Included in AWS Free Tier |
| **MongoDB Atlas** | M0 Sandbox Cluster | \$0.00 | **Free Forever** tier (512MB, Vector Search) |
| **Google Gemini API** | `gemini-3.5-flash-lite` | ~\$2.50 | \$0.30/M in, \$2.50/M out |
| **Total Estimated Cost** | Running 24/7 | **~\$70.60 / month** | |

### Cost Minimization Tips (Portfolio & Freshers)
1. **Fargate Spot (Save up to 70%):** Switch ECS launch type to `FARGATE_SPOT` to drop the ECS compute bill from \$53/month down to **~\$16/month**.
2. **Scheduled Scaling to Zero (Save 65%):** Use AWS Application Auto Scaling to scale tasks to `desired-count=0` during night hours (e.g. 10 PM to 8 AM) and weekends when not demoing.
3. **Delete ALB When Inactive (Save \$16/month):** If not actively demoing the live web address, delete the ALB. You can run ECS tasks with a public IP directly.

---

## 5. Rollback Procedure

If a bad deployment occurs, revert immediately to the previous task definition revision without downtime:

```bash
# 1. Inspect existing revisions
aws ecs list-task-definitions --family-prefix opssage-backend

# 2. Update service to previous known-good revision (e.g. revision 1)
aws ecs update-service \
  --cluster opssage-cluster \
  --service opssage-backend-service \
  --task-definition opssage-backend:1 \
  --force-new-deployment

# 3. Monitor deployment status until rolled out
aws ecs wait services-stable \
  --cluster opssage-cluster \
  --services opssage-backend-service
```

---

## 6. Teardown Instructions (Zero Ongoing Charges)

Run the following commands in order to completely delete all deployed AWS resources and prevent unexpected billing:

```bash
# 1. Scale down and delete ECS services
aws ecs update-service --cluster opssage-cluster --service opssage-frontend-service --desired-count 0
aws ecs update-service --cluster opssage-cluster --service opssage-backend-service --desired-count 0
aws ecs delete-service --cluster opssage-cluster --service opssage-frontend-service --force
aws ecs delete-service --cluster opssage-cluster --service opssage-backend-service --force

# 2. Delete ECS cluster
aws ecs delete-cluster --cluster opssage-cluster

# 3. Delete Application Load Balancer, Listener, and Target Groups
aws elbv2 delete-listener --listener-arn $LISTENER_ARN
aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN
# Wait 30 seconds for ALB network interfaces to release before deleting target groups
sleep 30
aws elbv2 delete-target-group --target-group-arn $TG_FRONTEND_ARN
aws elbv2 delete-target-group --target-group-arn $TG_BACKEND_ARN

# 4. Delete Security Groups
aws ec2 delete-security-group --group-id $ECS_SG
aws ec2 delete-security-group --group-id $ALB_SG

# 5. Delete ECR Repositories and all container images
aws ecr delete-repository --repository-name opssage-backend --force
aws ecr delete-repository --repository-name opssage-frontend --force

# 6. Delete SSM Parameters
aws ssm delete-parameter --name "/opssage/prod/MONGODB_URI"
aws ssm delete-parameter --name "/opssage/prod/JWT_SECRET_KEY"
aws ssm delete-parameter --name "/opssage/prod/GEMINI_API_KEY"

# 7. Delete IAM Role & Policies
aws iam delete-role-policy --role-name opssage-ecs-execution-role --policy-name OpsSageSSMReadPolicy
aws iam detach-role-policy --role-name opssage-ecs-execution-role --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
aws iam delete-role --role-name opssage-ecs-execution-role

echo "All OpsSage AI AWS resources have been successfully deleted. Balance is safe."
```
