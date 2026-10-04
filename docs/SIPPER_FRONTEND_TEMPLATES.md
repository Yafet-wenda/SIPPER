# Workspace Implementation Note

The current runnable templates are in the root `templates/` directory and use `base.html`, `home.html`, `application_v2.html`, `citizen_dashboard_v4.html`, `application_detail_v2.html`, and related active variants. The original multi-app template examples below remain reference material for future refactoring.

# SIPPER - Frontend Templates & Components
## HTML Templates & JavaScript Implementation

---

## 📁 Template Structure

```
templates/
├── base.html
├── home.html
├── dashboard.html
├── layouts/
│   ├── navbar.html
│   ├── sidebar.html
│   └── footer.html
├── users/
│   ├── login.html
│   ├── register.html
│   └── profile.html
├── perantau/
│   ├── dashboard.html
│   ├── pendaftaran.html
│   ├── upload_dokumen.html
│   ├── review_data.html
│   ├── edit_data.html
│   └── kartu_digital.html
├── verifikasi/
│   ├── dashboard_petugas.html
│   ├── list_pengajuan.html
│   ├── detail_pengajuan.html
│   └── statistik.html
├── kartu/
│   ├── validasi.html
│   └── qr_viewer.html
├── 404.html
└── 500.html
```

---

## 🎨 Layout Components

### navbar.html
```html
{% load static %}

<nav class="navbar navbar-expand-lg navbar-custom">
    <div class="container-fluid">
        <a class="navbar-brand" href="{% url 'core:home' %}">
            <i class="fas fa-globe"></i> <span>SIPPER</span>
        </a>
        
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
            <span class="navbar-toggler-icon"></span>
        </button>
        
        <div class="collapse navbar-collapse" id="navbarNav">
            <ul class="navbar-nav ms-auto">
                {% if user.is_authenticated %}
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" id="userDropdown" role="button" data-bs-toggle="dropdown">
                            <i class="fas fa-user-circle"></i> {{ user.first_name|default:user.username }}
                        </a>
                        <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="userDropdown">
                            <li><a class="dropdown-item" href="{% url 'users:profile' %}">Profil Saya</a></li>
                            {% if user.role == 'petugas' %}
                                <li><a class="dropdown-item" href="{% url 'verifikasi:dashboard' %}">Dashboard</a></li>
                            {% else %}
                                <li><a class="dropdown-item" href="{% url 'perantau:dashboard' %}">Dashboard</a></li>
                            {% endif %}
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item" href="{% url 'users:logout' %}">Logout</a></li>
                        </ul>
                    </li>
                {% else %}
                    <li class="nav-item">
                        <a class="nav-link" href="{% url 'users:login' %}">Login</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link btn btn-primary text-white ms-2" href="{% url 'users:register' %}">Daftar</a>
                    </li>
                {% endif %}
            </ul>
        </div>
    </div>
</nav>
```

