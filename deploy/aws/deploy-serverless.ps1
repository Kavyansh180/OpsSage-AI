# ==============================================================================
# OpsSage AI - Serverless Deployment Automation Script
# Deploys FastAPI Lambda Backend + API Gateway HTTP API via AWS SAM
# ==============================================================================

[CmdletBinding()]
param(
    [string]$Region = "us-east-1",
    [string]$StackName = "opssage-serverless-prod",
    [string]$Environment = "prod"
)

$ErrorActionPreference = "Stop"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "       OpsSage AI — AWS Serverless Backend Deployment            " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Check AWS CLI and identity
Write-Host "`n[1/5] Checking AWS Authentication..." -ForegroundColor Yellow
try {
    $identityJson = aws sts get-caller-identity --output json | ConvertFrom-Json
    $accountId = $identityJson.Account
    Write-Host "Authenticated as AWS Account: $accountId in Region: $Region" -ForegroundColor Green
} catch {
    Write-Error "Failed to query AWS caller identity. Please configure credentials with 'aws configure'."
    exit 1
}

# 2. Check AWS SAM CLI
Write-Host "`n[2/5] Checking AWS SAM CLI..." -ForegroundColor Yellow
if (-not (Get-Command "sam" -ErrorAction SilentlyContinue)) {
    Write-Error "AWS SAM CLI is not installed or not in PATH. Please install SAM CLI: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"
    exit 1
}
$samVersion = sam --version
Write-Host "Found: $samVersion" -ForegroundColor Green

# 3. Check SSM Parameters
Write-Host "`n[3/5] Verifying SSM Parameter Store Credentials..." -ForegroundColor Yellow
$parameters = @(
    "/opssage/prod/MONGODB_URI",
    "/opssage/prod/JWT_SECRET_KEY",
    "/opssage/prod/GEMINI_API_KEY"
)

foreach ($param in $parameters) {
    try {
        $null = aws ssm get-parameter --name $param --region $Region --error-action SilentlyContinue
        Write-Host "  [OK] Found parameter: $param" -ForegroundColor Green
    } catch {
        Write-Warning "  [MISSING] Parameter $param not found in SSM Parameter Store."
        Write-Warning "  Please create it with: aws ssm put-parameter --name '$param' --type 'SecureString' --value '<secret>' --region $Region"
    }
}

# 4. Build SAM application
Write-Host "`n[4/5] Building SAM Container Application..." -ForegroundColor Yellow
$templatePath = Join-Path $PSScriptRoot "lambda\template.yaml"
sam build -t $templatePath

if ($LASTEXITCODE -ne 0) {
    Write-Error "SAM build failed. Please inspect build output above."
    exit 1
}

# 5. Deploy SAM Stack
Write-Host "`n[5/5] Deploying CloudFormation Stack via SAM..." -ForegroundColor Yellow
sam deploy `
    --stack-name $StackName `
    --region $Region `
    --capabilities CAPABILITY_IAM `
    --resolve-s3 `
    --resolve-image-repos `
    --parameter-overrides Environment=$Environment

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n=================================================================" -ForegroundColor Green
    Write-Host "  Deployment Succeeded!                                          " -ForegroundColor Green
    Write-Host "=================================================================" -ForegroundColor Green
    
    # Query API Gateway endpoint
    $apiUrl = aws cloudformation describe-stacks `
        --stack-name $StackName `
        --region $Region `
        --query "Stacks[0].Outputs[?OutputKey=='HttpApiUrl'].OutputValue" `
        --output text
        
    Write-Host "API Gateway Base URL: $apiUrl" -ForegroundColor Cyan
    Write-Host "Swagger Docs:         $apiUrl/docs" -ForegroundColor Cyan
    Write-Host "Health Check:         $apiUrl/api/v1/health" -ForegroundColor Cyan
    Write-Host "`nConfigure this URL in your Streamlit Community Cloud app secrets:" -ForegroundColor Yellow
    Write-Host "API_BASE_URL = ""$apiUrl/api/v1""" -ForegroundColor White
} else {
    Write-Error "SAM deployment failed."
    exit 1
}
