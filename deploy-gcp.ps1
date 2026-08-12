<#
.SYNOPSIS
Deploys Kabiero SMS to Google Cloud Run with Cloud SQL PostgreSQL and Secret Manager.

.IMPORTANT
- Do NOT commit this file with real secrets.
- Secrets are stored in Google Secret Manager, not in this script.
- Run this script from an authenticated PowerShell with gcloud installed.

.MANUAL STEPS BEFORE RUNNING
1. Create a Google Cloud project and note the PROJECT_ID.
2. Enable the required APIs (this script can do it, but you must have project editor permissions).
3. Create a Cloud SQL PostgreSQL instance and note the instance connection name (PROJECT:REGION:INSTANCE).
4. Create a database (e.g., kabiero_sms) and user in Cloud SQL.
5. Create secrets in Secret Manager with actual values:
   - SECRET_KEY: a long random string
   - DATABASE_URL: postgresql://USER:PASSWORD@/DB_NAME?host=/cloudsql/PROJECT:REGION:INSTANCE
   - DEFAULT_ADMIN_PASSWORD: a strong password for the bootstrap admin account

.NOTES
- This script does NOT create a Cloud SQL database automatically (marked as separate optional step below).
- This script does NOT create a Django superuser automatically.
- This script DOES deploy the Cloud Run service when you run it.
- After deployment, the script automatically updates ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS with the actual service URL.
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,
    
    [Parameter(Mandatory=$true)]
    [string]$Region,
    
    [Parameter(Mandatory=$true)]
    [string]$CloudSqlInstance,
    
    [Parameter(Mandatory=$true)]
    [string]$CloudSqlDatabase,
    
    [Parameter(Mandatory=$true)]
    [string]$CloudSqlUser,
    
    [Parameter(Mandatory=$true)]
    [string]$ArtifactRepo,
    
    [Parameter(Mandatory=$true)]
    [string]$ImageName,
    
    [Parameter(Mandatory=$true)]
    [string]$CloudRunService,
    
    [Parameter(Mandatory=$false)]
    [string]$DefaultAdminUsername = "admin"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Kabiero SMS - GCP Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# 1. VERIFY GCLOUD IS INSTALLED
# ============================================================
Write-Host "[1/8] Verifying gcloud CLI..." -ForegroundColor Yellow
$gcloudVersion = gcloud --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: gcloud CLI is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Install from: https://cloud.google.com/sdk/docs/install" -ForegroundColor Red
    exit 1
}
Write-Host "gcloud is installed." -ForegroundColor Green
Write-Host ""

# ============================================================
# 2. VERIFY AUTHENTICATION
# ============================================================
Write-Host "[2/8] Verifying authentication..." -ForegroundColor Yellow
$authStatus = gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>&1
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($authStatus)) {
    Write-Host "ERROR: No active gcloud authentication found." -ForegroundColor Red
    Write-Host "Run: gcloud auth login" -ForegroundColor Red
    exit 1
}
Write-Host "Authenticated as: $authStatus" -ForegroundColor Green
Write-Host ""

# ============================================================
# 3. VERIFY/CONFIGURE PROJECT
# ============================================================
Write-Host "[3/8] Configuring project..." -ForegroundColor Yellow
$currentProject = gcloud config get-value project 2>&1
if ($currentProject -ne $ProjectId) {
    Write-Host "Setting project to: $ProjectId" -ForegroundColor Yellow
    gcloud config set project $ProjectId
} else {
    Write-Host "Project already set to: $ProjectId" -ForegroundColor Green
}
Write-Host ""

# ============================================================
# 4. ENABLE REQUIRED APIS
# ============================================================
Write-Host "[4/8] Enabling required APIs..." -ForegroundColor Yellow
$apis = @(
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com"
)

foreach ($api in $apis) {
    Write-Host "  Enabling $api..." -ForegroundColor Gray
    gcloud services enable $api --project=$ProjectId | Out-Null
}
Write-Host "APIs enabled." -ForegroundColor Green
Write-Host ""

