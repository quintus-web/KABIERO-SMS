# Google Cloud Run deployment

Cloud Run containers are temporary. Use PostgreSQL on Cloud SQL; do not use `db.sqlite3` in production.

1. Enable Cloud Run, Cloud Build, Artifact Registry, Secret Manager, and Cloud SQL Admin APIs. Create a PostgreSQL Cloud SQL database and user.
2. Store `SECRET_KEY`, `DATABASE_URL`, and a strong `DEFAULT_ADMIN_PASSWORD` in Secret Manager. The database URL must use the Cloud SQL Unix socket: `postgres://USER:PASSWORD@/DATABASE?host=/cloudsql/PROJECT:REGION:INSTANCE`.
3. Build and deploy (replace `PROJECT_ID`, `REGION`, `INSTANCE`, and `CLOUD_RUN_HOST`):

```powershell
gcloud builds submit --tag us-central1-docker.pkg.dev/PROJECT_ID/kabiero-sms/kabiero-sms:latest
gcloud run deploy kabiero-sms --image us-central1-docker.pkg.dev/PROJECT_ID/kabiero-sms/kabiero-sms:latest --region REGION --allow-unauthenticated --add-cloudsql-instances PROJECT_ID:REGION:INSTANCE --set-env-vars "DEFAULT_ADMIN_USERNAME=admin,ALLOWED_HOSTS=CLOUD_RUN_HOST" --set-secrets "SECRET_KEY=SECRET_KEY:latest,DATABASE_URL=DATABASE_URL:latest,DEFAULT_ADMIN_PASSWORD=DEFAULT_ADMIN_PASSWORD:latest"
```

4. Before first use, run migrations, then load the bundled Kabiero workbook into Cloud SQL. Run this from PowerShell after deploying the image:

```powershell
python manage.py migrate --noinput
.\gcp-import-data.ps1 -ProjectId PROJECT_ID -Region REGION -CloudSqlInstance PROJECT:REGION:INSTANCE -ImageName kabiero-sms
```

The import uses `KBA-2026-0001` through `KBA-2026-0295`. Add `-Replace` only to intentionally remove existing school operational data before reloading it.

Create the superuser:

```powershell
python manage.py createsuperuser --noinput --username=admin --email=admin@kabiero.ac.ke
```

Set the password via the Django admin or shell after deployment. When using a custom domain, add it to `ALLOWED_HOSTS` and add its complete `https://` URL to `CSRF_TRUSTED_ORIGINS`.
