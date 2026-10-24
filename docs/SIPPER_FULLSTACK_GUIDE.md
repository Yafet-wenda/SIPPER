# Workspace Implementation Note

The runnable workspace currently uses the `sipper` project package and a single `core` Django app. The active implementation includes the models, routes, templates, document review, QR cards, PDF export, role profile, APIs, backups, and Docker deployment. Some examples below describe the original planned multi-app architecture (`users`, `perantau`, `verifikasi`, and `kartu`) and are retained as historical design reference; use `README.md` and `SIPPER_SETUP_DEPLOYMENT.md` for the current setup.

# 📱 SIPPER - Sistem Informasi Penduduk Perantauan
## Dokumentasi Lengkap Fullstack Development

**Status:** Rujukan historis (bukan spesifikasi berjalan)  
**Version:** 1.0.0  
**Tech Stack yang diuraikan di bawah (rancangan lama):** Python 3.10+, Django 4.2, MySQL 8.0, Bootstrap 5 — versi-versi ini hanya konteks historis, JANGAN dipakai untuk pemasangan baru  
**Yang berjalan sekarang:** Python 3.12 (lokal) / 3.13–3.14 (CI), Django 5.2, MariaDB 10.4 (XAMPP), CSS
tulisan sendiri tanpa Bootstrap, satu aplikasi `core` plus panel `ai_ocr`  
**Author:** Development Team  
**Last Updated:** 2024 — blok *settings* di bagian 4 adalah rancangan lama: nilai
`STATIC_ROOT = 'static_root'`, `AUTH_USER_MODEL = 'core.CustomUser'`, dan Crispy Forms
tidak ada di `sipper/settings.py`. Baca berkas itu untuk angka yang sebenarnya.

---

## 📑 Daftar Isi

