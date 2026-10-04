## Status Implementasi Workspace

Workspace saat ini menjalankan satu aplikasi Django `core` dengan MariaDB bawaan XAMPP (10.4) di port 3306; `sipper/__init__.py` memuat shim agar Django 5.2 menerima MariaDB 10.4. Migration dijalankan langsung dari PowerShell.

Untuk deployment:

1. Salin `.env.example` menjadi `.env` dan ganti seluruh password/secret placeholder.
2. Pastikan `DJANGO_ALLOWED_HOSTS` dan `DJANGO_CSRF_TRUSTED_ORIGINS` memakai domain HTTPS aktual.
3. TLS harus diterminasi oleh reverse proxy dengan sertifikat yang valid sebelum mengaktifkan `DJANGO_SECURE_SSL_REDIRECT=1`.
4. Pantau `GET /health/` dan jadwalkan `py manage.py backup_db`.

Custom user model penuh belum diterapkan agar migrasi tidak merusak user database existing; role aplikasi memakai `UserRole` dan tetap kompatibel dengan `is_staff`.

Gunakan `py manage.py promote_officer <username>` untuk memberi role petugas pada akun existing. Migrasi ke custom user model penuh harus dilakukan sebagai proyek migrasi terpisah dengan backup dan database staging.

ClamAV bersifat opsional. Untuk development lokal tanpa ClamAV, biarkan `CLAMAV_ENABLED=0`.
# SIPPER - Setup, Testing & Deployment Guide

---

## 📦 Instalasi Lengkap Step-by-Step

### Phase 1: Environment Setup (Windows)

#### 1.1 Install Python & MySQL

```bash
# Verify Python installation
python --version  # Should be 3.10 or higher

# Verify MySQL installation
mysql --version
```

#### 1.2 Create Project Directory

```bash
# Create and navigate to project directory
mkdir C:\Projects\sipper-app
cd C:\Projects\sipper-app

# Initialize git repository
git init
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

#### 1.3 Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# You should see (venv) prefix in command line
# If not working, try: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### 1.4 Install Dependencies

```bash
# Upgrade pip
python -m pip install --upgrade pip

# Create requirements.txt
echo # Add content below to requirements.txt

# Install all packages
pip install -r requirements.txt

# Verify installations
pip list
```

#### 1.5 Create Django Project Structure

```bash
# Create Django project
django-admin startproject sipper_config .

# Create main apps
python manage.py startapp core
python manage.py startapp users
python manage.py startapp perantau
python manage.py startapp verifikasi
python manage.py startapp kartu

# Create directories
mkdir media
mkdir media\dokumen
mkdir media\qr_codes
mkdir media\avatars
mkdir static
mkdir static\css
mkdir static\js
mkdir static\img
mkdir templates
mkdir logs
mkdir docs
```

---

## 🗄️ Database Setup

### 2.1 MySQL Configuration

```sql
-- Login to MySQL
mysql -u root -p

-- Create database
CREATE DATABASE sipper_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user
CREATE USER 'sipper_user'@'localhost' IDENTIFIED BY 'strong_password_123';

-- Grant privileges
GRANT ALL PRIVILEGES ON sipper_db.* TO 'sipper_user'@'localhost';

-- Flush privileges
FLUSH PRIVILEGES;

-- Verify
SELECT User, Host FROM mysql.user WHERE User='sipper_user';

-- Exit MySQL
EXIT;
```

### 2.2 Django Database Configuration

Create `.env` file in project root:

```env
# Django Settings
SECRET_KEY=django-insecure-your-secret-key-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration
DB_ENGINE=django.db.backends.mysql
DB_NAME=sipper_db
DB_USER=sipper_user
DB_PASSWORD=strong_password_123
DB_HOST=localhost
DB_PORT=3306

# Email Configuration (optional)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# AI Services
OPENAI_API_KEY=
GOOGLE_API_KEY=
```

### 2.3 Run Migrations

```bash
# Create migrations from models
python manage.py makemigrations

# Show migration plans
python manage.py migrate --plan

# Apply migrations
python manage.py migrate

# Verify database
python manage.py dbshell
SHOW TABLES;
```

### 2.4 Create Superuser

```bash
# Create admin user
python manage.py createsuperuser

# Follow prompts:
# Username: admin
# Email: admin@example.com
# Password: (enter strong password)
```

---

## 🧪 Testing & Quality Assurance

### 3.1 Unit Testing

Create `core/tests.py`:

```python
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from core.models import CustomUser, Penduduk, Pengajuan

User = get_user_model()


