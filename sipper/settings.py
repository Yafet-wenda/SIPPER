import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
# Bawaannya mati supaya proses yang dilupakan tanpa DJANGO_DEBUG di lingkungan
# tidak berakhir menyajikan traceback SQL. dev.bat menyetel 1, prod.bat menyetel 0.
DEBUG = os.getenv('DJANGO_DEBUG', '0') == '1'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'sipper-local-development-key-change-this-before-production-2026'
    else:
        # Kunci bawaan terlihat di repository, jadi memakainya saat non-debug
        # berarti cookie sesi dan token CSRF bisa dipalsukan siapa pun yang
        # bisa membaca kode ini. Lebih baik gagal saat start daripada diam-diam
        # berjalan dengan kunci yang sudah diketahui publik.
        raise ImproperlyConfigured(
            'DJANGO_SECRET_KEY belum diisi. Salin .env.example menjadi .env dan isi '
            'DJANGO_SECRET_KEY dengan nilai acak panjang, atau set DJANGO_DEBUG=1 untuk '
            'pengembangan lokal.')
ALLOWED_HOSTS = [host.strip() for host in os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost,testserver').split(',') if host.strip()]
# 'ai_ocr' harus sesudah 'core': modelnya proxy atas core.Dokumen, dan adminnya
# memakai Site + mixin dari core.admin_site. Urutan ini juga yang menentukan
# urutan blok modul di halaman utama admin.
INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'core', 'ai_ocr']
MIDDLEWARE = ['core.middleware.MaxUploadSizeMiddleware', 'django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'sipper.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages', 'core.context_processors.role_flags']}}]
WSGI_APPLICATION = 'sipper.wsgi.application'
DB_ENGINE = os.getenv('DB_ENGINE', 'mysql').strip().lower()

if DB_ENGINE in {'sqlite', 'sqlite3'}:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / os.getenv('DB_NAME', 'sipper.sqlite3'),
        }
    }
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.mysql', 'NAME': os.getenv('DB_NAME', 'sipper_db'), 'USER': os.getenv('DB_USER', 'root'), 'PASSWORD': os.getenv('DB_PASSWORD', ''), 'HOST': os.getenv('DB_HOST', '127.0.0.1'), 'PORT': os.getenv('DB_PORT', '3306'), 'OPTIONS': {'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"}}}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
]
LANGUAGE_CODE = 'id-id'
TIME_ZONE = 'Asia/Jakarta'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
# WhiteNoise: /static/ dilayani proses Django mana pun (runserver tanpa --insecure, waitress).
# CompressedStaticFilesStorage dipilih agar nama file tanpa hash — Alias /static/ Apache tetap sah.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = os.getenv('DJANGO_SECURE_COOKIES', '0' if DEBUG else '1') == '1'
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_SSL_REDIRECT = os.getenv('DJANGO_SECURE_SSL_REDIRECT', '0' if DEBUG else '1') == '1'
SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_HSTS_SECONDS', '0' if DEBUG else '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Test client Django berbicara lewat HTTP polos ke host `testserver`, jadi
# SECURE_SSL_REDIRECT di atas akan mengubah SETIAP permintaan jadi 301 dan
# seluruh suite gagal tanpa ada yang salah secara fungsional. Flag-flag itu
# tetap wajib di produksi (Apache + TLS), jadi pengecualian dibuat sempit:
# hanya untuk proses `manage.py test`, bukan untuk runserver atau waitress.
MENJALANKAN_TEST = len(sys.argv) > 1 and sys.argv[1] == 'test'
if MENJALANKAN_TEST:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# Mode pengembangan (DJANGO_DEBUG=1): tiga flag TLS dimatikan berapa pun isi
# .env, supaya `runserver` polos tetap bisa dibuka lewat http://127.0.0.1:8000.
# Produksi tetap ketat: prod.bat memaksa DJANGO_DEBUG=0 sebelum waitress mulai,
# sehingga blok ini tidak pernah menyentuh bentuk produksi.
if DEBUG:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if origin.strip()]
EMAIL_BACKEND = os.getenv('DJANGO_EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('DJANGO_EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('DJANGO_EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('DJANGO_EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('DJANGO_EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('DJANGO_EMAIL_USE_TLS', '1') == '1'
# Tanpa batas waktu, send_mail ikut menunggu sampai OS menyerah (menit) ketika
# SMTP mati atau DNS menggantung, dan petugas yang menekan tombol verifikasi
# melihat layarnya membeku.
EMAIL_TIMEOUT = int(os.getenv('DJANGO_EMAIL_TIMEOUT', '10'))
EMAIL_FILE_PATH = BASE_DIR / os.getenv('DJANGO_EMAIL_FILE_PATH', 'tmp/outbox')
DEFAULT_FROM_EMAIL = os.getenv('DJANGO_DEFAULT_FROM_EMAIL', 'SIPPER <no-reply@example.com>')
CLAMAV_ENABLED = os.getenv('CLAMAV_ENABLED', '0') == '1'
CLAMAV_HOST = os.getenv('CLAMAV_HOST', '127.0.0.1')
CLAMAV_PORT = int(os.getenv('CLAMAV_PORT', '3310'))
# Kejadian yang tidak lagi berhenti sebagai baris AuditLog saja. Semua jalur
# kegagalan (OCR, ClamAV, pemotretan pasfoto) menulis ke log proses supaya
# penyebab aslinya masih terbaca di jendela waitress saat petugas hanya
# melihat "proses gagal". Level root sengaja WARNING agar log tidak membengkak.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'ringkas': {'format': '{levelname} {asctime} {name}: {message}', 'style': '{'}},
    'handlers': {'konsol': {'class': 'logging.StreamHandler', 'formatter': 'ringkas'}},
    'root': {'handlers': ['konsol'], 'level': 'WARNING'},
    'loggers': {
        'core': {'handlers': ['konsol'], 'level': 'INFO', 'propagate': False},
        'django.security': {'handlers': ['konsol'], 'level': 'WARNING', 'propagate': False},
    },
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