1. [Setup Environment](#1-setup-environment)
2. [Database Architecture](#2-database-architecture)
3. [Project Structure](#3-project-structure)
4. [Backend Implementation](#4-backend-implementation)
5. [Frontend & UI Theme](#5-frontend--ui-theme)
6. [Authentication & Security](#6-authentication--security)
7. [Feature Implementation](#7-feature-implementation)
8. [Deployment Guide](#8-deployment-guide)

---

## 1. Setup Environment

### 1.1 Prerequisites
```bash
# Check Python version (minimum 3.10)
python --version

# Check MySQL version (minimum 5.7)
mysql --version
```

### 1.2 Project Initialization

```bash
# Create project directory
mkdir sipper-app
cd sipper-app

# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# Activate virtual environment (Linux/Mac)
source venv/bin/activate
```

### 1.3 Install Dependencies

Create `requirements.txt`:
```
Django==4.2.0
mysqlclient==2.2.0
python-decouple==3.8
Pillow==10.0.0
qrcode==7.4.2
django-crispy-forms==2.1
crispy-bootstrap5==0.7
python-dotenv==1.0.0
requests==2.31.0
langchain==0.0.300
openai==0.27.8
```

```bash
# Install all dependencies
pip install -r requirements.txt
```

### 1.4 Create Django Project & App

```bash
# Create Django project
django-admin startproject sipper_config .

# Create main app
python manage.py startapp core

# Create additional apps
python manage.py startapp users
python manage.py startapp perantau
python manage.py startapp verifikasi
python manage.py startapp kartu
```

---

## 2. Database Architecture

### 2.1 MySQL Database Setup

```sql
-- Create database
CREATE DATABASE sipper_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Use database
USE sipper_db;

-- Create users table
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    nama VARCHAR(150) NOT NULL,
    email VARCHAR(254) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    nomor_telepon VARCHAR(15),
    role ENUM('masyarakat', 'petugas') DEFAULT 'masyarakat',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create penduduk table
CREATE TABLE penduduk (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    nik VARCHAR(16) UNIQUE NOT NULL,
    nama VARCHAR(150) NOT NULL,
    daerah_asal VARCHAR(100) NOT NULL,
    provinsi_asal VARCHAR(50),
    kabupaten_asal VARCHAR(50),
    alamat_tujuan TEXT NOT NULL,
    provinsi_tujuan VARCHAR(50) NOT NULL,
    kabupaten_tujuan VARCHAR(50) NOT NULL,
    tujuan_merantau VARCHAR(50) NOT NULL,
    tanggal_mulai DATE NOT NULL,
    perkiraan_kembali DATE,
    status ENUM('aktif', 'pindah', 'pulang') DEFAULT 'aktif',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_nik (nik),
    INDEX idx_status (status),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create pengajuan table
CREATE TABLE pengajuan (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    penduduk_id BIGINT NOT NULL,
    status ENUM('menunggu', 'disetujui', 'ditolak', 'perlu_perbaikan') DEFAULT 'menunggu',
    catatan TEXT,
    tanggal_pengajuan DATETIME DEFAULT CURRENT_TIMESTAMP,
    tanggal_verifikasi DATETIME,
    verified_by_id BIGINT,
    ai_confidence_score DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (penduduk_id) REFERENCES penduduk(id) ON DELETE CASCADE,
    FOREIGN KEY (verified_by_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_status (status),
    INDEX idx_penduduk_id (penduduk_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create dokumen table
CREATE TABLE dokumen (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    penduduk_id BIGINT NOT NULL,
    pengajuan_id BIGINT,
    nama_dokumen VARCHAR(100) NOT NULL,
    jenis_dokumen ENUM('ktp', 'surat_kerja', 'surat_kuliah', 'surat_domisili', 'lainnya') NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    ukuran_file BIGINT,
    status ENUM('valid', 'invalid', 'pending') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (penduduk_id) REFERENCES penduduk(id) ON DELETE CASCADE,
    FOREIGN KEY (pengajuan_id) REFERENCES pengajuan(id) ON DELETE SET NULL,
    INDEX idx_penduduk_id (penduduk_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create pemutakhiran table
CREATE TABLE pemutakhiran (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    penduduk_id BIGINT NOT NULL,
    data_lama JSON,
    data_baru JSON,
    field_yang_diubah VARCHAR(100),
    tanggal TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (penduduk_id) REFERENCES penduduk(id) ON DELETE CASCADE,
    INDEX idx_penduduk_id (penduduk_id),
    INDEX idx_tanggal (tanggal)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create kartu_digital table
CREATE TABLE kartu_digital (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    penduduk_id BIGINT UNIQUE NOT NULL,
    kode_verifikasi VARCHAR(64) UNIQUE NOT NULL,
    qr_code_path VARCHAR(255),
    tanggal_terbit DATE DEFAULT CURRENT_DATE,
    masa_berlaku DATE,
    status ENUM('aktif', 'nonaktif', 'expired') DEFAULT 'aktif',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (penduduk_id) REFERENCES penduduk(id) ON DELETE CASCADE,
    INDEX idx_kode_verifikasi (kode_verifikasi),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create audit_log table
CREATE TABLE audit_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT,
    aksi VARCHAR(255),
    deskripsi TEXT,
    ip_address VARCHAR(50),
    user_agent VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 2.2 Django Models

Create `core/models.py`:
```python
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid
import json

# Custom User Model
class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('masyarakat', 'Masyarakat'),
        ('petugas', 'Petugas Pemerintah'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='masyarakat')
    nomor_telepon = models.CharField(
        max_length=15, 
        blank=True,
        validators=[RegexValidator(r'^\d{10,15}$', 'Nomor telepon harus 10-15 digit')]
    )
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    class Meta:
        db_table = 'users'
        verbose_name = 'Pengguna'
        verbose_name_plural = 'Pengguna'
    
    def __str__(self):
        return f"{self.first_name or self.username} ({self.get_role_display()})"


class Penduduk(models.Model):
    STATUS_CHOICES = [
        ('aktif', 'Masih di Tujuan'),
        ('pindah', 'Pindah Daerah'),
        ('pulang', 'Kembali ke Asal'),
    ]
    
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profil_penduduk')
    nik = models.CharField(
        max_length=16,
        unique=True,
        validators=[RegexValidator(r'^\d{16}$', 'NIK harus 16 digit')]
    )
    nama = models.CharField(max_length=150)
    daerah_asal = models.CharField(max_length=100)
    provinsi_asal = models.CharField(max_length=50, blank=True)
    kabupaten_asal = models.CharField(max_length=50, blank=True)
    alamat_tujuan = models.TextField()
    provinsi_tujuan = models.CharField(max_length=50)
    kabupaten_tujuan = models.CharField(max_length=50)
    tujuan_merantau = models.CharField(
        max_length=50,
        choices=[
            ('pendidikan', 'Pendidikan'),
            ('pekerjaan', 'Pekerjaan'),
            ('usaha', 'Pengembangan Usaha'),
            ('keluarga', 'Kepentingan Keluarga'),
            ('lainnya', 'Lainnya'),
        ]
    )
    tanggal_mulai = models.DateField()
    perkiraan_kembali = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aktif')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'penduduk'
        verbose_name = 'Data Perantau'
        verbose_name_plural = 'Data Perantau'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.nama} - {self.nik}"


class Pengajuan(models.Model):
    STATUS_CHOICES = [
        ('menunggu', 'Menunggu Verifikasi'),
        ('disetujui', 'Disetujui'),
        ('ditolak', 'Ditolak'),
        ('perlu_perbaikan', 'Perlu Perbaikan'),
    ]
    
    penduduk = models.OneToOneField(Penduduk, on_delete=models.CASCADE, related_name='pengajuan')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='menunggu')
    catatan = models.TextField(blank=True)
    tanggal_pengajuan = models.DateTimeField(auto_now_add=True)
    tanggal_verifikasi = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    ai_confidence_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pengajuan'
        verbose_name = 'Pengajuan Verifikasi'
        verbose_name_plural = 'Pengajuan Verifikasi'
        ordering = ['-tanggal_pengajuan']
    
    def __str__(self):
        return f"Pengajuan {self.penduduk.nama} - {self.get_status_display()}"


class Dokumen(models.Model):
    JENIS_CHOICES = [
        ('ktp', 'KTP'),
        ('surat_kerja', 'Surat Keterangan Kerja'),
        ('surat_kuliah', 'Surat Keterangan Kuliah'),
        ('surat_domisili', 'Surat Keterangan Domisili'),
        ('lainnya', 'Dokumen Lainnya'),
    ]
    
    STATUS_CHOICES = [
        ('valid', 'Valid'),
        ('invalid', 'Invalid'),
        ('pending', 'Pending Review'),
    ]
    
    penduduk = models.ForeignKey(Penduduk, on_delete=models.CASCADE, related_name='dokumen')
    pengajuan = models.ForeignKey(Pengajuan, on_delete=models.SET_NULL, null=True, blank=True, related_name='dokumen')
    nama_dokumen = models.CharField(max_length=100)
    jenis_dokumen = models.CharField(max_length=50, choices=JENIS_CHOICES)
    file = models.FileField(upload_to='dokumen/%Y/%m/')
    ukuran_file = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'dokumen'
        verbose_name = 'Dokumen Pendukung'
        verbose_name_plural = 'Dokumen Pendukung'
    
    def __str__(self):
        return f"{self.penduduk.nama} - {self.get_jenis_dokumen_display()}"


class Pemutakhiran(models.Model):
    penduduk = models.ForeignKey(Penduduk, on_delete=models.CASCADE, related_name='pemutakhiran')
    data_lama = models.JSONField(default=dict)
    data_baru = models.JSONField(default=dict)
    field_yang_diubah = models.CharField(max_length=100)
    tanggal = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'pemutakhiran'
        verbose_name = 'Pemutakhiran Data'
        verbose_name_plural = 'Pemutakhiran Data'
        ordering = ['-tanggal']
    
    def __str__(self):
        return f"Update {self.penduduk.nama} - {self.field_yang_diubah}"


class KartuDigital(models.Model):
    STATUS_CHOICES = [
        ('aktif', 'Aktif'),
        ('nonaktif', 'Nonaktif'),
        ('expired', 'Expired'),
    ]
    
    penduduk = models.OneToOneField(Penduduk, on_delete=models.CASCADE, related_name='kartu_digital')
    kode_verifikasi = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    qr_code_path = models.ImageField(upload_to='qr_codes/', null=True, blank=True)
    tanggal_terbit = models.DateField(auto_now_add=True)
    masa_berlaku = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aktif')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'kartu_digital'
        verbose_name = 'Kartu Digital'
        verbose_name_plural = 'Kartu Digital'
    
    def __str__(self):
        return f"Kartu {self.penduduk.nama}"
    
    def is_valid(self):
        from django.utils import timezone
        return self.status == 'aktif' and self.masa_berlaku >= timezone.now().date()


class AuditLog(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    aksi = models.CharField(max_length=255)
    deskripsi = models.TextField()
    ip_address = models.CharField(max_length=50, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'audit_log'
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Log'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user} - {self.aksi}"
```

---

## 3. Project Structure

```
sipper-app/
├── sipper_config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── core/
│   ├── migrations/
│   ├── templates/
│   │   ├── base.html
│   │   ├── home.html
│   │   ├── dashboard.html
│   │   └── layouts/
│   │       ├── sidebar.html
│   │       └── navbar.html
│   ├── static/
│   │   ├── css/
│   │   │   ├── style.css (tema hijau)
│   │   │   └── bootstrap-custom.css
│   │   ├── js/
│   │   │   └── main.js
│   │   └── img/
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py
│   ├── urls.py
│   ├── views.py
│   └── tests.py
├── users/
│   ├── migrations/
│   ├── templates/users/
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   └── models.py
├── perantau/
│   ├── migrations/
│   ├── templates/perantau/
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   └── models.py
├── verifikasi/
│   ├── migrations/
│   ├── templates/verifikasi/
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── ai_processor.py
│   └── models.py
├── kartu/
│   ├── migrations/
│   ├── templates/kartu/
│   ├── views.py
│   ├── urls.py
│   ├── qr_generator.py
│   └── models.py
├── media/
│   ├── dokumen/
│   ├── qr_codes/
│   └── avatars/
├── static_root/
├── templates/
│   ├── 404.html
│   ├── 500.html
│   └── email/
├── manage.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
└── README.md
```

---

## 4. Backend Implementation

### 4.1 Django Settings Configuration

Create `sipper_config/settings.py`:
```python
import os
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-development-key')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'crispy_forms',
    'crispy_bootstrap5',
    
    # Local apps
    'core',
    'users',
    'perantau',
    'verifikasi',
    'kartu',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sipper_config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sipper_config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME', default='sipper_db'),
        'USER': config('DB_USER', default='root'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'use_unicode': True,
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        }
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'id-id'
TIME_ZONE = 'Asia/Jakarta'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static_root'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Authentication
AUTH_USER_MODEL = 'core.CustomUser'
LOGIN_URL = 'users:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'core:home'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Session & Security
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

# File Upload
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
FILE_UPLOAD_PERMISSIONS = 0o644

# Email configuration (untuk production)
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'debug.log',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
}

# AI/ML Services
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')
GOOGLE_API_KEY = config('GOOGLE_API_KEY', default='')
AI_CONFIDENCE_THRESHOLD = 0.85
```

### 4.2 URL Configuration

Create `sipper_config/urls.py`:
```python
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls', namespace='core')),
    path('auth/', include('users.urls', namespace='users')),
    path('perantau/', include('perantau.urls', namespace='perantau')),
    path('verifikasi/', include('verifikasi.urls', namespace='verifikasi')),
    path('kartu/', include('kartu.urls', namespace='kartu')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Error handling
handler404 = 'core.views.handler404'
handler500 = 'core.views.handler500'
```

### 4.3 Core Views

Create `core/views.py`:
```python
from django.shortcuts import render, redirect
from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.utils import timezone
from core.models import Pengajuan, Penduduk, CustomUser

class HomeView(TemplateView):
    template_name = 'home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_perantau'] = Penduduk.objects.count()
        context['pengajuan_disetujui'] = Pengajuan.objects.filter(status='disetujui').count()
        context['pengajuan_menunggu'] = Pengajuan.objects.filter(status='menunggu').count()
        return context


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'
    login_url = 'users:login'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        if user.role == 'petugas':
            context['total_pengajuan'] = Pengajuan.objects.count()
            context['pengajuan_pending'] = Pengajuan.objects.filter(status='menunggu').count()
            context['pengajuan_disetujui'] = Pengajuan.objects.filter(status='disetujui').count()
            context['pengajuan_ditolak'] = Pengajuan.objects.filter(status='ditolak').count()
            context['total_perantau'] = Penduduk.objects.count()
            
            # Data untuk chart
            context['recent_pengajuan'] = Pengajuan.objects.select_related('penduduk').order_by('-tanggal_pengajuan')[:10]
        else:
            # Dashboard untuk masyarakat
            try:
                penduduk = user.profil_penduduk
                context['penduduk'] = penduduk
                context['pengajuan'] = penduduk.pengajuan
                context['dokumen'] = penduduk.dokumen.all()
                context['kartu'] = penduduk.kartu_digital
            except:
                context['penduduk'] = None
        
        return context


class StatistikView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'verifikasi/statistik.html'
    
    def test_func(self):
        return self.request.user.role == 'petugas'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistik per status
        context['stats_status'] = Pengajuan.objects.values('status').annotate(count=Count('id'))
        
        # Statistik per tujuan merantau
        context['stats_tujuan'] = Penduduk.objects.values('tujuan_merantau').annotate(count=Count('id'))
        
        # Statistik per provinsi tujuan
        context['stats_provinsi'] = Penduduk.objects.values('provinsi_tujuan').annotate(count=Count('id'))
        
        # Grafik waktu pengajuan
        from django.db.models.functions import TruncDate
        from django.db.models import Count
        
        pengajuan_timeline = Pengajuan.objects.annotate(
            tanggal=TruncDate('tanggal_pengajuan')
        ).values('tanggal').annotate(count=Count('id')).order_by('tanggal')
        
        context['pengajuan_timeline'] = list(pengajuan_timeline)
        
        return context


def handler404(request, exception):
    return render(request, '404.html', status=404)


def handler500(request):
    return render(request, '500.html', status=500)


@login_required(login_url='users:login')
def audit_log_view(request):
    from core.models import AuditLog
    logs = AuditLog.objects.all().order_by('-created_at')[:100]
    return render(request, 'audit_log.html', {'logs': logs})
```

### 4.4 Forms Implementation

Create `core/forms.py`:
```python
from django import forms
from django.contrib.auth import authenticate
from core.models import CustomUser, Penduduk, Pengajuan, Dokumen


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Email',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Password'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        
        if email and password:
            try:
                user = CustomUser.objects.get(email=email)
                if not authenticate(username=user.username, password=password):
                    raise forms.ValidationError('Email atau password salah')
            except CustomUser.DoesNotExist:
                raise forms.ValidationError('Email atau password salah')
        
        return cleaned_data


class RegistrasiForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Password (minimal 8 karakter)'
        })
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Konfirmasi Password'
        })
    )
    
    class Meta:
        model = CustomUser
        fields = ['first_name', 'email', 'nomor_telepon']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Nama Lengkap'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Email'
            }),
            'nomor_telepon': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Nomor Telepon'
            }),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if password and password_confirm:
            if password != password_confirm:
                raise forms.ValidationError('Password tidak cocok')
            if len(password) < 8:
                raise forms.ValidationError('Password minimal 8 karakter')
        
        return cleaned_data