### sidebar.html
```html
{% load static %}

<aside class="sidebar" id="sidebar">
    <div class="sidebar-header">
        <div class="sidebar-logo mb-3">
            <i class="fas fa-file-alt"></i> Menu
        </div>
    </div>
    
    <nav class="nav flex-column">
        {% if user.role == 'masyarakat' %}
            <!-- Menu Masyarakat -->
            <div class="sidebar-heading">Navigasi Utama</div>
            <a class="nav-link {% if request.resolver_match.url_name == 'dashboard' %}active{% endif %}" 
               href="{% url 'perantau:dashboard' %}">
                <i class="fas fa-home"></i> Dashboard
            </a>
            
            <div class="sidebar-heading mt-3">Pendataan</div>
            <a class="nav-link {% if request.resolver_match.url_name == 'pendaftaran' %}active{% endif %}" 
               href="{% url 'perantau:pendaftaran' %}">
                <i class="fas fa-edit"></i> Pendaftaran
            </a>
            <a class="nav-link {% if request.resolver_match.url_name == 'edit_data' %}active{% endif %}" 
               href="{% url 'perantau:edit_data' pk=user.profil_penduduk.id %}">
                <i class="fas fa-pen-square"></i> Edit Data
            </a>
            
            <div class="sidebar-heading mt-3">Dokumen & Kartu</div>
            <a class="nav-link" href="{% url 'kartu:view' %}">
                <i class="fas fa-id-card"></i> Kartu Digital
            </a>
            <a class="nav-link" href="{% url 'perantau:dashboard' %}#dokumen">
                <i class="fas fa-file-upload"></i> Dokumen Saya
            </a>
            
        {% elif user.role == 'petugas' %}
            <!-- Menu Petugas -->
            <div class="sidebar-heading">Navigasi Utama</div>
            <a class="nav-link {% if request.resolver_match.url_name == 'dashboard' %}active{% endif %}" 
               href="{% url 'verifikasi:dashboard' %}">
                <i class="fas fa-chart-line"></i> Dashboard
            </a>
            
            <div class="sidebar-heading mt-3">Verifikasi</div>
            <a class="nav-link {% if request.resolver_match.url_name == 'list_pengajuan' %}active{% endif %}" 
               href="{% url 'verifikasi:list_pengajuan' %}">
                <i class="fas fa-clipboard-list"></i> Daftar Pengajuan
            </a>
            <a class="nav-link" href="{% url 'verifikasi:list_pengajuan' %}?status=menunggu">
                <i class="fas fa-hourglass-half"></i> Menunggu Verifikasi
                <span class="badge badge-warning ms-2" id="pending-count">0</span>
            </a>
            
            <div class="sidebar-heading mt-3">Laporan & Analytics</div>
            <a class="nav-link {% if request.resolver_match.url_name == 'statistik' %}active{% endif %}" 
               href="{% url 'verifikasi:statistik' %}">
                <i class="fas fa-chart-bar"></i> Statistik
            </a>
            
        {% endif %}
        
        <div class="sidebar-heading mt-3">Pengaturan</div>
        <a class="nav-link" href="{% url 'users:profile' %}">
            <i class="fas fa-user"></i> Profil Saya
        </a>
        <a class="nav-link" href="{% url 'users:logout' %}">
            <i class="fas fa-sign-out-alt"></i> Logout
        </a>
    </nav>
</aside>

<style>
.navbar-custom {
    background: linear-gradient(135deg, #065f46 0%, #10b981 100%);
}
</style>
```

### footer.html
```html
<footer class="bg-dark text-white mt-5">
    <div class="container-fluid py-4">
        <div class="row">
            <div class="col-md-4 mb-4">
                <h5><i class="fas fa-globe"></i> SIPPER</h5>
                <p class="text-muted">Sistem Informasi Penduduk Perantauan - Platform digital untuk pendataan penduduk yang merantau</p>
            </div>
            <div class="col-md-4 mb-4">
                <h5>Link Cepat</h5>
                <ul class="list-unstyled">
                    <li><a href="#" class="text-muted">Tentang SIPPER</a></li>
                    <li><a href="#" class="text-muted">Panduan Penggunaan</a></li>
                    <li><a href="#" class="text-muted">Hubungi Kami</a></li>
                </ul>
            </div>
            <div class="col-md-4 mb-4">
                <h5>Informasi Kontak</h5>
                <p class="text-muted">
                    <i class="fas fa-phone"></i> +62 XXX XXXX XXXX<br>
                    <i class="fas fa-envelope"></i> info@sipper.gov.id
                </p>
            </div>
        </div>
        <hr class="bg-secondary">
        <div class="text-center text-muted">
            <p>&copy; 2024 SIPPER. Hak Cipta Dilindungi. Dikembangkan dengan <i class="fas fa-heart text-danger"></i></p>
        </div>
    </div>
</footer>
```

---

## 📄 Page Templates