# ============================================================
# 5. CREATE ARTIFACT REGISTRY (IF NOT EXISTS)
# ============================================================
Write-Host "[5/8] Setting up Artifact Registry..." -ForegroundColor Yellow
$repoExists = gcloud artifacts repositories describe $ArtifactRepo --location=$Region --format="value(name)" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating Artifact Registry repository: $ArtifactRepo in $Region" -ForegroundColor Yellow
    gcloud artifacts repositories create $ArtifactRepo `
        --repository-format=docker `
        --location=$Region `
        --description="Kabiero SMS Docker images" `
        --project=$ProjectId
} else {
    Write-Host "Artifact Registry repository already exists: $repoExists" -ForegroundColor Green
}

# Configure Docker authentication
Write-Host "Configuring Docker authentication..." -ForegroundColor Gray
gcloud auth configure-docker ${Region}-docker.pkg.dev --quiet | Out-Null
Write-Host ""

# ============================================================
# 6. BUILD AND PUSH DOCKER IMAGE
# ============================================================
Write-Host "[6/8] Building and pushing Docker image..." -ForegroundColor Yellow
$imagePath = "${Region}-docker.pkg.dev/${ProjectId}/${ArtifactRepo}/${ImageName}:latest"
Write-Host "Image: $imagePath" -ForegroundColor Gray

# Build using Cloud Build (recommended for GCP)
Write-Host "Submitting build to Cloud Build..." -ForegroundColor Yellow
gcloud builds submit `
    --tag=$imagePath `
    --project=$ProjectId `
    --region=$Region `
    .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker build failed." -ForegroundColor Red
    exit 1
}
Write-Host "Image built and pushed successfully." -ForegroundColor Green
Write-Host ""

# ============================================================
# 7. VERIFY SECRETS EXIST IN SECRET MANAGER
# ============================================================
Write-Host "[7/8] Verifying secrets in Secret Manager..." -ForegroundColor Yellow
$secrets = @("SECRET_KEY", "DATABASE_URL", "DEFAULT_ADMIN_PASSWORD")
$missingSecrets = @()
foreach ($secret in $secrets) {
    $secretExists = gcloud secrets describe $secret --format="value(name)" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: Secret '$secret' does not exist in Secret Manager." -ForegroundColor Yellow
        Write-Host "  Create it with: gcloud secrets create $secret --replication-policy=automatic" -ForegroundColor Yellow
        Write-Host "  Then add a version: echo -n 'YOUR_VALUE' | gcloud secrets versions add $secret --data-file=-" -ForegroundColor Yellow
        $missingSecrets += $secret
    } else {
        Write-Host "  Secret '$secret' exists." -ForegroundColor Green
    }
}
Write-Host ""

if ($missingSecrets.Count -gt 0) {
    Write-Host "WARNING: The following secrets are missing: $($missingSecrets -join ', ')" -ForegroundColor Yellow
    Write-Host "The deployment will continue, but the service may not function correctly without these secrets." -ForegroundColor Yellow
    $continue = Read-Host "Do you want to continue anyway? (yes/no)"
    if ($continue -ne "yes") {
        Write-Host "Deployment cancelled by user." -ForegroundColor Yellow
        exit 0
    }
    Write-Host ""
}

# ============================================================
# 8. DEPLOY TO CLOUD RUN
# ============================================================
Write-Host "[8/8] Deploying to Cloud Run..." -ForegroundColor Yellow
Write-Host "Service: $CloudRunService" -ForegroundColor Gray
Write-Host "Image: $imagePath" -ForegroundColor Gray
Write-Host "Region: $Region" -ForegroundColor Gray
Write-Host "Cloud SQL: $CloudSqlInstance" -ForegroundColor Gray
Write-Host ""

Write-Host "IMPORTANT: Ensure DATABASE_URL secret contains:" -ForegroundColor Yellow
Write-Host "  postgresql://${CloudSqlUser}:PASSWORD@/${CloudSqlDatabase}?host=/cloudsql/${CloudSqlInstance}" -ForegroundColor Yellow
Write-Host "  (Replace PASSWORD with the actual database user password in Secret Manager)" -ForegroundColor Yellow
Write-Host ""