class PendaftaranPerantauForm(forms.ModelForm):
    class Meta:
        model = Penduduk
        fields = [
            'nik', 'nama', 'daerah_asal', 'provinsi_asal', 'kabupaten_asal',
            'alamat_tujuan', 'provinsi_tujuan', 'kabupaten_tujuan',
            'tujuan_merantau', 'tanggal_mulai', 'perkiraan_kembali'
        ]
        widgets = {
            'nik': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Masukkan NIK (16 digit)',
                'pattern': '\\d{16}'
            }),
            'nama': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nama sesuai NIK'
            }),
            'daerah_asal': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Kota/Kabupaten asal'
            }),
            'provinsi_asal': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Provinsi asal'
            }),
            'kabupaten_asal': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Kabupaten asal'
            }),
            'alamat_tujuan': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Alamat lengkap tujuan',
                'rows': 4
            }),
            'provinsi_tujuan': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Provinsi tujuan'
            }),
            'kabupaten_tujuan': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Kabupaten tujuan'
            }),
            'tujuan_merantau': forms.Select(attrs={
                'class': 'form-select'
            }),
            'tanggal_mulai': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'perkiraan_kembali': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }


class DokumenForm(forms.ModelForm):
    class Meta:
        model = Dokumen
        fields = ['jenis_dokumen', 'file']
        widgets = {
            'jenis_dokumen': forms.Select(attrs={
                'class': 'form-select'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png',
                'size': 5242880
            }),
        }