### home.html (Landing Page)
```html
{% extends 'base.html' %}
{% load static %}

{% block title %}SIPPER - Sistem Informasi Penduduk Perantauan{% endblock %}

{% block content %}
<div class="bg-light">
    <!-- Hero Section -->
    <section class="py-5" style="background: linear-gradient(135deg, #065f46 0%, #10b981 100%); color: white;">
        <div class="container">
            <div class="row align-items-center">
                <div class="col-lg-6">
                    <h1 class="display-4 fw-bold mb-3">
                        <i class="fas fa-globe"></i> Selamat Datang di SIPPER
                    </h1>
                    <p class="lead mb-4">
                        Platform digital untuk pendataan dan verifikasi penduduk yang merantau
                    </p>
                    <div class="d-flex gap-2">
                        <a href="{% url 'users:login' %}" class="btn btn-light btn-lg">
                            <i class="fas fa-sign-in-alt"></i> Login
                        </a>
                        <a href="{% url 'users:register' %}" class="btn btn-outline-light btn-lg">
                            <i class="fas fa-user-plus"></i> Daftar Baru
                        </a>
                    </div>
                </div>
                <div class="col-lg-6 text-center">
                    <img src="{% static 'img/hero-illustration.svg' %}" alt="SIPPER" class="img-fluid" style="max-width: 400px;">
                </div>
            </div>
        </div>
    </section>
    
    <!-- Statistics Section -->
    <section class="py-5">
        <div class="container">
            <div class="row">
                <div class="col-md-4 text-center mb-4">
                    <div class="stat-card rounded-lg p-4">
                        <div style="font-size: 2rem; color: #10b981;">
                            <i class="fas fa-users"></i>
                        </div>
                        <h3 class="text-dark mt-3">{{ total_perantau }}</h3>
                        <p class="text-muted">Total Perantau Terdaftar</p>
                    </div>
                </div>
                <div class="col-md-4 text-center mb-4">
                    <div class="stat-card rounded-lg p-4">
                        <div style="font-size: 2rem; color: #10b981;">
                            <i class="fas fa-check-circle"></i>
                        </div>
                        <h3 class="text-dark mt-3">{{ pengajuan_disetujui }}</h3>
                        <p class="text-muted">Pengajuan Disetujui</p>
                    </div>
                </div>
                <div class="col-md-4 text-center mb-4">
                    <div class="stat-card rounded-lg p-4">
                        <div style="font-size: 2rem; color: #10b981;">
                            <i class="fas fa-hourglass-half"></i>
                        </div>
                        <h3 class="text-dark mt-3">{{ pengajuan_menunggu }}</h3>
                        <p class="text-muted">Menunggu Verifikasi</p>
                    </div>
                </div>
            </div>
        </div>
    </section>
    
    <!-- Features Section -->
    <section class="py-5 bg-white">
        <div class="container">
            <h2 class="text-center text-dark mb-5">Fitur Utama SIPPER</h2>
            <div class="row">
                <div class="col-md-6 mb-4">
                    <div class="card rounded-lg border-0 shadow-sm">
                        <div class="card-body p-4">
                            <h5 class="text-primary mb-2">
                                <i class="fas fa-edit"></i> Pendaftaran Mudah
                            </h5>
                            <p class="text-muted">
                                Daftarkan data perantauan Anda dengan form yang user-friendly dan intuitif
                            </p>
                        </div>
                    </div>
                </div>
                <div class="col-md-6 mb-4">
                    <div class="card rounded-lg border-0 shadow-sm">
                        <div class="card-body p-4">
                            <h5 class="text-primary mb-2">
                                <i class="fas fa-shield-alt"></i> Verifikasi Aman
                            </h5>
                            <p class="text-muted">
                                Sistem verifikasi berlapis untuk memastikan keamanan dan keakuratan data
                            </p>
                        </div>
                    </div>
                </div>
                <div class="col-md-6 mb-4">
                    <div class="card rounded-lg border-0 shadow-sm">
                        <div class="card-body p-4">
                            <h5 class="text-primary mb-2">
                                <i class="fas fa-id-card"></i> Kartu Digital
                            </h5>
                            <p class="text-muted">
                                Dapatkan kartu digital dengan QR Code sebagai bukti pendataan resmi
                            </p>
                        </div>
                    </div>
                </div>
                <div class="col-md-6 mb-4">
                    <div class="card rounded-lg border-0 shadow-sm">
                        <div class="card-body p-4">
                            <h5 class="text-primary mb-2">
                                <i class="fas fa-chart-bar"></i> Analytics Real-time
                            </h5>
                            <p class="text-muted">
                                Dashboard statistik untuk pemantauan dan analisis data perantauan secara real-time
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>
    
    <!-- How It Works Section -->
    <section class="py-5">
        <div class="container">
            <h2 class="text-center text-dark mb-5">Cara Kerja SIPPER</h2>
            <div class="row">
                <div class="col-md-3 text-center mb-4">
                    <div class="wizard-step active">
                        <div class="step-number">1</div>
                    </div>
                    <h5 class="text-dark">Daftar Akun</h5>
                    <p class="text-muted small">Buat akun dengan email dan password yang aman</p>
                </div>
                <div class="col-md-3 text-center mb-4">
                    <div class="wizard-step">
                        <div class="step-number">2</div>
                    </div>
                    <h5 class="text-dark">Isi Data</h5>
                    <p class="text-muted small">Lengkapi form data perantauan Anda dengan teliti</p>
                </div>
                <div class="col-md-3 text-center mb-4">
                    <div class="wizard-step">
                        <div class="step-number">3</div>
                    </div>
                    <h5 class="text-dark">Upload Dokumen</h5>
                    <p class="text-muted small">Upload dokumen pendukung (KTP, surat kerja, dll)</p>
                </div>
                <div class="col-md-3 text-center mb-4">
                    <div class="wizard-step">
                        <div class="step-number">4</div>
                    </div>
                    <h5 class="text-dark">Dapatkan Kartu</h5>
                    <p class="text-muted small">Tunggu verifikasi dan terima kartu digital Anda</p>
                </div>
            </div>
        </div>
    </section>
</div>

<style>
.stat-card {
    background: linear-gradient(135deg, #d1fae5 0%, white 100%);
    border-left: 4px solid #10b981;
}

.wizard-step {
    position: relative;
    margin-bottom: 2rem;
}

.wizard-step .step-number {
    width: 50px;
    height: 50px;
    border-radius: 50%;
    background-color: #10b981;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    font-weight: bold;
    margin: 0 auto 1rem;
}
</style>
{% endblock %}
```

