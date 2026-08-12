<#
.SYNOPSIS
Creates a Django superuser for Kabiero SMS on Google Cloud Run.

.DESCRIPTION
This script creates a Cloud Run Job that executes:
    python manage.py createsuperuser --noinput --username=admin --email=admin@kabiero.ac.ke

The user is created without a usable password. You must set the password
separately after the user is created (see instructions below).

.MANUAL STEPS BEFORE RUNNING
1. Ensure the Cloud SQL instance exists.
2. Ensure secrets exist in Secret Manager:
   - SECRET_KEY
   - DATABASE_URL
3. Ensure migrations have been run (use gcp-migrate.ps1 first).
4. Note the Cloud Run service region and Cloud SQL instance connection name.

.IMPORTANT
- This script does NOT store any passwords.
- After running this script, you MUST set the admin password manually.
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
    [string]$JobName = "kabiero-createsuperuser",
    
    [Parameter(Mandatory=$true)]
    [string]$DefaultAdminUsername
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Kabiero SMS - Create Superuser" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verify gcloud
Write-Host "[1/4] Verifying gcloud CLI..." -ForegroundColor Yellow
$gcloudVersion = gcloud --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: gcloud CLI is not installed." -ForegroundColor Red
    exit 1
}
Write-Host "gcloud is installed." -ForegroundColor Green
Write-Host ""

# Configure project
Write-Host "[2/4] Configuring project..." -ForegroundColor Yellow
gcloud config set project $ProjectId | Out-Null
Write-Host "Project set to: $ProjectId" -ForegroundColor Green
Write-Host ""

# Construct image path
$imagePath = "${Region}-docker.pkg.dev/${ProjectId}/${ArtifactRepo}/${ImageName}:latest"

Write-Host "[3/4] Creating Cloud Run Job..." -ForegroundColor Yellow
Write-Host "Job Name: $JobName" -ForegroundColor Gray
Write-Host "Image: $imagePath" -ForegroundColor Gray
Write-Host "Region: $Region" -ForegroundColor Gray
Write-Host "Cloud SQL: $CloudSqlInstance" -ForegroundColor Gray
Write-Host "Username: $DefaultAdminUsername" -ForegroundColor Gray
Write-Host ""

# Create the Cloud Run Job for createsuperuser
gcloud run jobs create $JobName `
    --image=$imagePath `
    --platform=managed `
    --region=$Region `
    --add-cloudsql-instances=$CloudSqlInstance `
    --set-secrets=SECRET_KEY=SECRET_KEY:latest `
    --set-secrets=DATABASE_URL=DATABASE_URL:latest `
    --set-secrets=DEFAULT_ADMIN_PASSWORD=DEFAULT_ADMIN_PASSWORD:latest `
    --set-env-vars=DJANGO_SETTINGS_MODULE=sms_core.settings `
    --set-env-vars=DEBUG=False `
    --set-env-vars=DEFAULT_ADMIN_USERNAME=$DefaultAdminUsername `
    --command=python `
    --args=manage.py,createsuperuser,--noinput,--username=$DefaultAdminUsername,--email=admin@kabiero.ac.ke `
    --project=$ProjectId

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to create Cloud Run Job." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Superuser Job Created!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Ask if user wants to run it now
$runNow = Read-Host "Do you want to execute the superuser creation job now? (yes/no)"
if ($runNow -eq "yes") {
    Write-Host "Executing job..." -ForegroundColor Yellow
    gcloud run jobs execute $JobName --region=$Region --project=$ProjectId
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Job execution failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "Job executed successfully." -ForegroundColor Green
} else {
    Write-Host "Job created but not executed." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " IMPORTANT: Set the Admin Password" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "The superuser was created WITHOUT a usable password." -ForegroundColor Yellow
Write-Host "You must set the password using ONE of the following methods:" -ForegroundColor Yellow
Write-Host ""
Write-Host "Method 1 - Django Admin Shell (recommended):" -ForegroundColor White
Write-Host "  gcloud run jobs create kabiero-shell --image $imagePath --region $Region --add-cloudsql-instances $CloudSqlInstance --set-secrets=SECRET_KEY=SECRET_KEY:latest,DATABASE_URL=DATABASE_URL:latest --set-env-vars=DJANGO_SETTINGS_MODULE=sms_core.settings,DEBUG=False --command python --args manage.py,shell,-c,\"from django.contrib.auth import get_user_model; u=get_user_model().objects.get(username='$DefaultAdminUsername'); u.set_password('YOUR_NEW_PASSWORD'); u.save()\" --project $ProjectId" -ForegroundColor Gray
Write-Host ""
Write-Host "Method 2 - Django changepassword command:" -ForegroundColor White
Write-Host "  gcloud run jobs create kabiero-changepass --image $imagePath --region $Region --add-cloudsql-instances $CloudSqlInstance --set-secrets=SECRET_KEY=SECRET_KEY:latest,DATABASE_URL=DATABASE_URL:latest --set-env-vars=DJANGO_SETTINGS_MODULE=sms_core.settings,DEBUG=False --command python --args manage.py,changepassword,$DefaultAdminUsername --project $ProjectId" -ForegroundColor Gray
Write-Host ""
Write-Host "Replace YOUR_NEW_PASSWORD with a strong password of your choice." -ForegroundColor Yellow
Write-Host "Do NOT store the password in any script or Git repository." -ForegroundColor Red
