# 🏛️ SIPPER — Sistem Informasi Penduduk Perantauan

> *Supporting system* digitalisasi pendataan dan pemutakhiran data perantau berbasis e-government.
> Proyek Workshop Pemrograman Framework — Politeknik Elektronika Negeri Surabaya (PENS)

[![CI](https://github.com/Yafet-wenda/SIPPER/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/Yafet-wenda/SIPPER/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.13%20%7C%203.14-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![MariaDB](https://img.shields.io/badge/MariaDB-10.4%20%28XAMPP%29-4479A1?style=for-the-badge&logo=mariadb&logoColor=white)](https://mariadb.org/)
[![License](https://img.shields.io/badge/License-Academic-blue?style=for-the-badge)](#-batasan-sistem-dan-disclaimer)

---

## 📌 Ringkasan Proyek

| Aspek | Keterangan |
| :--- | :--- |
| Mata kuliah | Workshop Pemrograman Framework, PENS |
| Dosen pengampu | Evianita Dewi Fajrianti, S.Tr.T., M.Tr.T |
| Penyusun | Yafet Wenda (NRP 3125521058), Muhammad Ai Nur Haaq (NRP 3125521052) |
| Rerangka | Django 5.2 dengan satu aplikasi utama, `core` |
| Basis data | MariaDB 10.4 (bawaan XAMPP) melalui PyMySQL; SQLite tersedia sebagai jalur uji cepat |
| Pengujian | 38 pengujian otomatis, seluruhnya lolos |
| Integrasi berkelanjutan | GitHub Actions — lihat [Pengujian dan CI](#-pengujian-dan-ci) dan [`docs/ci-status.md`](docs/ci-status.md) |
| Visibilitas | Repo privat, karena sistem memuat data turunan KTP warga |

---

## 📋 Ikhtisar Proyek

Perpindahan penduduk antar daerah untuk studi, pekerjaan, maupun bisnis bersifat dinamis dan membutuhkan validasi cepat. Pendataan manual kependudukan resmi seperti KTP dan KK kerap memakan waktu serta kurang fleksibel untuk pemantauan taktis wilayah.

**SIPPER (Sistem Informasi Penduduk Perantauan)** hadir sebagai *supporting system* kependudukan taktis berbasis web. Aplikasi ini menghubungkan partisipasi aktif warga perantau (*Citizen*) dengan verifikasi pemerintah lokal (*Government*) secara langsung.

```text
┌─────────────────┐        1. Pengajuan Data dan Berkas       ┌──────────────────┐
│                 ├──────────────────────────────────────────►│                  │
│  Warga Perantau │                                           │    Pemerintah /  │
│   (Masyarakat)  │◄──────────────────────────────────────────┤     Petugas      │
└─────────────────┘     3. Kartu Digital + Validasi QR        └────────┬─────────┘
                                                                       │ 2. Pra-pemeriksaan
                                                                       ▼    dan Verifikasi Berkas
                                                              ┌──────────────────┐
                                                              │  Aturan Validasi │
                                                              │   dan Audit di   │
                                                              │      Django      │
                                                              └──────────────────┘
```

---

## ✨ Fitur Utama

### 🧑‍💼 Modul Masyarakat (Perantau)

- **Portal Pendataan Bertahap**: pendaftaran akun dan pengisian formulir domisili asal, alamat tujuan, durasi tinggal, serta alasan merantau.
- **Unggah dan Pra-pemeriksaan Berkas**: dokumen pendukung (KTP/Surat Tugas) maksimal 5 MB, dengan pemeriksaan tipe berkas (`pdf`, `jpeg`, `png`), batas ukuran di *middleware*, dan validasi format NIK melalui `api/validate-nik/`.
- **Kartu Digital dan QR Code**: kartu identitas perantau terbit setelah pengajuan disetujui, dilengkapi berkas QR dan unduhan PDF. QR dapat dipindai untuk validasi publik.
- **Pemutakhiran Data Mandiri**: pelaporan perubahan alamat tujuan, perpanjangan durasi tinggal, atau konfirmasi kembali ke daerah asal, lengkap dengan riwayat.

### 🏛️ Modul Pemerintah (Petugas)

- **Dasbor Monitoring**: visualisasi ringkas statistik perantau aktif, jumlah pengajuan masuk, dan grafik tujuan merantau.
- **Panel Verifikasi Berkas**: antarmuka peninjauan pengajuan dengan opsi *Approve*, *Reject*, atau *Minta Perbaikan* disertai catatan petugas.
- **Validasi Kode QR**: pemindaian QR lewat kamera (`html5-qrcode`) untuk memastikan keabsahan kartu digital warga di lokasi, dengan alternatif masukan kode manual bila kamera tidak tersedia.
- **Ekspor dan Audit**: ekspor CSV daftar pengajuan (`/petugas/?export=csv`) serta `AuditLog` untuk setiap aksi petugas.

### 🤖 Pra-verifikasi Otomatis

Pra-verifikasi yang berjalan saat ini **berbasis aturan di Django**, bukan model AI: validasi struktur NIK, kelengkapan isian, tipe dan ukuran berkas, serta pencatatan audit. Asisten berbasis LangChain atau OpenAI API untuk OCR dokumen masih pada tahap rencana dan **belum diimplementasikan** di kode ini.

---

## 🛠️ Tech Stack

| Layer | Teknologi | Fungsi |
| :--- | :--- | :--- |
| Bahasa | `Python 3.13` / `3.14` | Logika *backend* utama; kedua versi diuji di CI |
| Rerangka | `Django 5.2` | MVT, ORM, autentikasi, admin |
| Basis data | `MariaDB 10.4` (XAMPP) atau keluarga MySQL | Penyimpanan data relasional warga, pengajuan, dan dokumen |
| Penghubung basis data | `PyMySQL` | Driver Django ORM ke MySQL/MariaDB |
| Peladen (Windows) | `waitress` | Proses WSGI pada port 8099, berada di belakang Apache |
| Peladen (Linux) | `gunicorn` | Proses WSGI untuk lingkungan non-Windows |
| Aset statis | `WhiteNoise` + Alias Apache | Melayani `/static/` pada semua jalur, termasuk `runserver` |
| Antarmuka | `HTML5`, `CSS3`, `JavaScript` | Tampilan tanpa *framework* JavaScript |
| Gaya | `static/css/style.css`, `admin.css` | Sistem gaya kustom SIPPER (proyek ini **tidak** memakai Bootstrap) |
| Utilitas | `qrcode`, `Pillow`, `reportlab` | Pembuatan gambar QR Code dan kartu PDF |
| Keamanan (opsional) | `clamd` | Pemeriksaan antivirus ClamAV untuk berkas terunggah; dinonaktifkan di mesin pengembangan |

---

## 📂 Struktur Direktori Proyek

```text
SIPPER/
├── .github/workflows/ci.yml        # CI: cek cepat (SQLite) + paritas MariaDB
├── core/                           # Aplikasi Django utama (logika bisnis)
│   ├── models.py                   # ORM: Penduduk, Pengajuan, Dokumen, dll.
│   ├── views.py                    # Alur request-response dan hak akses
│   ├── urls.py                     # Rute tingkat aplikasi
│   ├── admin.py / admin_site.py    # Penampilan dan dasbor admin
│   ├── middleware.py               # Batas ukuran berkas dan penjaga lain
│   ├── emails.py                   # Notifikasi surel
│   ├── tests.py                    # 38 pengujian otomatis
│   └── management/commands/        # backup_db, promote_officer, send_test_email
│
├── sipper/                         # Konfigurasi proyek
│   ├── settings.py                 # Pengaturan inti dan koneksi basis data
│   ├── urls.py                     # Rute tingkat atas
│   ├── __init__.py                 # Shim kompatibilitas MariaDB 10.4
│   └── wsgi.py / asgi.py           # Penangan penerapan
│
├── templates/                      # Beranda HTML
│   ├── base.html                   # Tata letak dasar dan navigasi
│   ├── landing.html                # Halaman depan publik
│   ├── dashboard.html              # Dasbor warga atau petugas
│   ├── officer.html                # Antrean verifikasi petugas
│   ├── scan_card.html              # Pemindai QR
│   └── registration/               # Templat reset sandi
│
├── static/                         # CSS, JavaScript, dan aset merek
├── media/                          # Berkas unggahan dan QR terhasil (di-gitignore)
├── docs/                           # 📚 Dokumentasi teknis
│   ├── SIPPER_FULLSTACK_GUIDE.md   # Panduan arsitektur dan alur API
│   ├── SIPPER_FRONTEND_TEMPLATES.md# Spesifikasi templat antarmuka
│   ├── SIPPER_SETUP_DEPLOYMENT.md  # Panduan instalasi dan penerapan
│   ├── SIPPER_QUICK_REFERENCE.md   # Ringkasan perintah baris
│   └── ci-status.md                # Status dan riwayat hasil CI
├── apache/                         # Konfigurasi virtual host dan sertifikat lokal
├── tools/                          # Skrip bantu (penyelarasan sandi basis data)
│
├── .env.example                    # Templat konfigurasi lingkungan
├── manage.py                       # utilitas CLI Django
├── requirements.txt                # Dependensi Python
└── README.md                       # Dokumentasi utama repositori
```

---

## 🗄️ Skema Database Singkat (`sipper_db`)

Akun warga dan petugas memakai model bawaan Django (`auth.User`). Di atasnya sistem mengelola **7 tabel utama**, semuanya dibuat lewat Django Migration:

1. `UserRole` — pemetaan peran tambahan di luar *flag* `is_staff`.
2. `Penduduk` — profil detail perantau dan status domisili.
3. `Pengajuan` — alur status verifikasi (`Menunggu`, `Disetujui`, `Ditolak`).
4. `Dokumen` — jalur penyimpanan berkas pendukung (KTP/Surat Keterangan).
5. `KartuDigital` — token verifikasi unik dan jalur berkas QR Code.
6. `Pemutakhiran` — riwayat perubahan alamat atau status perantau.
7. `AuditLog` — jejak aktivitas petugas dan sistem.

> Rincian tipe data dan *constraint* skema tersedia pada [`docs/SIPPER_FULLSTACK_GUIDE.md`](docs/SIPPER_FULLSTACK_GUIDE.md).

---

## ⚡ Panduan Instalasi Lokal

### 1. Prasyarat Sistem

- Python `3.13` atau `3.14`.
- MariaDB atau MySQL yang aktif. Mesin pengembangan memakai **MariaDB bawaan XAMPP 10.4** pada port 3306. MySQL 8 belum didukung selama *shim* pada `sipper/__init__.py` masih menurunkan gerbang versi ke `(10, 4)`.
- Git terpasang.

### 2. Clone Repositori dan Lingkungan Virtual

```bash
# Repo privat — gunakan akun yang punya akses.
git clone https://github.com/Yafet-wenda/SIPPER.git
cd SIPPER

python -m venv .venv

# Windows (PowerShell atau CMD)
.venv\Scripts\activate
# macOS atau Linux
source .venv/bin/activate
```

### 3. Pasang Dependensi

```bash
pip install -r requirements.txt
```

### 4. Siapkan Basis Data dan Konfigurasi Lingkungan

Buat basis data `sipper_db` dan satu akun aplikasi berhak seperlunya (misalnya `sipper_app@localhost` dan `sipper_app@127.0.0.1`). Salin `.env.example` menjadi `.env` lalu sesuaikan; berkas `.env` tidak pernah di-*commit*.

```env
DB_ENGINE=mysql
DB_NAME=sipper_db
DB_USER=sipper_app
DB_PASSWORD=ganti-dengan-sandi-anda
DB_HOST=127.0.0.1
DB_PORT=3306
DJANGO_SECRET_KEY=ganti-dengan-nilai-acak-panjang
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost,http://127.0.0.1
DJANGO_SECURE_COOKIES=0
DJANGO_SECURE_SSL_REDIRECT=0
DJANGO_HSTS_SECONDS=0
DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

Tiga nilai terakhir (`DJANGO_SECURE_COOKIES`, `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_HSTS_SECONDS`) sengaja dimatikan untuk XAMPP lokal yang belum memakai TLS. Dengan begitu `http://` tetap hidup dan phpMyAdmin pada port 80 tetap terjangkau, meskipun sertifikat lokal yang ada masih *self-signed*.

### 5. Jalankan Migrasi dan Peladen Pengembangan

```bash
python manage.py makemigrations
python manage.py migrate

# Opsional: buat akun superuser
python manage.py createsuperuser

python manage.py runserver 127.0.0.1:8000
```

Buka peramban dan akses aplikasi melalui `http://127.0.0.1:8000/`.

---

## ✅ Pengujian dan CI

```bash
# Jalur cepat tanpa peladen basis data (mis. saat MariaDB berhenti)
DB_ENGINE=sqlite python manage.py test

# Atau terhadap MariaDB/MySQL yang sedang berjalan
python manage.py test
```

Sebanyak 38 pengujian itu menutup alur daftar dan masuk, pengajuan, unggah berkas (termasuk penolakan berkas melebihi 5 MB), peninjauan petugas, kartu dan QR, statistik, ekspor, dasbor admin, serta aturan hak aksesnya.

GitHub Actions menjalankan `.github/workflows/ci.yml` pada setiap *push* dan *pull request* ke `master`, dan dapat dipicu manual lewat `workflow_dispatch`. Ada tiga *job*:

| *Job* | Basis data | Cakupan |
| :--- | :--- | :--- |
| `cek-cepat` (Python 3.13) | SQLite | `check`, migrasi tertinggal, `collectstatic`, seluruh pengujian |
| `cek-cepat` (Python 3.14) | SQLite | sama, untuk memastikan tidak ada regresi versi Python |
| `paritas-mariadb` | MariaDB 10.11 | `check`, migrasi tertinggal, seluruh pengujian lewat PyMySQL |

*Job* `cek-cepat` juga memeriksa agar berkas `.env` tidak pernah terlacak oleh git. Riwayat hasil dan catatan peninjauannya tersedia di [`docs/ci-status.md`](docs/ci-status.md).

---

## 🚀 Arsitektur dan Status Implementasi

Implementasi aktif memakai satu aplikasi Django `core` dengan **MariaDB bawaan XAMPP (10.4)** pada port 3306. Django 5.2 resmi mensyaratkan MariaDB 10.5, sehingga `sipper/__init__.py` memuat *shim* kompatibilitas kecil: menurunkan gerbang versi minimum dan mematikan dukungan `INSERT ... RETURNING` yang belum tersedia di 10.4. Fitur yang sudah berjalan mencakup akun masyarakat dan petugas, pengajuan, unggah dokumen maksimal 5 MB, peninjauan dokumen, riwayat pemutakhiran, kartu QR, kartu PDF, statistik, ekspor CSV, reset sandi, pencadangan, dan pemindai QR.

Rangkaian lokal pada mesin pengembangan: peramban → **Apache (:80 dan :443)** → *reverse proxy* → **waitress (:8099)**. Aset `/static/` dilayani Alias Apache dengan *fallback* WhiteNoise sehingga tetap tampil baik pada `runserver` maupun waitress. Berkas `/media/` **tidak pernah** dilayani secara langsung: unggahan warga hanya dapat diunduh melalui `/dokumen/<pk>/file/` yang memeriksa status masuk dan kepemilikan, sambil menulis catatan audit.

### Menjalankan Lokal

```powershell
# Prasyarat: panel XAMPP -> Start pada Apache dan MySQL (MariaDB)
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Pencadangan data dibuat dengan `python manage.py backup_db`, dan tersedia `prod.bat` untuk menyalakan seluruh rangkaian secara berurutan (MariaDB, waitress, Apache). Kredensial koneksi pengembangan berada di `.env` (`DB_USER=sipper_app`, `DB_PASSWORD` baca dari berkas itu, host `127.0.0.1:3306`, basis data `sipper_db`) dan berkas tersebut tidak di-*commit*.

### URL Utama

| Rute | Kegunaan |
| :--- | :--- |
| `/` | Beranda publik |
| `/daftar/`, `/login/`, `/logout/` | Pembuatan akun dan masuk |
| `/dashboard/` | Dasbor warga atau petugas |
| `/pengajuan/`, `/pengajuan/<pk>/kirim-ulang/` | Pengajuan baru dan pengiriman ulang |
| `/pemutakhiran/`, `/histori/` | Ubah data dan riwayatnya |
| `/profil/`, `/password/`, `/lupa-password/` | Profil dan pengelolaan sandi |
| `/petugas/` | Antrean verifikasi (juga `?export=csv`) |
| `/petugas/pengajuan/<pk>/`, `/petugas/dokumen/<pk>/` | Detail pengajuan dan peninjauan berkas |
| `/petugas/statistik/` | Grafik statistik |
| `/kartu/`, `/kartu/<code>/`, `/kartu/<code>/download/` | Pencarian kartu, validasi publik, kartu PDF |
| `/scan-kartu/` | Pemindai QR |
| `/health/`, `/api/*` | Pemeriksaan status dan titik data antarhalaman |
| `/admin/` | Administrasi Django |

### Administrasi

Akun superuser memakai `/admin/` sebagai pusat kendali. Dasbor admin menampilkan statistik langsung yang diperbarui setiap 5 detik (`REFRESH_MS` pada `static/js/admin-dashboard.js`), pengajuan terbaru, aktivitas audit, dan jumlah dokumen yang menunggu peninjauan. Setiap model memiliki pencarian, filter, paginasi, dan aksi massal yang relevan.

Perintah pengelolaan peran:

```powershell
python manage.py promote_officer <username>
```

---

## 🔒 Batasan Sistem dan Disclaimer

1. **Batasan akademis**: SIPPER dikembangkan khusus untuk memenuhi tugas proyek mata kuliah Workshop Pemrograman Framework, Politeknik Elektronika Negeri Surabaya (PENS).
2. **Bukan dokumen legal utama**: kartu digital SIPPER **bukan** pengganti KTP-el, Kartu Keluarga, maupun Surat Keterangan Pindah Warga Negara Indonesia (SKPWNI) resmi terbitan Dukcapil.
3. **Integrasi data**: sistem ini tidak terhubung langsung ke basis data nasional Dukcapil. Data yang diproses adalah data yang diunggah warga sendiri, sehingga repositori ini sengaja dipertahankan **privat** dan berkas unggahan tidak pernah dilayani sebagai berkas publik.

---

## 👥 Tim Penyusun

- **Yafet Wenda** (NRP: `3125521058`)
- **Muhammad Ai Nur Haaq** (NRP: `3125521052`)

**Dosen pengampu:** Evianita Dewi Fajrianti, S.Tr.T., M.Tr.T

---

<p align="center">
  <sub>Dibangun dengan Python dan Django untuk inovasi e-government.</sub>
</p>