class PemutakhiranStatusForm(forms.ModelForm):
    class Meta:
        model = Penduduk
        fields = ['status', 'alamat_tujuan', 'perkiraan_kembali']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'alamat_tujuan': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'perkiraan_kembali': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }
```

---

## 5. Frontend & UI Theme

### 5.1 Custom CSS - Tema Hijau

Create `static/css/style.css`:
```css
/* ============================================
   SIPPER - CUSTOM THEME HIJAU (GREEN THEME)
   ============================================ */

:root {
    --primary-dark: #065f46;
    --primary: #10b981;
    --primary-light: #d1fae5;
    --primary-lighter: #f0fdf4;
    --secondary: #059669;
    --danger: #dc2626;
    --warning: #f59e0b;
    --success: #10b981;
    --info: #0ea5e9;
    --light: #f8fafc;
    --dark: #1e293b;
    --text-muted: #64748b;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

html {
    scroll-behavior: smooth;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background-color: #f9fafb;
    color: #1f2937;
    line-height: 1.6;
}

/* ============================================
   TYPOGRAPHY
   ============================================ */

h1, h2, h3, h4, h5, h6 {
    font-weight: 700;
    color: var(--primary-dark);
}

a {
    color: var(--primary);
    text-decoration: none;
    transition: color 0.3s ease;
}

a:hover {
    color: var(--secondary);
}

/* ============================================
   NAVBAR / HEADER
   ============================================ */

.navbar {
    background: linear-gradient(135deg, var(--primary-dark) 0%, var(--primary) 100%);
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    padding: 1rem 0;
}

.navbar-brand {
    font-size: 1.5rem;
    font-weight: 800;
    color: white !important;
    letter-spacing: -0.5px;
}

.navbar-brand span {
    color: #d1fae5;
}

.nav-link {
    color: rgba(255,255,255,0.8) !important;
    font-weight: 500;
    transition: color 0.3s ease;
    margin: 0 0.5rem;
}

.nav-link:hover,
.nav-link.active {
    color: white !important;
}

.navbar-toggler {
    border-color: rgba(255,255,255,0.5);
}

.navbar-toggler:focus {
    box-shadow: 0 0 0 0.25rem rgba(16, 185, 129, 0.25);
}

/* ============================================
   SIDEBAR
   ============================================ */

.sidebar {
    background: linear-gradient(180deg, var(--primary-dark) 0%, var(--primary) 100%);
    color: white;
    min-height: 100vh;
    padding: 2rem 0;
    box-shadow: 2px 0 8px rgba(0,0,0,0.1);
    position: sticky;
    top: 0;
}

.sidebar .sidebar-heading {
    font-size: 0.875rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: rgba(255,255,255,0.6);
    padding: 1.5rem 1.5rem 0.75rem;
    font-weight: 700;
}

.sidebar .nav-link {
    color: rgba(255,255,255,0.8);
    padding: 0.75rem 1.5rem;
    border-left: 3px solid transparent;
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.sidebar .nav-link:hover,
.sidebar .nav-link.active {
    background-color: rgba(255,255,255,0.1);
    color: white;
    border-left-color: white;
    padding-left: 1.5rem;
}

.sidebar .nav-link i {
    width: 1.25rem;
    text-align: center;
}

/* ============================================
   BUTTONS
   ============================================ */

.btn {
    border-radius: 0.5rem;
    font-weight: 600;
    padding: 0.625rem 1.25rem;
    transition: all 0.3s ease;
    border: none;
}

.btn-primary {
    background-color: var(--primary);
    color: white;
}

.btn-primary:hover {
    background-color: var(--secondary);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
}

.btn-primary:active {
    transform: translateY(0);
}

.btn-outline-primary {
    border: 2px solid var(--primary);
    color: var(--primary);
}

.btn-outline-primary:hover {
    background-color: var(--primary);
    color: white;
}

.btn-success {
    background-color: var(--success);
}

.btn-success:hover {
    background-color: #059669;
}

.btn-danger {
    background-color: var(--danger);
}

.btn-danger:hover {
    background-color: #b91c1c;
}

.btn-sm {
    padding: 0.375rem 0.75rem;
    font-size: 0.875rem;
}

.btn-lg {
    padding: 0.75rem 1.5rem;
    font-size: 1.125rem;
}

/* ============================================
   CARDS
   ============================================ */

.card {
    border: none;
    border-radius: 0.75rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.3s ease;
    margin-bottom: 1.5rem;
}

.card:hover {
    box-shadow: 0 10px 25px rgba(0,0,0,0.1);
}

.card-header {
    background-color: var(--primary-lighter);
    border-bottom: 2px solid var(--primary-light);
    color: var(--primary-dark);
    font-weight: 600;
    border-radius: 0.75rem 0.75rem 0 0;
}

.card-body {
    padding: 1.5rem;
}

.stat-card {
    background: linear-gradient(135deg, var(--primary-light) 0%, white 100%);
    border-left: 4px solid var(--primary);
    padding: 1.5rem;
}

.stat-card h3 {
    color: var(--primary-dark);
    font-size: 2rem;
    margin: 0.5rem 0 0 0;
}

.stat-card p {
    color: var(--text-muted);
    margin: 0;
}

/* ============================================
   FORMS
   ============================================ */

.form-control,
.form-select,
.form-check-input {
    border-radius: 0.5rem;
    border: 1px solid #e5e7eb;
    transition: all 0.3s ease;
}

.form-control:focus,
.form-select:focus,
.form-check-input:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 0.2rem rgba(16, 185, 129, 0.25);
    color: #1f2937;
}

.form-label {
    font-weight: 600;
    color: var(--primary-dark);
    margin-bottom: 0.5rem;
}

.form-text {
    color: var(--text-muted);
    font-size: 0.875rem;
}

.invalid-feedback {
    display: block;
    color: var(--danger);
    font-size: 0.875rem;
    margin-top: 0.25rem;
}

.form-group {
    margin-bottom: 1.5rem;
}

.form-group:last-child {
    margin-bottom: 0;
}

/* ============================================
   ALERTS
   ============================================ */

.alert {
    border-radius: 0.5rem;
    border: none;
    padding: 1rem 1.5rem;
    margin-bottom: 1rem;
}

.alert-success {
    background-color: #d1fae5;
    color: #065f46;
    border-left: 4px solid var(--success);
}

.alert-danger {
    background-color: #fee2e2;
    color: #7f1d1d;
    border-left: 4px solid var(--danger);
}

.alert-warning {
    background-color: #fef3c7;
    color: #78350f;
    border-left: 4px solid var(--warning);
}

.alert-info {
    background-color: #cffafe;
    color: #164e63;
    border-left: 4px solid var(--info);
}

/* ============================================
   TABLES
   ============================================ */

.table {
    margin-bottom: 0;
}

.table thead th {
    background-color: var(--primary-lighter);
    color: var(--primary-dark);
    border-bottom: 2px solid var(--primary);
    font-weight: 600;
    padding: 1rem 0.75rem;
    text-transform: uppercase;
    font-size: 0.875rem;
    letter-spacing: 0.05em;
}

.table tbody tr {
    transition: background-color 0.3s ease;
}

.table tbody tr:hover {
    background-color: var(--primary-lighter);
}

.table tbody td {
    padding: 1rem 0.75rem;
    vertical-align: middle;
}

/* ============================================
   BADGES & LABELS
   ============================================ */

.badge {
    padding: 0.5rem 0.75rem;
    font-weight: 600;
    border-radius: 0.25rem;
    font-size: 0.75rem;
    letter-spacing: 0.05em;
}

.badge-success {
    background-color: #d1fae5;
    color: #065f46;
}

.badge-danger {
    background-color: #fee2e2;
    color: #7f1d1d;
}

.badge-warning {
    background-color: #fef3c7;
    color: #78350f;
}

.badge-info {
    background-color: #cffafe;
    color: #164e63;
}

.badge-pending {
    background-color: #f3e8ff;
    color: #6b21a8;
}

/* ============================================
   PAGINATION
   ============================================ */

.pagination {
    gap: 0.25rem;
}

.page-link {
    color: var(--primary);
    border: 1px solid #e5e7eb;
    border-radius: 0.25rem;
    transition: all 0.3s ease;
}

.page-link:hover {
    color: white;
    background-color: var(--primary);
    border-color: var(--primary);
}

.page-item.active .page-link {
    background-color: var(--primary);
    border-color: var(--primary);
}

/* ============================================
   MODAL
   ============================================ */

.modal-content {
    border: none;
    border-radius: 0.75rem;
    box-shadow: 0 20px 25px rgba(0,0,0,0.15);
}

.modal-header {
    background-color: var(--primary-lighter);
    border-bottom: 2px solid var(--primary);
    border-radius: 0.75rem 0.75rem 0 0;
}

.modal-header .btn-close {
    filter: invert(0.8);
}

.modal-title {
    color: var(--primary-dark);
    font-weight: 700;
}

/* ============================================
   UTILITY CLASSES
   ============================================ */

.text-primary {
    color: var(--primary) !important;
}

.text-dark {
    color: var(--primary-dark) !important;
}

.text-muted {
    color: var(--text-muted) !important;
}

.bg-light {
    background-color: var(--primary-lighter) !important;
}

.bg-primary-light {
    background-color: var(--primary-light) !important;
}

.border-primary {
    border-color: var(--primary) !important;
}

.rounded {
    border-radius: 0.5rem !important;
}

.rounded-lg {
    border-radius: 0.75rem !important;
}

.shadow-sm {
    box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
}

.shadow {
    box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
}

.shadow-lg {
    box-shadow: 0 10px 15px rgba(0,0,0,0.1) !important;
}

.transition-all {
    transition: all 0.3s ease !important;
}

/* ============================================
   RESPONSIVE
   ============================================ */

@media (max-width: 768px) {
    .sidebar {
        position: fixed;
        left: -100%;
        top: 0;
        width: 250px;
        height: 100vh;
        z-index: 999;
        transition: left 0.3s ease;
    }
    
    .sidebar.show {
        left: 0;
    }
    
    .navbar-brand {
        font-size: 1.25rem;
    }
    
    .stat-card {
        margin-bottom: 1rem;
    }
    
    h1 {
        font-size: 1.75rem;
    }
    
    h2 {
        font-size: 1.5rem;
    }
}

/* ============================================
   ANIMATIONS
   ============================================ */

@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes slideInLeft {
    from {
        opacity: 0;
        transform: translateX(-20px);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

.fade-in {
    animation: fadeIn 0.5s ease;
}

.slide-in-left {
    animation: slideInLeft 0.5s ease;
}

/* ============================================
   CUSTOM COMPONENTS
   ============================================ */

.wizard {
    margin-bottom: 2rem;
}

.wizard-step {
    display: flex;
    align-items: center;
    margin-bottom: 1.5rem;
    position: relative;
}

.wizard-step.active .step-number {
    background-color: var(--primary);
    color: white;
}

.wizard-step.completed .step-number {
    background-color: var(--success);
    color: white;
}

.step-number {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background-color: #e5e7eb;
    color: var(--primary-dark);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    margin-right: 1rem;
    transition: all 0.3s ease;
}

.step-label {
    font-weight: 600;
    color: var(--primary-dark);
}

.qr-container {
    background: white;
    padding: 1.5rem;
    border-radius: 0.75rem;
    text-align: center;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.qr-container img {
    max-width: 200px;
    margin: 1rem 0;
}

.document-upload-area {
    border: 2px dashed var(--primary);
    border-radius: 0.75rem;
    padding: 2rem;
    text-align: center;
    transition: all 0.3s ease;
    cursor: pointer;
    background-color: var(--primary-lighter);
}

.document-upload-area:hover {
    background-color: var(--primary-light);
    border-color: var(--secondary);
}

.document-upload-area.drag-over {
    background-color: var(--primary-light);
    border-color: var(--secondary);
    transform: scale(1.02);
}

/* ============================================
   LOADING SPINNER
   ============================================ */

.spinner-custom {
    display: inline-block;
    width: 30px;
    height: 30px;
    border: 3px solid var(--primary-light);
    border-top-color: var(--primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* ============================================
   FOOTER
   ============================================ */

footer {
    background-color: var(--primary-dark);
    color: white;
    padding: 2rem 0;
    margin-top: 3rem;
}

footer a {
    color: #d1fae5;
}

footer a:hover {
    color: white;
}

footer .footer-section h5 {
    color: white;
    margin-bottom: 1rem;
}
```

### 5.2 Base HTML Template

Create `templates/base.html`:
```html
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="SIPPER - Sistem Informasi Penduduk Perantauan">
    <meta name="keywords" content="perantau, pendataan, e-government">
    <title>{% block title %}SIPPER - Sistem Informasi Penduduk Perantauan{% endblock %}</title>
    
    {% load static %}
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <!-- Custom CSS -->
    <link rel="stylesheet" href="{% static 'css/style.css' %}">
    
    {% block extra_css %}{% endblock %}
</head>
<body>
    <!-- Navigation -->
    {% include 'layouts/navbar.html' %}
    
    {% if user.is_authenticated %}
        <div class="d-flex">
            <!-- Sidebar -->
            {% include 'layouts/sidebar.html' %}
            
            <!-- Main Content -->
            <main class="flex-grow-1">
                <div class="container-fluid p-4">
                    {% if messages %}
                        {% for message in messages %}
                            <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
                                {{ message }}
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        {% endfor %}
                    {% endif %}
                    
                    {% block content %}{% endblock %}
                </div>
            </main>
        </div>
    {% else %}
        <div class="container-fluid">
            {% if messages %}
                {% for message in messages %}
                    <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
            
            {% block content %}{% endblock %}
        </div>
    {% endif %}
    
    <!-- Footer -->
    {% include 'layouts/footer.html' %}
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    <!-- jQuery -->
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    
    <!-- Custom JS -->
    <script src="{% static 'js/main.js' %}"></script>
    
    {% block extra_js %}{% endblock %}
</body>
</html>
```

---

## 6. Authentication & Security

### 6.1 User Authentication

Create `users/views.py`:
```python
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from core.models import CustomUser, AuditLog
from core.forms import LoginForm, RegistrasiForm


def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_audit(request, aksi, deskripsi):
    """Log user activity"""
    try:
        AuditLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            aksi=aksi,
            deskripsi=deskripsi,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:255]
        )
    except:
        pass


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            
            try:
                user = CustomUser.objects.get(email=email)
                user = authenticate(request, username=user.username, password=password)
                
                if user is not None:
                    login(request, user)
                    log_audit(request, 'LOGIN', f'User {email} berhasil login')
                    messages.success(request, f'Selamat datang, {user.first_name or user.username}!')
                    
                    # Redirect berdasarkan role
                    if user.role == 'petugas':
                        return redirect('verifikasi:dashboard')
                    else:
                        return redirect('perantau:dashboard')
                else:
                    messages.error(request, 'Email atau password salah')
                    log_audit(request, 'LOGIN_FAILED', f'Gagal login: {email}')
            except CustomUser.DoesNotExist:
                messages.error(request, 'Email atau password salah')
                log_audit(request, 'LOGIN_FAILED', f'Email tidak ditemukan: {email}')
    else:
        form = LoginForm()
    
    return render(request, 'users/login.html', {'form': form})


@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = RegistrasiForm(request.POST)
        if form.is_valid():
            try:
                # Create user
                email = form.cleaned_data['email']
                password = form.cleaned_data['password']
                first_name = form.cleaned_data['first_name']
                nomor_telepon = form.cleaned_data.get('nomor_telepon', '')
                
                # Check if email already exists
                if CustomUser.objects.filter(email=email).exists():
                    messages.error(request, 'Email sudah terdaftar')
                else:
                    # Generate username from email
                    username = email.split('@')[0]
                    counter = 1
                    original_username = username
                    while CustomUser.objects.filter(username=username).exists():
                        username = f"{original_username}{counter}"
                        counter += 1
                    
                    user = CustomUser.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=first_name,
                        nomor_telepon=nomor_telepon,
                        role='masyarakat'
                    )
                    
                    # Auto login
                    login(request, user)
                    log_audit(request, 'REGISTER', f'User baru terdaftar: {email}')
                    messages.success(request, 'Registrasi berhasil! Silahkan lengkapi data perantauan Anda')
                    return redirect('perantau:pendaftaran')
            except Exception as e:
                messages.error(request, f'Terjadi kesalahan: {str(e)}')
    else:
        form = RegistrasiForm()
    
    return render(request, 'users/register.html', {'form': form})


@login_required(login_url='users:login')
def logout_view(request):
    log_audit(request, 'LOGOUT', f'User {request.user.email} logout')
    logout(request)
    messages.success(request, 'Anda telah logout')
    return redirect('core:home')


@login_required(login_url='users:login')
def profile_view(request):
    return render(request, 'users/profile.html', {
        'user': request.user
    })
```

---

## 7. Feature Implementation

### 7.1 Perantau Registration & Data Management

Create `perantau/views.py`:
```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from core.models import Penduduk, Pengajuan, Dokumen, Pemutakhiran, KartuDigital
from core.forms import PendaftaranPerantauForm, DokumenForm, PemutakhiranStatusForm
from users.views import log_audit
import json


@login_required(login_url='users:login')
def pendaftaran_view(request):
    """Pendaftaran data perantauan"""
    if request.user.role != 'masyarakat':
        messages.error(request, 'Anda tidak memiliki akses')
        return redirect('core:home')
    
    # Check if already has penduduk data
    try:
        penduduk = request.user.profil_penduduk
        return redirect('perantau:edit_data', pk=penduduk.id)
    except:
        pass
    
    if request.method == 'POST':
        form = PendaftaranPerantauForm(request.POST)
        if form.is_valid():
            try:
                penduduk = form.save(commit=False)
                penduduk.user = request.user
                penduduk.save()
                
                log_audit(request, 'PENDAFTARAN', f'User {request.user.email} mendaftar sebagai perantau')
                
                # Create pengajuan
                pengajuan = Pengajuan.objects.create(penduduk=penduduk)
                
                messages.success(request, 'Data pendaftaran berhasil disimpan. Silahkan upload dokumen pendukung')
                return redirect('perantau:upload_dokumen', pk=penduduk.id)
            except Exception as e:
                messages.error(request, f'Terjadi kesalahan: {str(e)}')
    else:
        form = PendaftaranPerantauForm()
    
    return render(request, 'perantau/pendaftaran.html', {
        'form': form,
        'step': 1
    })


@login_required(login_url='users:login')
def upload_dokumen_view(request, pk):
    """Upload dokumen pendukung"""
    penduduk = get_object_or_404(Penduduk, id=pk, user=request.user)
    
    if request.method == 'POST':
        form = DokumenForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                dokumen = form.save(commit=False)
                dokumen.penduduk = penduduk
                dokumen.pengajuan = penduduk.pengajuan
                dokumen.nama_dokumen = form.cleaned_data['jenis_dokumen']
                dokumen.save()
                
                # Get file size
                dokumen.ukuran_file = dokumen.file.size
                dokumen.save()
                
                log_audit(request, 'UPLOAD_DOKUMEN', f'Dokumen {dokumen.jenis_dokumen} diupload')
                
                messages.success(request, 'Dokumen berhasil diupload')
                return redirect('perantau:review_data', pk=penduduk.id)
            except Exception as e:
                messages.error(request, f'Gagal upload dokumen: {str(e)}')
    else:
        form = DokumenForm()
    
    dokumen_list = penduduk.dokumen.all()
    
    return render(request, 'perantau/upload_dokumen.html', {
        'form': form,
        'penduduk': penduduk,
        'dokumen_list': dokumen_list,
        'step': 2
    })


@login_required(login_url='users:login')
def review_data_view(request, pk):
    """Review data sebelum submit"""
    penduduk = get_object_or_404(Penduduk, id=pk, user=request.user)
    dokumen_list = penduduk.dokumen.all()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'submit':
            # Update status pengajuan
            pengajuan = penduduk.pengajuan
            pengajuan.status = 'menunggu'
            pengajuan.save()
            
            log_audit(request, 'SUBMIT_PENGAJUAN', f'Pengajuan dari {penduduk.nama} disubmit')
            
            messages.success(request, 'Pengajuan Anda berhasil dikirim untuk diverifikasi')
            return redirect('perantau:dashboard')
        elif action == 'back':
            return redirect('perantau:upload_dokumen', pk=penduduk.id)
    
    return render(request, 'perantau/review_data.html', {
        'penduduk': penduduk,
        'dokumen_list': dokumen_list,
        'step': 3
    })


@login_required(login_url='users:login')
def dashboard_perantau_view(request):
    """Dashboard user masyarakat"""
    if request.user.role != 'masyarakat':
        messages.error(request, 'Anda tidak memiliki akses')
        return redirect('core:home')
    
    try:
        penduduk = request.user.profil_penduduk
        pengajuan = penduduk.pengajuan
        dokumen_list = penduduk.dokumen.all()
        kartu = penduduk.kartu_digital
        pemutakhiran = penduduk.pemutakhiran.all()[:5]
    except:
        penduduk = None
        pengajuan = None
        dokumen_list = None
        kartu = None
        pemutakhiran = None
    
    return render(request, 'perantau/dashboard.html', {
        'penduduk': penduduk,
        'pengajuan': pengajuan,
        'dokumen_list': dokumen_list,
        'kartu': kartu,
        'pemutakhiran': pemutakhiran
    })


@login_required(login_url='users:login')
def edit_data_view(request, pk):
    """Edit data perantauan"""
    penduduk = get_object_or_404(Penduduk, id=pk, user=request.user)
    
    if request.method == 'POST':
        form = PemutakhiranStatusForm(request.POST, instance=penduduk)
        if form.is_valid():
            # Simpan data lama
            data_lama = {
                'status': str(penduduk.status),
                'alamat_tujuan': penduduk.alamat_tujuan,
                'perkiraan_kembali': str(penduduk.perkiraan_kembali) if penduduk.perkiraan_kembali else None
            }
            
            # Simpan data baru
            form.save()
            
            # Buat log pemutakhiran
            Pemutakhiran.objects.create(
                penduduk=penduduk,
                data_lama=data_lama,
                data_baru={
                    'status': penduduk.status,
                    'alamat_tujuan': penduduk.alamat_tujuan,
                    'perkiraan_kembali': str(penduduk.perkiraan_kembali) if penduduk.perkiraan_kembali else None
                },
                field_yang_diubah='status,alamat_tujuan,perkiraan_kembali'
            )
            
            log_audit(request, 'PEMUTAKHIRAN_DATA', f'Data perantau {penduduk.nama} diperbarui')
            
            messages.success(request, 'Data berhasil diperbarui')
            return redirect('perantau:dashboard')
    else:
        form = PemutakhiranStatusForm(instance=penduduk)
    
    return render(request, 'perantau/edit_data.html', {
        'form': form,
        'penduduk': penduduk
    })
```

### 7.2 Verification Module (Admin/Petugas)

Create `verifikasi/views.py`:
```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.views.decorators.http import require_http_methods
from core.models import Pengajuan, Penduduk, Dokumen, KartuDigital, CustomUser
from users.views import log_audit
from datetime import datetime, timedelta
from kartu.qr_generator import generate_qr_code
import uuid


def verify_akses_petugas(function):
    """Decorator untuk verifikasi akses petugas"""
    def wrap(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'petugas':
            messages.error(request, 'Anda tidak memiliki akses')
            return redirect('core:home')
        return function(request, *args, **kwargs)
    return wrap


@login_required(login_url='users:login')
@verify_akses_petugas
def dashboard_petugas_view(request):
    """Dashboard petugas verifikasi"""
    total_pengajuan = Pengajuan.objects.count()
    pending = Pengajuan.objects.filter(status='menunggu').count()
    disetujui = Pengajuan.objects.filter(status='disetujui').count()
    ditolak = Pengajuan.objects.filter(status='ditolak').count()
    
    recent_pengajuan = Pengajuan.objects.select_related('penduduk').order_by('-tanggal_pengajuan')[:10]
    
    context = {
        'total_pengajuan': total_pengajuan,
        'pending': pending,
        'disetujui': disetujui,
        'ditolak': ditolak,
        'recent_pengajuan': recent_pengajuan,
    }
    
    return render(request, 'verifikasi/dashboard_petugas.html', context)


@login_required(login_url='users:login')
@verify_akses_petugas
def list_pengajuan_view(request):
    """List semua pengajuan dengan filter"""
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    pengajuan_qs = Pengajuan.objects.select_related('penduduk', 'verified_by').order_by('-tanggal_pengajuan')
    
    if status_filter:
        pengajuan_qs = pengajuan_qs.filter(status=status_filter)
    
    if search:
        pengajuan_qs = pengajuan_qs.filter(
            Q(penduduk__nama__icontains=search) |
            Q(penduduk__nik__icontains=search) |
            Q(penduduk__email__icontains=search)
        )
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(pengajuan_qs, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search': search,
        'statuses': Pengajuan._meta.get_field('status').choices
    }
    
    return render(request, 'verifikasi/list_pengajuan.html', context)


@login_required(login_url='users:login')
@verify_akses_petugas
def detail_pengajuan_view(request, pk):
    """Detail pengajuan untuk verifikasi"""
    pengajuan = get_object_or_404(Pengajuan, id=pk)
    penduduk = pengajuan.penduduk
    dokumen_list = penduduk.dokumen.all()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        catatan = request.POST.get('catatan', '')
        
        if action in ['disetujui', 'ditolak', 'perlu_perbaikan']:
            pengajuan.status = action
            pengajuan.catatan = catatan
            pengajuan.verified_by = request.user
            pengajuan.tanggal_verifikasi = datetime.now()
            pengajuan.save()
            
            # Jika disetujui, generate kartu digital
            if action == 'disetujui':
                try:
                    kode_verifikasi = str(uuid.uuid4())[:32]
                    qr_path = generate_qr_code(kode_verifikasi, penduduk.nik)
                    
                    KartuDigital.objects.update_or_create(
                        penduduk=penduduk,
                        defaults={
                            'kode_verifikasi': kode_verifikasi,
                            'qr_code_path': qr_path,
                            'masa_berlaku': datetime.now().date() + timedelta(days=365),
                            'status': 'aktif'
                        }
                    )
                    
                    messages.success(request, 'Pengajuan disetujui dan kartu digital berhasil dibuat')
                except Exception as e:
                    messages.warning(request, f'Pengajuan disetujui, tapi ada error saat membuat kartu: {str(e)}')
            else:
                messages.success(request, f'Pengajuan {action} dengan catatan')
            
            log_audit(request, 'VERIFIKASI_PENGAJUAN', f'Pengajuan {pengajuan.id} diubah status menjadi {action}')
            
            return redirect('verifikasi:list_pengajuan')
    
    context = {
        'pengajuan': pengajuan,
        'penduduk': penduduk,
        'dokumen_list': dokumen_list,
        'statuses': [
            ('disetujui', 'Disetujui'),
            ('ditolak', 'Ditolak'),
            ('perlu_perbaikan', 'Perlu Perbaikan')
        ]
    }
    
    return render(request, 'verifikasi/detail_pengajuan.html', context)


@login_required(login_url='users:login')
@verify_akses_petugas
def statistik_view(request):
    """Halaman statistik"""
    # Statistik dasar
    total_penduduk = Penduduk.objects.count()
    total_petugas = CustomUser.objects.filter(role='petugas').count()
    total_masyarakat = CustomUser.objects.filter(role='masyarakat').count()
    
    # Status pengajuan
    status_stats = Pengajuan.objects.values('status').annotate(count=Count('id'))
    
    # Distribusi tujuan
    tujuan_stats = Penduduk.objects.values('tujuan_merantau').annotate(count=Count('id'))
    
    # Distribusi provinsi
    provinsi_stats = Penduduk.objects.values('provinsi_tujuan').annotate(count=Count('id')).order_by('-count')[:10]
    
    context = {
        'total_penduduk': total_penduduk,
        'total_petugas': total_petugas,
        'total_masyarakat': total_masyarakat,
        'status_stats': list(status_stats),
        'tujuan_stats': list(tujuan_stats),
        'provinsi_stats': list(provinsi_stats),
    }
    
    return render(request, 'verifikasi/statistik.html', context)
```

---

## 8. Deployment Guide

### 8.1 Production Settings

Create `.env` file:
```env
# Django
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DB_ENGINE=django.db.backends.mysql
DB_NAME=sipper_db
DB_USER=sipper_user
DB_PASSWORD=strong-password-here
DB_HOST=localhost
DB_PORT=3306

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# AI Services
OPENAI_API_KEY=your-openai-key
GOOGLE_API_KEY=your-google-key

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
```

### 8.2 Initial Setup Commands

```bash
# Create database
mysql -u root -p
CREATE DATABASE sipper_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'sipper_user'@'localhost' IDENTIFIED BY 'strong-password';
GRANT ALL PRIVILEGES ON sipper_db.* TO 'sipper_user'@'localhost';
FLUSH PRIVILEGES;

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Create necessary directories
mkdir -p media/dokumen media/qr_codes media/avatars
mkdir -p logs

# Run development server
python manage.py runserver
```

### 8.3 Production Deployment (Gunicorn + Nginx)

```bash
# Install Gunicorn
pip install gunicorn

# Create Gunicorn service file
sudo nano /etc/systemd/system/sipper.service

[Unit]
Description=SIPPER Django Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/home/sipper/sipper-app
ExecStart=/home/sipper/sipper-app/venv/bin/gunicorn \
    --workers 4 \
    --bind 127.0.0.1:8000 \
    sipper_config.wsgi:application

[Install]
WantedBy=multi-user.target

# Enable service
sudo systemctl daemon-reload
sudo systemctl enable sipper
sudo systemctl start sipper

# Nginx configuration
sudo nano /etc/nginx/sites-available/sipper

upstream sipper {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    client_max_body_size 5M;
    
    location /static/ {
        alias /home/sipper/sipper-app/static_root/;
    }
    
    location /media/ {
        alias /home/sipper/sipper-app/media/;
    }
    
    location / {
        proxy_pass http://sipper;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Enable nginx site
sudo ln -s /etc/nginx/sites-available/sipper /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# SSL Certificate (Let's Encrypt)
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

---

## 📋 Checklist Implementasi

- [ ] Setup virtual environment dan install dependencies
- [ ] Konfigurasi database MySQL
- [ ] Buat Django apps dan models
- [ ] Implementasi authentication system
- [ ] Setup tema hijau di frontend
- [ ] Buat template untuk semua halaman
- [ ] Implementasi fitur pendaftaran perantau
- [ ] Implementasi modul verifikasi petugas
- [ ] Integrasi QR code generation
- [ ] Setup logging dan audit trail
- [ ] Testing semua fitur
- [ ] Optimasi database queries
- [ ] Setup security headers
- [ ] Deploy ke production
- [ ] Setup monitoring dan backups

---

## 📞 Support & Dokumentasi

**Repository GitHub:** `sipper-e-government`  
**Author:** Development Team  
**Version:** 1.0.0  
**Last Updated:** 2024

---

**Selesai! Dokumentasi fullstack SIPPER sudah siap untuk implementasi.**
