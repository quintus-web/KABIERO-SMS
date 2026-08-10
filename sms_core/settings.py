# sms_core/settings.py
import os
from pathlib import Path

import dj_database_url
import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
env_file = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_file):
    environ.Env.read_env(env_file)

SECRET_KEY = env('SECRET_KEY', default='django-insecure-ypx*^vy2-%wj23lotuzn-ngd!jluip-*)^=vhq#%4dzsojhm2v')
DEBUG = env.bool('DEBUG', default=False)

def _csv_env(name, default=''):
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]

RENDER_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '').strip()

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '192.168.1.50']
if RENDER_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_HOSTNAME)
ALLOWED_HOSTS += _csv_env('ALLOWED_HOSTS')
ALLOWED_HOSTS = list(dict.fromkeys(filter(None, ALLOWED_HOSTS)))

CSRF_TRUSTED_ORIGINS = _csv_env('CSRF_TRUSTED_ORIGINS')
if RENDER_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_HOSTNAME}')
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(filter(None, CSRF_TRUSTED_ORIGINS)))

DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', f'sqlite:///{BASE_DIR / "db.sqlite3"}'),
        conn_max_age=0,
    )
}

# Validate DB connections before reuse so a stale/disconnected Postgres
# connection (common on Render's free tier) triggers a reconnect instead of a 500.
CONN_HEALTH_CHECKS = True

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'finance.middleware.RoleAccessMiddleware',
]

ROOT_URLCONF = 'sms_core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sms_core.wsgi.application'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'finance.apps.FinanceConfig',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
# Non-manifest storage keeps the portal available while branding assets are updated.
# WhiteNoise still serves compressed static files in production.
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

LOGIN_URL = '/gateway/login/'
LOGIN_REDIRECT_URL = '/portal/executive-kpis/'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 3600
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SECURE = bool(RENDER_HOSTNAME)
SESSION_COOKIE_SECURE = bool(RENDER_HOSTNAME)
CSRF_COOKIE_SAMESITE = 'None' if RENDER_HOSTNAME else 'Lax'
SESSION_COOKIE_SAMESITE = 'None' if RENDER_HOSTNAME else 'Lax'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'ERROR',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