# Confirm before deploying
$confirm = Read-Host "Do you want to proceed with deployment? (yes/no)"
if ($confirm -ne "yes") {
    Write-Host "Deployment cancelled by user." -ForegroundColor Yellow
    exit 0
}

# Deploy with placeholder ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS
# We will update them after deployment with the actual URL
$placeholderHost = "${CloudRunService}.example.com"

gcloud run deploy $CloudRunService `
    --image=$imagePath `
    --platform=managed `
    --region=$Region `
    --allow-unauthenticated `
    --port=8080 `
    --memory=512Mi `
    --cpu=1 `
    --min-instances=1 `
    --max-instances=10 `
    --set-env-vars=DJANGO_SETTINGS_MODULE=sms_core.settings `
    --set-env-vars=DEBUG=False `
    --set-env-vars=DEFAULT_ADMIN_USERNAME=$DefaultAdminUsername `
    --set-env-vars=ALLOWED_HOSTS=$placeholderHost `
    --set-env-vars=CSRF_TRUSTED_ORIGINS=https://$placeholderHost `
    --set-secrets=SECRET_KEY=SECRET_KEY:latest `
    --set-secrets=DATABASE_URL=DATABASE_URL:latest `
    --set-secrets=DEFAULT_ADMIN_PASSWORD=DEFAULT_ADMIN_PASSWORD:latest `
    --add-cloudsql-instances=$CloudSqlInstance `
    --project=$ProjectId

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Deployment failed." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Initial Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Get the actual service URL
Write-Host "Fetching service URL..." -ForegroundColor Yellow
$serviceUrl = gcloud run services describe $CloudRunService --region=$Region --format="value(status.url)" 2>&1
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($serviceUrl)) {
    Write-Host "WARNING: Could not fetch service URL automatically." -ForegroundColor Yellow
    Write-Host "You must manually update ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS with your Cloud Run URL." -ForegroundColor Yellow
} else {
    Write-Host "Service URL: $serviceUrl" -ForegroundColor Green
    
    # Update ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS with the actual URL
    Write-Host "Updating ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS..." -ForegroundColor Yellow
    gcloud run services update $CloudRunService `
        --region=$Region `
        --update-env-vars=ALLOWED_HOSTS=$serviceUrl `
        --update-env-vars=CSRF_TRUSTED_ORIGINS=https://$serviceUrl `
        --project=$ProjectId
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: Failed to update environment variables." -ForegroundColor Yellow
        Write-Host "You must manually update ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS." -ForegroundColor Yellow
    } else {
        Write-Host "Environment variables updated successfully." -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Service URL: $serviceUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Run migrations using .\gcp-migrate.ps1" -ForegroundColor White
Write-Host "2. Create superuser using .\gcp-createsuperuser.ps1" -ForegroundColor White
Write-Host "3. Set the admin password (see gcp-createsuperuser.ps1 output for instructions)" -ForegroundColor White
Write-Host "4. Visit the URL and log in with the admin credentials." -ForegroundColor White
Write-Host ""
Write-Host "Optional - Create Cloud SQL database (if not already created):" -ForegroundColor Yellow
Write-Host "  gcloud sql databases create $CloudSqlDatabase --instance=$CloudSqlInstance --project=$ProjectId" -ForegroundColor Gray
Write-Host ""
Write-Host "Optional - Run bootstrap_kabiero to seed CBC levels and fee structures:" -ForegroundColor Yellow
Write-Host "  gcloud run jobs create kabiero-bootstrap --image $imagePath --region $Region --add-cloudsql-instances $CloudSqlInstance --set-secrets=SECRET_KEY=SECRET_KEY:latest,DATABASE_URL=DATABASE_URL:latest,DEFAULT_ADMIN_PASSWORD=DEFAULT_ADMIN_PASSWORD:latest --set-env-vars=DJANGO_SETTINGS_MODULE=sms_core.settings,DEBUG=False,DEFAULT_ADMIN_USERNAME=$DefaultAdminUsername --command python --args manage.py,bootstrap_kabiero --project $ProjectId" -ForegroundColor Gray
Write-Host "  gcloud run jobs execute kabiero-bootstrap --region=$Region --project=$ProjectId" -ForegroundColor Gray
