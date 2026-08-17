<#
.SYNOPSIS
Loads the bundled Kabiero workbook into the Cloud SQL database used by Cloud Run.

.DESCRIPTION
Deploys a Cloud Run Job using the same image, Cloud SQL connection, and secrets
used by the Kabiero service, then executes the import_xlsx management command.

Use -Replace only when you deliberately want to replace existing school data.
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

    [string]$ArtifactRepo = "kabiero-sms",

    [string]$JobName = "kabiero-import-data",

    [switch]$Replace
)

$ErrorActionPreference = "Stop"

# Docker image
$imagePath = "${Region}-docker.pkg.dev/${ProjectId}/${ArtifactRepo}/${ImageName}:latest"

# Import command
$arguments = "manage.py,import_xlsx,--uniform-admission-numbers"

if ($Replace) {
    $arguments += ",--replace"
}

if ($Replace) {
    $arguments += "--replace"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " KABIERO CLOUD SQL DATA IMPORT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Project:       $ProjectId"
Write-Host "Region:        $Region"
Write-Host "Cloud SQL:     $CloudSqlInstance"
Write-Host "Image:         $imagePath"
Write-Host "Job:           $JobName"
Write-Host "Replace mode:  $Replace"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Make sure gcloud is using the correct project
Write-Host "Setting Google Cloud project..." -ForegroundColor Yellow

gcloud config set project $ProjectId

if ($LASTEXITCODE -ne 0) {
    throw "Could not set Google Cloud project."
}

# Deploy/update the Cloud Run Job
Write-Host ""
Write-Host "Deploying Cloud Run import job..." -ForegroundColor Yellow

gcloud run jobs deploy $JobName `
    --image=$imagePath `
    --region=$Region `
    --project=$ProjectId `
    --set-cloudsql-instances=$CloudSqlInstance `
    --set-secrets="SECRET_KEY=SECRET_KEY:latest,DATABASE_URL=DATABASE_URL:latest" `
    --set-env-vars="DJANGO_SETTINGS_MODULE=sms_core.settings,DEBUG=False" `
    --command=python `
    --args=$arguments

if ($LASTEXITCODE -ne 0) {
    throw "Cloud Run import job could not be deployed."
}

Write-Host ""
Write-Host "Cloud Run import job deployed successfully." -ForegroundColor Green

# Execute the job
Write-Host ""
Write-Host "Starting Cloud SQL data import..." -ForegroundColor Yellow
Write-Host "This may take a few minutes." -ForegroundColor Yellow
Write-Host ""

gcloud run jobs execute $JobName `
    --region=$Region `
    --project=$ProjectId `
    --wait

if ($LASTEXITCODE -ne 0) {
    throw "Cloud Run import job failed. Check the Cloud Run Job logs."
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " IMPORT COMPLETED SUCCESSFULLY" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Kabiero student, staff, balance, and fee data"
Write-Host "has been loaded into Cloud SQL." -ForegroundColor Green
Write-Host ""