### users/login.html
```html
{% extends 'base.html' %}
{% load static %}
{% load crispy_forms_tags %}

{% block title %}Login - SIPPER{% endblock %}

{% block content %}
<div class="container d-flex align-items-center justify-content-center" style="min-height: 100vh;">
    <div class="w-100" style="max-width: 400px;">
        <div class="card rounded-lg shadow-lg border-0">
            <div class="card-body p-5">
                <div class="text-center mb-4">
                    <div style="font-size: 3rem; color: #10b981;">
                        <i class="fas fa-sign-in-alt"></i>
                    </div>
                    <h2 class="text-dark mt-3">Login SIPPER</h2>
                    <p class="text-muted">Masuk ke akun Anda</p>
                </div>
                
                {% if messages %}
                    {% for message in messages %}
                        <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}
                
                <form method="post">
                    {% csrf_token %}
                    
                    <div class="mb-3">
                        <label for="id_email" class="form-label">Email</label>
                        <input type="email" class="form-control form-control-lg" id="id_email" name="email" 
                               placeholder="Masukkan email Anda" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="id_password" class="form-label">Password</label>
                        <input type="password" class="form-control form-control-lg" id="id_password" name="password" 
                               placeholder="Masukkan password Anda" required>
                    </div>
                    
                    <button type="submit" class="btn btn-primary btn-lg w-100">
                        <i class="fas fa-sign-in-alt"></i> Login
                    </button>
                </form>
                
                <hr class="my-4">
                
                <p class="text-center text-muted">
                    Belum punya akun? <a href="{% url 'users:register' %}" class="text-primary fw-bold">Daftar di sini</a>
                </p>
            </div>
        </div>
        
        <p class="text-center text-muted mt-4 small">
            <i class="fas fa-lock"></i> Informasi Anda dilindungi dengan enkripsi SSL
        </p>
    </div>
</div>
{% endblock %}
```

