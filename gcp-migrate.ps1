<#
.SYNOPSIS
Creates a Cloud Run Job to run Django migrations for Kabiero SMS.

.DESCRIPTION
This script creates a one-time Cloud Run Job that executes:
    python manage.py migrate --noinput

The job uses Secret Manager for SECRET_KEY and DATABASE_URL.
It does NOT create a superuser or seed data.

.MANUAL STEPS BEFORE RUNNING
1. Ensure the Cloud SQL instance exists.
2. Ensure secrets exist in Secret Manager:
   - SECRET_KEY
   - DATABASE_URL (format: postgresql://USER:PASSWORD@/DB_NAME?host=/cloudsql/PROJECT:REGION:INSTANCE)
3. Note the Cloud Run service region and Cloud SQL instance connection name.
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,
    
    [Parameter(Mandatory=$true)]
    [string]$Region,
    
    [Parameter(Mandatory=$true)]
    [string]$CloudSqlInstance,
    
    [Parameter(Mandatory=$true)]
    [string]$ImageName,
    
    [Parameter(Mandatory=$false)]
    [string]$ArtifactRepo = "kabiero-sms",
    
    [Parameter(Mandatory=$false)]
    [string]$JobName = "kabiero-migrate"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Kabiero SMS - GCP Migration Job" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verify gcloud
Write-Host "[1/3] Verifying gcloud CLI..." -ForegroundColor Yellow
$gcloudVersion = gcloud --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: gcloud CLI is not installed." -ForegroundColor Red
    exit 1
}
Write-Host "gcloud is installed." -ForegroundColor Green
Write-Host ""

# Configure project
Write-Host "[2/3] Configuring project..." -ForegroundColor Yellow
gcloud config set project $ProjectId | Out-Null
Write-Host "Project set to: $ProjectId" -ForegroundColor Green
Write-Host ""

# Construct image path
$imagePath = "${Region}-docker.pkg.dev/${ProjectId}/$(if ($ArtifactRepo) { $ArtifactRepo } else { 'kabiero-sms' })/${ImageName}:latest"

Write-Host "[3/3] Creating Cloud Run Job..." -ForegroundColor Yellow
Write-Host "Job Name: $JobName" -ForegroundColor Gray
Write-Host "Image: $imagePath" -ForegroundColor Gray
Write-Host "Region: $Region" -ForegroundColor Gray
Write-Host "Cloud SQL: $CloudSqlInstance" -ForegroundColor Gray
Write-Host ""

# Create the Cloud Run Job
gcloud run jobs create $JobName `
    --image=$imagePath `
    --platform=managed `
    --region=$Region `
    --add-cloudsql-instances=$CloudSqlInstance `
    --set-secrets=SECRET_KEY=SECRET_KEY:latest `
    --set-secrets=DATABASE_URL=DATABASE_URL:latest `
    --set-env-vars=DJANGO_SETTINGS_MODULE=sms_core.settings `
    --set-env-vars=DEBUG=False `
    --command=python `
    --args=manage.py,migrate,--noinput `
    --project=$ProjectId

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to create Cloud Run Job." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Migration Job Created!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "To run the migration job, execute:" -ForegroundColor Yellow
Write-Host "  gcloud run jobs execute $JobName --region=$Region --project=$ProjectId" -ForegroundColor Cyan
Write-Host ""
Write-Host "To view job execution logs:" -ForegroundColor Yellow
Write-Host "  gcloud logging read 'resource.type=cloud_run_job' --limit=50 --project=$ProjectId" -ForegroundColor Cyan
