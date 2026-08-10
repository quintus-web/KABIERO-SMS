FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput --skip-checks
CMD exec gunicorn sms_core.wsgi:application --bind 0.0.0.0:${PORT} --workers 2 --access-logfile - --error-logfile -