### perantau/pendaftaran.html
```html
{% extends 'base.html' %}
{% load static %}
{% load crispy_forms_tags %}

{% block title %}Pendaftaran Perantau - SIPPER{% endblock %}

{% block content %}
<div class="container-fluid">
    <div class="row">
        <div class="col-lg-8 mx-auto">
            <!-- Progress Bar -->
            <div class="mb-4">
                <div class="card border-0 shadow-sm">
                    <div class="card-body">
                        <h5 class="card-title text-dark mb-3">Langkah Pendaftaran</h5>
                        <div class="progress" style="height: 25px;">
                            <div class="progress-bar bg-success" role="progressbar" 
                                 style="width: 33%" aria-valuenow="33" aria-valuemin="0" aria-valuemax="100">
                                1. Data Pribadi
                            </div>
                            <div class="progress-bar bg-light text-dark" role="progressbar" 
                                 style="width: 33%" aria-valuenow="33" aria-valuemin="0" aria-valuemax="100">
                                2. Upload Dokumen
                            </div>
                            <div class="progress-bar bg-light text-dark" role="progressbar" 
                                 style="width: 33%" aria-valuenow="33" aria-valuemin="0" aria-valuemax="100">
                                3. Review & Submit
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Form Section -->
            <div class="card border-0 shadow-lg rounded-lg">
                <div class="card-header bg-light border-bottom-2">
                    <h4 class="mb-0 text-dark">
                        <i class="fas fa-edit"></i> Data Pribadi Perantau
                    </h4>
                </div>
                
                <div class="card-body p-4">
                    {% if messages %}
                        {% for message in messages %}
                            <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
                                {{ message }}
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        {% endfor %}
                    {% endif %}
                    
                    <form method="post" novalidate>
                        {% csrf_token %}
                        
                        <!-- Identitas Section -->
                        <h5 class="text-primary mb-3">
                            <i class="fas fa-id-card"></i> Identitas
                        </h5>
                        
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label for="id_nik" class="form-label">NIK <span class="text-danger">*</span></label>
                                <input type="text" class="form-control {% if form.nik.errors %}is-invalid{% endif %}" 
                                       id="id_nik" name="nik" placeholder="16 digit NIK" pattern="\d{16}" maxlength="16">
                                {% if form.nik.errors %}
                                    <div class="invalid-feedback d-block">{{ form.nik.errors.0 }}</div>
                                {% endif %}
                            </div>
                            <div class="col-md-6">
                                <label for="id_nama" class="form-label">Nama Lengkap <span class="text-danger">*</span></label>
                                <input type="text" class="form-control {% if form.nama.errors %}is-invalid{% endif %}" 
                                       id="id_nama" name="nama" placeholder="Nama sesuai NIK">
                                {% if form.nama.errors %}
                                    <div class="invalid-feedback d-block">{{ form.nama.errors.0 }}</div>
                                {% endif %}
                            </div>
                        </div>
                        
                        <!-- Lokasi Asal Section -->
                        <h5 class="text-primary mb-3 mt-4">
                            <i class="fas fa-map-marker-alt"></i> Lokasi Asal
                        </h5>
                        
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label for="id_daerah_asal" class="form-label">Kota/Kabupaten Asal <span class="text-danger">*</span></label>
                                <input type="text" class="form-control" id="id_daerah_asal" name="daerah_asal">
                            </div>
                            <div class="col-md-6">
                                <label for="id_provinsi_asal" class="form-label">Provinsi Asal</label>
                                <input type="text" class="form-control" id="id_provinsi_asal" name="provinsi_asal">
                            </div>
                        </div>
                        
                        <!-- Lokasi Tujuan Section -->
                        <h5 class="text-primary mb-3 mt-4">
                            <i class="fas fa-location-arrow"></i> Lokasi Tujuan
                        </h5>
                        
                        <div class="mb-3">
                            <label for="id_alamat_tujuan" class="form-label">Alamat Lengkap <span class="text-danger">*</span></label>
                            <textarea class="form-control" id="id_alamat_tujuan" name="alamat_tujuan" 
                                      rows="4" placeholder="Jalan, No., Kelurahan, Kecamatan"></textarea>
                        </div>
                        
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label for="id_provinsi_tujuan" class="form-label">Provinsi Tujuan <span class="text-danger">*</span></label>
                                <input type="text" class="form-control" id="id_provinsi_tujuan" name="provinsi_tujuan">
                            </div>
                            <div class="col-md-6">
                                <label for="id_kabupaten_tujuan" class="form-label">Kabupaten/Kota Tujuan <span class="text-danger">*</span></label>
                                <input type="text" class="form-control" id="id_kabupaten_tujuan" name="kabupaten_tujuan">
                            </div>
                        </div>
                        
                        <!-- Tujuan Merantau Section -->
                        <h5 class="text-primary mb-3 mt-4">
                            <i class="fas fa-graduation-cap"></i> Tujuan Merantau
                        </h5>
                        
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label for="id_tujuan_merantau" class="form-label">Alasan Merantau <span class="text-danger">*</span></label>
                                <select class="form-select" id="id_tujuan_merantau" name="tujuan_merantau">
                                    <option value="">-- Pilih Alasan --</option>
                                    <option value="pendidikan">Pendidikan</option>
                                    <option value="pekerjaan">Pekerjaan</option>
                                    <option value="usaha">Pengembangan Usaha</option>
                                    <option value="keluarga">Kepentingan Keluarga</option>
                                    <option value="lainnya">Lainnya</option>
                                </select>
                            </div>
                            <div class="col-md-6">
                                <label for="id_tanggal_mulai" class="form-label">Tanggal Mulai Merantau <span class="text-danger">*</span></label>
                                <input type="date" class="form-control" id="id_tanggal_mulai" name="tanggal_mulai">
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label for="id_perkiraan_kembali" class="form-label">Perkiraan Tanggal Kembali</label>
                            <input type="date" class="form-control" id="id_perkiraan_kembali" name="perkiraan_kembali">
                        </div>
                        
                        <!-- Buttons -->
                        <div class="d-flex gap-2 mt-4">
                            <button type="submit" class="btn btn-primary btn-lg">
                                <i class="fas fa-arrow-right"></i> Lanjutkan ke Upload Dokumen
                            </button>
                            <a href="{% url 'perantau:dashboard' %}" class="btn btn-outline-secondary btn-lg">
                                <i class="fas fa-times"></i> Batal
                            </a>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

---

## 🎯 JavaScript Components

### static/js/main.js
```javascript
// ============================================
// SIPPER - Main JavaScript
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    initializeSidebar();
    initializeFormValidation();
    initializeFileUpload();
    initializeTooltips();
    updatePendingCount();
}