class UserAuthenticationTest(TestCase):
    """Test authentication functionality"""
    
    def setUp(self):
        self.client = Client()
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        self.user = User.objects.create_user(**self.user_data)
    
    def test_user_registration(self):
        """Test user registration"""
        response = self.client.post(reverse('users:register'), {
            'first_name': 'Test',
            'email': 'newuser@example.com',
            'nomor_telepon': '08123456789',
            'password': 'newpass123',
            'password_confirm': 'newpass123'
        })
        self.assertEqual(User.objects.count(), 2)
    
    def test_user_login(self):
        """Test user login"""
        response = self.client.post(reverse('users:login'), {
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
    
    def test_login_with_wrong_password(self):
        """Test login with wrong password"""
        response = self.client.post(reverse('users:login'), {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)


class PendudukModelTest(TestCase):
    """Test Penduduk model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_penduduk(self):
        """Test creating penduduk record"""
        penduduk = Penduduk.objects.create(
            user=self.user,
            nik='1234567890123456',
            nama='Budi Santoso',
            daerah_asal='Sleman',
            alamat_tujuan='Jl. Sudirman No. 1, Jakarta',
            provinsi_tujuan='DKI Jakarta',
            kabupaten_tujuan='Jakarta Pusat',
            tujuan_merantau='pekerjaan',
            tanggal_mulai='2024-01-01'
        )
        self.assertEqual(penduduk.nama, 'Budi Santoso')
        self.assertEqual(penduduk.nik, '1234567890123456')
    
    def test_nik_validation(self):
        """Test NIK validation"""
        with self.assertRaises(Exception):
            Penduduk.objects.create(
                user=self.user,
                nik='123456789',  # Too short
                nama='Test',
                daerah_asal='Test',
                alamat_tujuan='Test',
                provinsi_tujuan='Test',
                kabupaten_tujuan='Test',
                tujuan_merantau='pekerjaan',
                tanggal_mulai='2024-01-01'
            )


class APIEndpointsTest(TestCase):
    """Test API endpoints"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='petugas',
            email='petugas@example.com',
            password='testpass123',
            role='petugas'
        )
    
    def test_pending_count_api(self):
        """Test pending count API"""
        self.client.force_login(self.user)
        response = self.client.get(reverse('api_pending_count'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('count', data)
```

Run tests:

```bash
# Run all tests
python manage.py test

# Run specific test
python manage.py test core.tests.UserAuthenticationTest

# Run with verbose output
python manage.py test --verbosity=2

# Run with coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
coverage html
```

### 3.2 Integration Testing

```python
# Create integration tests
python manage.py test perantau.tests
python manage.py test verifikasi.tests
```

### 3.3 Performance Testing

```bash
# Install django-extensions
pip install django-extensions

# Check query count
python manage.py shell
from django.test.utils import CaptureQueriesContext
from django.db import connection
with CaptureQueriesContext(connection) as queries:
    # Your code here
    pass
print(f"Total queries: {len(queries)}")
```

---

## 🚀 Local Development Server

### 4.1 Run Development Server

```bash
# Activate virtual environment (if not already)
venv\Scripts\activate

# Collect static files
python manage.py collectstatic --noinput

# Run server
python manage.py runserver

# Server running at http://127.0.0.1:8000/
```

### 4.2 Admin Panel Access

```
URL: http://localhost:8000/admin/
Username: admin
Password: (your superuser password)
```

### 4.3 Common Commands

```bash
# Create new migration
python manage.py makemigrations app_name

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Clear cache
python manage.py clear_cache

# Shell for testing
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> users = User.objects.all()
>>> exit()

# Check deployment readiness
python manage.py check --deploy
```

---

## 📊 Debugging & Logging

### 5.1 Django Debug Toolbar

```bash
# Install
pip install django-debug-toolbar

# Add to INSTALLED_APPS in settings.py
'debug_toolbar',

# Add middleware
'debug_toolbar.middleware.DebugToolbarMiddleware',

# Add URL pattern
from django.conf import settings
from django.urls import include, path

if settings.DEBUG:
    urlpatterns += [path('__debug__/', include('debug_toolbar.urls'))]

# Add INTERNAL_IPS
INTERNAL_IPS = ['127.0.0.1']
```

### 5.2 Logging Configuration

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'logs/sipper.log',
            'formatter': 'verbose'
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}
```

### 5.3 Error Monitoring

```python
# Install Sentry (optional)
pip install sentry-sdk

# Add to settings.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn="https://your-sentry-dsn@sentry.io/project-id",
    integrations=[DjangoIntegration()],
    traces_sample_rate=1.0,
    send_default_pii=False
)
```

---

## 🔐 Security Checklist

### 6.1 Pre-Production Security

```python
# settings.py for production

# 1. HTTPS & Security Headers
DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_SECURITY_POLICY = {
    "default-src": ("'self'",),
}

# 2. HSTS
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# 3. Secret Key
SECRET_KEY = os.environ.get('SECRET_KEY')

# 4. Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT'),
    }
}

# 5. File Uploads
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
```

### 6.2 Regular Security Updates

```bash
# Check for outdated packages
pip list --outdated

# Update packages
pip install --upgrade package-name

# Security audit
pip install safety
safety check
```

---

## 🌐 Production Deployment

### 7.1 Gunicorn Setup

```bash
# Install Gunicorn
pip install gunicorn

# Test with Gunicorn
gunicorn sipper_config.wsgi:application --bind 0.0.0.0:8000

# Create Gunicorn config file (gunicorn_config.py)
bind = "127.0.0.1:8000"
workers = 4
worker_class = "sync"
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2
```

### 7.2 Nginx Configuration

```nginx
# /etc/nginx/sites-available/sipper

upstream sipper_app {
    server 127.0.0.1:8000;
}

# Rate limiting
limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    client_max_body_size 5M;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css text/javascript application/json;
    gzip_min_length 1000;

    # Static files
    location /static/ {
        alias /home/sipper/sipper-app/static_root/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /home/sipper/sipper-app/media/;
        expires 7d;
    }

    # Rate limiting for login
    location /auth/login/ {
        limit_req zone=login burst=5 nodelay;
        proxy_pass http://sipper_app;
        include proxy_params;
    }

    # General rate limiting
    location / {
        limit_req zone=general burst=20 nodelay;
        proxy_pass http://sipper_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

### 7.3 Systemd Service Configuration

```ini
# /etc/systemd/system/sipper.service

[Unit]
Description=SIPPER Django Application
After=network.target mysql.service

[Service]
Type=notify
User=sipper
Group=www-data
WorkingDirectory=/home/sipper/sipper-app
Environment="PATH=/home/sipper/sipper-app/venv/bin"
ExecStart=/home/sipper/sipper-app/venv/bin/gunicorn \
    --workers 4 \
    --worker-class sync \
    --bind 127.0.0.1:8000 \
    --timeout 30 \
    --access-logfile /var/log/sipper/access.log \
    --error-logfile /var/log/sipper/error.log \
    sipper_config.wsgi:application

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 7.4 Deployment Commands

```bash
# 1. Create app user
sudo useradd -m -s /bin/bash sipper

# 2. Setup directories
sudo mkdir -p /home/sipper/sipper-app
sudo mkdir -p /var/log/sipper
sudo chown -R sipper:www-data /home/sipper/sipper-app
sudo chown -R sipper:www-data /var/log/sipper

# 3. Clone repository
cd /home/sipper/sipper-app
git clone your-repo-url .

# 4. Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Setup environment file
cp .env.example .env
nano .env  # Edit with production values

# 6. Collect static files
python manage.py collectstatic --noinput

# 7. Run migrations
python manage.py migrate

# 8. Enable and start services
sudo systemctl enable sipper.service
sudo systemctl start sipper.service
sudo systemctl enable nginx
sudo systemctl start nginx

# 9. Setup SSL
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com

# 10. Check status
sudo systemctl status sipper.service
sudo systemctl status nginx
```

### 7.5 Monitoring & Maintenance

```bash
# Monitor logs
sudo tail -f /var/log/sipper/error.log
sudo tail -f /var/log/sipper/access.log

# Monitor system resources
watch -n 1 'free -h && echo && ps aux | grep gunicorn'

# Backup database
mysqldump -u sipper_user -p sipper_db > backup_$(date +%Y%m%d).sql

# Rotate logs
sudo logrotate /etc/logrotate.d/sipper

# Update application
cd /home/sipper/sipper-app
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart sipper.service
```

---

## 📈 Performance Optimization

### 8.1 Database Optimization

```python
# Use select_related and prefetch_related
from django.db.models import Prefetch

# Good
pengajuan = Pengajuan.objects.select_related('penduduk').prefetch_related('dokumen')

# Bad
pengajuan = Pengajuan.objects.all()
for p in pengajuan:
    print(p.penduduk.nama)  # N+1 query problem
```

### 8.2 Caching

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}

# Usage in views
from django.views.decorators.cache import cache_page

@cache_page(60 * 15)  # Cache for 15 minutes
def expensive_view(request):
    # Your view logic
    pass
```

### 8.3 Async Tasks

```bash
# Install Celery
pip install celery redis

# Create tasks.py
from celery import shared_task
from core.models import Pengajuan

@shared_task
def process_verification(pengajuan_id):
    pengajuan = Pengajuan.objects.get(id=pengajuan_id)
    # Process verification
    pass
```

---

## 📋 Deployment Checklist

- [ ] All tests passing
- [ ] Security checks done
- [ ] Static files collected
- [ ] Database migrations applied
- [ ] Environment variables configured
- [ ] SSL certificate installed
- [ ] Nginx configured
- [ ] Gunicorn running
- [ ] Firewall configured
- [ ] Backups scheduled
- [ ] Monitoring setup
- [ ] Log rotation configured
- [ ] Domain pointing to server
- [ ] DNS records updated

---

## 🆘 Troubleshooting

### Common Issues & Solutions

```bash
# Permission denied errors
sudo chown -R sipper:www-data /home/sipper/sipper-app

# Database connection errors
mysql -u sipper_user -p sipper_db -e "SELECT 1"

# Static files not loading
python manage.py collectstatic --clear --noinput

# Gunicorn not starting
/home/sipper/sipper-app/venv/bin/gunicorn --check-config sipper_config.wsgi

# Memory issues
free -h
ps aux | sort -k4 -rn | head -n 10

# Disk space issues
df -h
du -sh /home/sipper/sipper-app/*
```

---

**Selesai! Setup, testing, dan deployment guide untuk SIPPER sudah lengkap.**
