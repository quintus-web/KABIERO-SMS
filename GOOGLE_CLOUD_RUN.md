# Google Cloud Run deployment

Cloud Run containers are temporary. Use PostgreSQL on Cloud SQL; do not use `db.sqlite3` in production.

1. Enable Cloud Run, Cloud Build, Artifact Registry, Secret Manager, and Cloud SQL Admin APIs. Create a PostgreSQL Cloud SQL database and user.
2. Store `SECRET_KEY`, `DATABASE_URL`, and a strong `DEFAULT_ADMIN_PASSWORD` in Secret Manager. The database URL must use the Cloud SQL Unix socket: `postgres://USER:PASSWORD@/DATABASE?host=/cloudsql/PROJECT:REGION:INSTANCE`.
3. Build and deploy (replace `PROJECT_ID`, `REGION`, `INSTANCE`, and `CLOUD_RUN_HOST`):

```powershell
gcloud builds submit --tag gcr.io/PROJECT_ID/kabiero-academy
gcloud run deploy kabiero-academy --image gcr.io/PROJECT_ID/kabiero-academy --region REGION --allow-unauthenticated --add-cloudsql-instances PROJECT_ID:REGION:INSTANCE --set-env-vars "DEFAULT_ADMIN_USERNAME=Kabiero,ALLOWED_HOSTS=CLOUD_RUN_HOST" --set-secrets "SECRET_KEY=SECRET_KEY:latest,DATABASE_URL=DATABASE_URL:latest,DEFAULT_ADMIN_PASSWORD=DEFAULT_ADMIN_PASSWORD:latest"
```

4. Before first use, run migrations and the empty-school bootstrap once. Create a Cloud Run Job from the same image, with the same Cloud SQL and secret settings, then run:

```powershell
python manage.py migrate --noinput
python manage.py bootstrap_kabiero
```

The account is `Kabiero`; use the password stored in Secret Manager, then change it after the first login. When using a custom domain, add it to `ALLOWED_HOSTS` and add its complete `https://` URL to `CSRF_TRUSTED_ORIGINS`.