// ============================================
// Sidebar Toggle (Mobile)
// ============================================

function initializeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.querySelector('.sidebar-toggle');
    
    if (toggleBtn) {
        toggleBtn.addEventListener('click', function(e) {
            e.preventDefault();
            sidebar.classList.toggle('show');
        });
    }
    
    // Close sidebar when clicking outside
    document.addEventListener('click', function(e) {
        if (sidebar && !sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
            sidebar.classList.remove('show');
        }
    });
}

// ============================================
// Form Validation
// ============================================

function initializeFormValidation() {
    const forms = document.querySelectorAll('form:not(.no-validation)');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
}

// ============================================
// File Upload Drag & Drop
// ============================================

function initializeFileUpload() {
    const uploadAreas = document.querySelectorAll('.document-upload-area');
    
    uploadAreas.forEach(area => {
        const fileInput = area.querySelector('input[type="file"]');
        
        if (fileInput) {
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                area.addEventListener(eventName, preventDefaults, false);
            });
            
            ['dragenter', 'dragover'].forEach(eventName => {
                area.addEventListener(eventName, highlight, false);
            });
            
            ['dragleave', 'drop'].forEach(eventName => {
                area.addEventListener(eventName, unhighlight, false);
            });
            
            area.addEventListener('drop', handleDrop, false);
            
            function handleDrop(e) {
                const dt = e.dataTransfer;
                const files = dt.files;
                fileInput.files = files;
                
                // Trigger change event
                const changeEvent = new Event('change', { bubbles: true });
                fileInput.dispatchEvent(changeEvent);
            }
            
            function highlight(e) {
                area.classList.add('drag-over');
            }
            
            function unhighlight(e) {
                area.classList.remove('drag-over');
            }
            
            function preventDefaults(e) {
                e.preventDefault();
                e.stopPropagation();
            }
            
            // Click to upload
            area.addEventListener('click', function() {
                fileInput.click();
            });
        }
    });
}

// ============================================
// Bootstrap Tooltips
// ============================================

function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// ============================================
// Update Pending Count
// ============================================

function updatePendingCount() {
    fetch('/api/pending-count/', {
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        const countEl = document.getElementById('pending-count');
        if (countEl && data.count > 0) {
            countEl.textContent = data.count;
            countEl.style.display = 'inline-block';
        }
    })
    .catch(error => console.error('Error:', error));
}

// ============================================
// CSRF Token Handler
// ============================================

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// ============================================
// Utility Functions
// ============================================

