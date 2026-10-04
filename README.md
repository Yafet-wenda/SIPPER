# 🏛️ SIPPER — Sistem Informasi Penduduk Perantauan

> **Supporting System Digitalisasi Pendataan & Pemutakhiran Data Perantau Berbasis E-Government**  
> *Proyek Workshop Pemrograman Framework (PENS)*

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Django-4.2%2B-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Database](https://img.shields.io/badge/MySQL-8.0%2B-4479A1?style=for-the-badge&logo=mysql&logoColor=white)](https://www.mysql.com/)
[![UI Framework](https://img.shields.io/badge/Bootstrap-5.3-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![License](https://img.shields.io/badge/License-Academic-blue?style=for-the-badge)](#-batasan-sistem--disclaimer)

---

## 📋 Ikhtisar Proyek

Perpindahan penduduk antar daerah untuk studi, pekerjaan, maupun bisnis seringkali dinamis dan membutuhkan validasi cepat. Pendataan manual kependudukan resmi (seperti KTP/KK) kerap memakan waktu dan kurang fleksibel untuk pemantauan taktis wilayah.

**SIPPER (Sistem Informasi Penduduk Perantauan)** hadir sebagai *supporting system* kependudukan taktis berbasis web. Aplikasi ini menghubungkan partisipasi aktif warga perantau (*Citizen*) dengan verifikasi taktis pemerintah lokal (*Government*) secara real-time.

```
┌─────────────────┐        1. Pengajuan Data & Berkas       ┌──────────────────┐
│                 ├────────────────────────────────────────►│                  │
│  Warga Perantau │                                         │    Pemerintah /  │
│   (Masyarakat)  │◄────────────────────────────────────────┤     Petugas      │
└─────────────────┘   3. Kartu Digital + Validation QR      └────────┬─────────┘
                                                                     │ 2. Pre-Screening &
                                                                     ▼    Verifikasi Berkas
                                                            ┌──────────────────┐
                                                            │  Agentic AI &    │
                                                            │  Validation Engine│
                                                            └──────────────────┘

## ✨ Fitur Utama

### 🧑‍💼 Modul Masyarakat (Perantau)
- **Portal Pendataan Multi-Step**: Pendaftaran akun dan pengisian formulir data domisili asal, alamat tujuan, durasi tinggal, serta alasan merantau.
- **Upload & Pre-screen Berkas**: Pengunggahan dokumen pendukung (KTP/Surat Tugas) dengan *auto-check* konsistensi data.
- **Kartu Digital & Dynamic QR Code**: Penerbitan kartu identitas perantau digital setelah pengajuan disetujui. QR Code dapat dipindai untuk validasi publik.
- **Pemutakhiran Data Mandiri**: Pelaporan perubahan alamat tujuan, perpanjangan durasi tinggal, atau konfirmasi kembali ke daerah asal.

### 🏛️ Modul Pemerintah / Petugas
- **Monitoring Dashboard**: Visualisasi ringkas statistik perantau aktif, jumlah pengajuan masuk, dan grafik tujuan merantau.
- **Panel Verifikasi Berkas**: Antarmuka review pengajuan dengan fitur opsi *Approve*, *Reject*, atau *Minta Perbaikan* disertai catatan petugas.
- **Validasi QR Code**: Fitur scan QR Code untuk memverifikasi keabsahan kartu digital warga secara *on-the-spot*.

### 🤖 Agentic AI Smart Assistant *(Experimental)*
- Skrip backend Python untuk membantu pra-verifikasi kelengkapan dokumen pendukung dan ekstraksi data NIK/Nama secara otomatis sebelum masuk antrean verifikasi petugas (confidence threshold standard > 85%).

---

## 🛠️ Tech Stack

| Layer | Teknologi / Library | Deskripsi Fungsi |
| :--- | :--- | :--- |
| **Language** | `Python 3.10+` | Bahasa pemrograman utama logika backend |
| **Framework** | `Django 4.2+` | Full-stack web framework (MVT structure, ORM, Auth) |
| **Database** | `MySQL 8.0+` | Datastore relasional untuk entitas user, pengajuan, & dokumen |
| **DB Connector** | `mysqlclient` / `PyMySQL` | Driver penghubung Django ORM ke MySQL |
| **Frontend UI** | `HTML5`, `CSS3`, `JavaScript` | Struktur tampilan antarmuka web |
| **CSS Framework**| `Bootstrap 5.3` | Grid system responsif dan komponen UI modern |
| **AI Processing** | `LangChain` / `OpenAI API` / `PyPDF2` | Agentic AI OCR & assistant pra-verifikasi dokumen |
| **Utils** | `qrcode`, `Pillow` | Library Python untuk generate gambar QR Code kartu |

---

## 📂 Struktur Direktori Proyek

```text
sipper-e-government/
├── core/                           # Main Django App (Business Logic)
│   ├── models.py                   # ORM Models (Users, Penduduk, Pengajuan, DLL)
│   ├── views.py                    # Logic Request-Response & RBAC Views
│   ├── urls.py                     # App Level Routing URL
│   ├── forms.py                    # Django Forms & Validation Rules
│   └── admin.py                    # Customized Django Admin Interface
│
├── sipper/                         # Project Configuration
│   ├── settings.py                 # Core Settings & DB Connection
│   ├── urls.py                     # Root URL Router
│   └── wsgi.py / asgi.py           # Deployment Handlers
│
├── docs/                           # 📚 Dokumentasi Teknis Lengkap
│   ├── SIPPER_FULLSTACK_GUIDE.md   # Panduan Arsitektur Backend & Flow API
│   ├── SIPPER_FRONTEND_TEMPLATES.md# Spesifikasi Template UI & Bootstrap
│   ├── SIPPER_SETUP_DEPLOYMENT.md  # Panduan Instalasi Server & Deployment
│   └── SIPPER_QUICK_REFERENCE.md   # Cheat Sheet CLI Commands
│
├── templates/                      # HTML Views
│   ├── base.html                   # Base Layout & Navbar Dynamic
│   ├── beranda.html                # Landing Page
│   ├── masyarakat/                 # View Formulir, Status & Kartu Digital
│   └── pemerintah/                 # View Dashboard Verifikasi Petugas
│
├── static/                         # Static Assets (Custom CSS, JS, Brand Logos)
├── media/                          # Uploaded User Documents & Generated QRs (.gitignore)
│
├── .gitignore                      # Environment & Sensitive File Filter
├── manage.py                       # Django CLI Utility Script
├── requirements.txt                # Python Dependencies
└── README.md                       # Dokumentasi Utama Repositori



## 🗄️ Skema Database Singkat (`sipper_db`)

Sistem mengelola 6 tabel utama menggunakan Django Migration:

1. `users` — Akun otentikasi (Masyarakat / Petugas).
2. `penduduk` — Profil data detail perantau & status domisili.
3. `pengajuan` — Workflow status verifikasi (`Menunggu`, `Disetujui`, `Ditolak`).
4. `dokumen` — Path penyimpanan berkas pendukung (KTP/Surat Keterangan).
5. `pemutakhiran` — Audit log histori perubahan alamat/status perantau.
6. `kartu_digital` — Token verifikasi unik & path file QR Code.

> Detail tipe data dan constraint constraint skema selengkapnya terdapat pada [`docs/SIPPER_FULLSTACK_GUIDE.md`](docs/SIPPER_FULLSTACK_GUIDE.md).



## ⚡ Panduan Instalasi Lokal

### 1. Prasyarat System

- Python version `3.10` atau yang lebih baru.
- MySQL Server versi `8.0+` aktif.
- Git Installed.

### 2. Clone Repositori & Virtual Environment

```bash
# 1. Clone Repositori
git clone https://github.com/username/sipper-e-government.git
cd sipper-e-government

# 2. Buat Virtual Environment
python -m venv venv

# 3. Aktivasi Environment (Windows PowerShell / CMD)
venv\Scriptsctivate
# Jika di MacOS / Linux: source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Konfigurasi Database & Environment Variable

Buat database baru di MySQL Workbench / phpMyAdmin dengan nama `sipper_db`.

Sesuaikan pengaturan koneksi database pada file `sipper/settings.py` atau buat file `.env`:

```env
DB_NAME=sipper_db
DB_USER=root
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

### 5. Jalankan Migration & Development Server

bash

# Run Database Migrations

python manage.py makemigrations
python manage.py migrate

# Buat Akun Superuser/Admin (Opsional)

python manage.py createsuperuser

# Jalankan Server Development

python manage.py runserver
Buka browser dan akses aplikasi melalui `http://127.0.0.1:8000/`.

---

## 🔒 Batasan Sistem & Disclaimer

1. **Batasan Akademis**: SIPPER dikembangkan khusus untuk memenuhi tugas proyek mata kuliah **Workshop Pemrograman Framework** (Politeknik Elektronika Negeri Surabaya - PENS).
2. **Bukan Dokumen Legal Utama**: Kartu Digital SIPPER **bukan** pengganti KTP-el, Kartu Keluarga, maupun Surat Keterangan Pindah (SKPWNI) resmi penerbitan Dukcapil.
3. **Integrasi Data**: Sistem ini tidak terhubung secara langsung ke basis data nasional Dukcapil. Seluruh data pada fase pengembangan menggunakan data simulasi (*dummy data*).

## Implementasi Saat Ini

Implementasi aktif menggunakan satu aplikasi Django `core` dengan **MariaDB bawaan XAMPP (10.4)** di port 3306. Karena Django 5.2 resmi mensyaratkan MariaDB 10.5, `sipper/__init__.py` memuat shim kompatibilitas kecil (turunkan gerbang versi + matikan `INSERT ... RETURNING` yang belum ada di 10.4); 19/19 test lolos dengan shim ini. phpMyAdmin dipakai lewat Apache saja. Fitur aktif meliputi akun masyarakat/petugas, pengajuan, upload dokumen maksimal 5 MB, review dokumen, histori pemutakhiran, QR card, PDF card, statistik, CSV export, reset password, backup, dan scanner QR.

### Menjalankan Lokal

```powershell
# Prasyarat: panel XAMPP -> Start pada Apache dan MySQL (MariaDB)
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Backup data dapat dibuat dengan `.venv\Scripts\python.exe manage.py backup_db`. Kredensial koneksi dev ada di `.env` (`DB_USER=sipper`, lihat `DB_PASSWORD` di `.env`, host `127.0.0.1:3306`, database `sipper_db`).

### URL Utama

- `/` beranda
- `/daftar/` dan `/login/` akun
- `/dashboard/` dashboard warga atau petugas
- `/petugas/` antrean verifikasi
- `/petugas/statistik/` grafik statistik
- `/scan-kartu/` scanner QR
- `/admin/` administrasi Django

### Administrasi Master

Akun superuser dapat memakai `/admin/` sebagai pusat kendali. Dashboard admin menampilkan statistik live yang diperbarui setiap 15 detik, pengajuan terbaru, aktivitas audit, dan jumlah dokumen yang menunggu review. Setiap model memiliki pencarian, filter, pagination, dan aksi massal yang relevan.

Perintah pengelolaan role:

```powershell
py manage.py promote_officer <username>
```

---

## 👥 Tim Penyusun

- **Yafet Wenda** (NRP: `3125521058`)
- **Muhammad Ai Nur Haaq** (NRP: `3125521052`)

**Dosen Pengampu:**  
Evianita Dewi Fajrianti, S.Tr.T., M.Tr.T

---

<p align="center">
  <sub>Built with ❤️ using Python & Django framework for Digital E-Government Innovation.</sub>
</p>
