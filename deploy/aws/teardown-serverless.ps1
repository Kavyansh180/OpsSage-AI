# ==============================================================================
# OpsSage AI - Serverless Teardown Automation Script
# Deletes all CloudFormation, Lambda, API Gateway, and CloudWatch resources
# ==============================================================================

[CmdletBinding()]
param(
    [string]$Region = "us-east-1",
    [string]$StackName = "opssage-serverless-prod"
)

$ErrorActionPreference = "Stop"

Write-Host "=================================================================" -ForegroundColor Yellow
Write-Host "       OpsSage AI — Serverless Stack Teardown                    " -ForegroundColor Yellow
Write-Host "=================================================================" -ForegroundColor Yellow

$confirmation = Read-Host "Are you sure you want to delete the '$StackName' stack and all associated resources? (y/N)"
if ($confirmation -ne "y" -and $confirmation -ne "Y") {
    Write-Host "Teardown cancelled." -ForegroundColor Cyan
    exit 0
}

Write-Host "`n[1/3] Deleting CloudFormation Stack '$StackName'..." -ForegroundColor Yellow
if (Get-Command "sam" -ErrorAction SilentlyContinue) {
    sam delete --stack-name $StackName --region $Region --no-prompts
} else {
    aws cloudformation delete-stack --stack-name $StackName --region $Region
    Write-Host "Waiting for stack deletion to complete..." -ForegroundColor Yellow
    aws cloudformation wait stack-delete-complete --stack-name $StackName --region $Region
}

Write-Host "`n[2/3] Checking for residual CloudWatch Log Groups..." -ForegroundColor Yellow
$logGroupName = "/aws/lambda/$StackName"
try {
    aws logs delete-log-group --log-group-name $logGroupName --region $Region --error-action SilentlyContinue
    Write-Host "Deleted residual log group: $logGroupName" -ForegroundColor Green
} catch {
    Write-Host "No residual log group found." -ForegroundColor Gray
}

Write-Host "`n[3/3] Checking SSM Parameters..." -ForegroundColor Yellow
Write-Host "SSM Parameters (/opssage/prod/*) were preserved." -ForegroundColor Cyan
Write-Host "To delete SSM parameters manually if needed, run:" -ForegroundColor Gray
Write-Host "  aws ssm delete-parameter --name '/opssage/prod/MONGODB_URI' --region $Region" -ForegroundColor Gray
Write-Host "  aws ssm delete-parameter --name '/opssage/prod/JWT_SECRET_KEY' --region $Region" -ForegroundColor Gray
Write-Host "  aws ssm delete-parameter --name '/opssage/prod/GEMINI_API_KEY' --region $Region" -ForegroundColor Gray

Write-Host "`n=================================================================" -ForegroundColor Green
Write-Host "  Serverless Stack Teardown Complete! (Zero ongoing AWS charges) " -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Green