function showAlert(message, type = 'info') {
    const alertHTML = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    const alertContainer = document.querySelector('.alert-container') || document.body;
    alertContainer.insertAdjacentHTML('afterbegin', alertHTML);
}

function formatDate(date) {
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return new Date(date).toLocaleDateString('id-ID', options);
}

function formatCurrency(value) {
    return new Intl.NumberFormat('id-ID', {
        style: 'currency',
        currency: 'IDR'
    }).format(value);
}

// ============================================
// API Helper Functions
// ============================================

async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    const response = await fetch(endpoint, options);
    return await response.json();
}

// ============================================
// Charts Integration (for statistik page)
// ============================================

function initializeCharts() {
    // Gunakan Chart.js atau library lain untuk visualisasi
    const chartElements = document.querySelectorAll('[data-chart]');
    
    chartElements.forEach(element => {
        const chartType = element.getAttribute('data-chart');
        const chartData = JSON.parse(element.getAttribute('data-chart-data'));
        
        // Initialize chart based on type
        // Ini adalah placeholder, sesuaikan dengan library chart yang digunakan
    });
}

// ============================================
// Real-time Updates
// ============================================

function setupRealtimeUpdates() {
    // Setup WebSocket atau polling untuk update real-time
    setInterval(() => {
        updatePendingCount();
    }, 30000); // Update setiap 30 detik
}

// ============================================
// Print Functions
// ============================================

function printElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        const printWindow = window.open('', '', 'height=400,width=800');
        printWindow.document.write(element.innerHTML);
        printWindow.document.close();
        printWindow.print();
    }
}

function downloadPDF(elementId, filename) {
    // Gunakan library seperti html2pdf atau similar
    // Placeholder untuk implementasi
    console.log(`Downloading ${filename} from ${elementId}`);
}

// ============================================
// Performance Optimization
// ============================================

// Lazy loading images
if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.classList.remove('lazy');
                observer.unobserve(img);
            }
        });
    });
    
    document.querySelectorAll('img.lazy').forEach(img => {
        imageObserver.observe(img);
    });
}
```

---

## 🌐 API Endpoints

### API untuk Frontend Interactions

```javascript
// Create Django URL patterns untuk API

// urls.py
urlpatterns = [
    path('api/pending-count/', views.api_pending_count, name='api_pending_count'),
    path('api/perantau/status/', views.api_perantau_status, name='api_perantau_status'),
    path('api/chart-data/', views.api_chart_data, name='api_chart_data'),
    path('api/validate-nik/', views.api_validate_nik, name='api_validate_nik'),
]

# views.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
def api_pending_count(request):
    if request.user.role != 'petugas':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    count = Pengajuan.objects.filter(status='menunggu').count()
    return JsonResponse({'count': count})

@login_required
def api_perantau_status(request):
    if request.user.role != 'masyarakat':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        penduduk = request.user.profil_penduduk
        pengajuan = penduduk.pengajuan
        return JsonResponse({
            'status': pengajuan.status,
            'last_update': pengajuan.tanggal_verifikasi.isoformat() if pengajuan.tanggal_verifikasi else None
        })
    except:
        return JsonResponse({'error': 'No data found'}, status=404)
```

---

## 📱 Responsive Design Breakpoints

Tema hijau SIPPER menggunakan Bootstrap 5 breakpoints:
- **xs**: < 576px (Mobile)
- **sm**: ≥ 576px (Tablet)
- **md**: ≥ 768px (Tablet Landscape)
- **lg**: ≥ 992px (Desktop)
- **xl**: ≥ 1200px (Large Desktop)
- **xxl**: ≥ 1400px (Extra Large)

---

## 🎨 Color Palette Reference

```css
Primary Dark (#065f46) - Headers, Sidebar
Primary (#10b981) - Buttons, Links, Accents
Primary Light (#d1fae5) - Card Headers, Backgrounds
Primary Lighter (#f0fdf4) - Light Backgrounds
Secondary (#059669) - Hover States
Success (#10b981) - Positive Actions
Danger (#dc2626) - Destructive Actions
Warning (#f59e0b) - Warnings
Info (#0ea5e9) - Information
```

---

**Template dan komponen frontend siap digunakan!**
