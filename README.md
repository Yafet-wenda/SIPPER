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
| Rerangka | Django 5.2 dengan aplikasi utama `core` dan aplikasi penunjang `ai_ocr` (tinjauan hasil OCR) |
| Basis data | MariaDB 10.4 (bawaan XAMPP) melalui PyMySQL; SQLite tersedia sebagai jalur uji cepat |
| Pengujian | 164 pengujian otomatis terhadap MariaDB, seluruhnya lolos |
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
- **Unggah KTP dan Kartu Keluarga**: formulir pengajuan mewajibkan dua berkas terpisah, *Foto KTP* dan *Foto Kartu Keluarga*, masing-masing maksimal 5 MB dan tersimpan sebagai `Dokumen` berlabel jenis (`ktp`, `kk`). Pemeriksaan meliputi tipe berkas (`pdf`, `jpeg`, `png`) lewat magic byte, batas ukuran di *middleware* (total badan permintaan), jumlah piksel untuk menolak *decompression bomb*, dan validasi format NIK (tepat 16 digit angka) di sisi server. Endpoint `api/validate-nik/` tersedia untuk pemeriksaan format dari peramban; halaman form saat ini memvalidasi saat dikirim, jadi endpoint itu tidak dipanggil templat mana pun.
- **Kartu Digital dan QR Code**: kartu identitas perantau terbit setelah pengajuan disetujui, dilengkapi berkas QR dan unduhan PDF. QR dapat dipindai untuk validasi publik.
- **Pemutakhiran Data Mandiri**: pelaporan perubahan alamat tujuan, perpanjangan durasi tinggal, atau konfirmasi kembali ke daerah asal, lengkap dengan riwayat.

### 🏛️ Modul Pemerintah (Petugas)

- **Dasbor Monitoring**: visualisasi ringkas statistik perantau aktif, jumlah pengajuan masuk, dan grafik tujuan merantau.
- **Panel Verifikasi Berkas**: antrean petugas memberi empat aksi langsung per baris — **Setujui**, **Perlu perbaikan**, **Tolak**, dan **Kembalikan ke menunggu** — masing-masing disertai satu medan catatan. Keputusan yang merugikan warga (*Tolak* dan *Perlu perbaikan*) **wajib menyertakan catatan**; aturannya ditegakkan di sisi server (`STATUS_WAJIB_CATATAN` di `core/views.py`), sehingga permintaan tanpa alasan ditolak meski validasi peramban dilewati. Tanpa catatan, warga tidak tahu apa yang harus diperbaiki dan tombol kirim ulang berkas tidak terbuka untuknya. Daftar antrean menampilkan penanda kelengkapan KTP dan KK per warga serta catatan terakhir tiap baris, dan halaman detail menampilkan pratinjau gambar tiap berkas (PDF ditautkan, bukan ditanam) beserta status valid per dokumen.
- **Validasi Kode QR**: pemindaian QR lewat kamera (`html5-qrcode`) untuk memastikan keabsahan kartu digital warga di lokasi, dengan alternatif masukan kode manual bila kamera tidak tersedia. Halaman hasil pindas tetap publik dan menutup NIK penuh; bila yang memindai adalah petugas yang sudah masuk, halaman menampilkan tambahan tombol **Lihat data lengkap (petugas)** menuju detail pengajuan warga tersebut.
- **Laporan PDF Data Lengkap**: setiap pengajuan dapat dicetak sebagai laporan A4 (`/petugas/pengajuan/<pk>/laporan.pdf`) berisi isian pendaftaran, status verifikasi, berkas pendukung beserta hasil baca OCR, dan status kartu. Rutenya dikunci `is_officer`, berkasnya ber-`Cache-Control: no-store`, dan setiap unduhan tercatat di `AuditLog` sebagai `cetak_laporan`. Warga biasa maupun pengunjung anonim tidak bisa membuka berkas milik siapa pun.
- **Ekspor dan Audit**: ekspor CSV daftar pengajuan (`/petugas/?export=csv`) serta `AuditLog` untuk setiap aksi petugas.

### 🤖 Pra-verifikasi Otomatis

Pra-verifikasi yang berjalan saat ini **berbasis aturan di Django**: validasi struktur NIK, kelengkapan isian, tipe dan ukuran berkas, serta pencatatan audit. Di halaman detail petugas ada **Asisten Verifikasi Dokumen** dengan dua mesin: bila `GEMINI_API_KEY` diisi di `.env`, pertanyaan dijawab LLM cloud Google Gemini (percakapan dan ringkasan konteks pengajuan dikirim ke Google); tanpa kunci — atau setiap kali Gemini gagal — asisten otomatis jatuh ke mesin aturan lokal yang jalan sepenuhnya offline.

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
│   ├── forms.py                    # Form bawaan Django + atribut autocomplete sandi
│   ├── middleware.py               # Batas ukuran berkas dan penjaga lain
│   ├── akses.py                    # Satu sumber penentu "ini petugas atau bukan"
│   ├── throttle.py                 # Pembatas permintaan publik + IP di belakang proxy
│   ├── uploads.py                  # Aturan unggah: ukuran, ekstensi, magic byte, piksel
│   ├── keputusan.py                # Transisi status pengajuan + penerbitan kartu
│   ├── ocr_worker.py               # Thread OCR: antrean, batas konkurensi, audit
│   ├── ocr_processor.py            # Ekstraksi teks KTP/KK via Tesseract
│   ├── ktp_parser.py               # Pemetaan teks OCR menjadi isian KTP
│   ├── ai_verifikasi.py            # Rumus skor kecocokan OCR vs isian formulir
│   ├── kartu_pdf.py                # Gambar kartu ID-1 (reportlab)
│   ├── pdf_report.py               # Laporan A4 data lengkap
│   ├── csv_utils.py                # Pelindung formula injection saat ekspor CSV
│   ├── chatbot.py                  # Mesin aturan asisten verifikasi
│   ├── llm.py                      # Klien Gemini (opsional, via .env) + penyamaran data
│   ├── emails.py                   # Notifikasi surel
│   ├── context_processors.py       # Variabel template yang dipakai semua halaman
│   ├── tests.py                    # Pengujian alur utama
│   ├── tests_pdf.py                # Pengujian keluaran PDF
│   ├── tests_llm.py                # Test router LLM + fallback
│   └── management/commands/        # backup_db, clean_data, promote_officer, send_test_email
│
├── ai_ocr/                         # Aplikasi penunjang: panel tinjauan hasil OCR
│   ├── models.py                   # Proxy model TinjauanOcr atas core.Dokumen
│   ├── admin.py                    # Changelist + form review berfilter skor
│   └── tests.py                    # Pengujian rumus skor, parser, dan panel
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
3. `Pengajuan` — alur status verifikasi (`Menunggu`, `Disetujui`, `Ditolak`, `Perlu perbaikan`); dua status terakhir menuntut catatan dari petugas.
4. `Dokumen` — jalur penyimpanan berkas per warga, dengan kolom `jenis` (`ktp`, `kk`, `surat_tugas`, `lainnya`) dan status validitas per berkas.
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

# atau cukup dev.bat (menyetel DJANGO_DEBUG=1 lalu runserver)
python manage.py runserver 127.0.0.1:8000
```

Buka peramban dan akses aplikasi melalui `http://127.0.0.1:8000/`. Perlu diingat bawaan `DJANGO_DEBUG` sekarang 0, jadi `runserver` langsung tanpa `set "DJANGO_DEBUG=1"` berjalan dalam mode produksi (halaman galat ringkas, tanpa *traceback*).

---

## ✅ Pengujian dan CI

```bash
# Jalur utama: terhadap MariaDB/MySQL yang sedang berjalan
python manage.py test

# Fallback tanpa peladen basis data (mis. saat MariaDB berhenti atau user
# aplikasi belum diberi hak membuat test_sipper_db)
DB_ENGINE=sqlite python manage.py test
```

Sebanyak 164 pengujian menutup alur daftar dan masuk, pengajuan, unggah berkas (termasuk penolakan berkas melebihi 5 MB), peninjauan petugas — termasuk aturan tolak/perlu-perbaikan wajib catatan di antrean maupun halaman detail, dan kembali ke status menunggu — kartu dan QR, statistik, ekspor, dasbor admin (tema, live-stats khusus staf, badge status, filter waktu, dan aksi massal *Setujui* yang melewati jalur keputusan tunggal sehingga kartu terbit, email jalan, dan audit tercatat), asisten chat dua mesin (LLM Gemini dengan cadangan rule-based; seluruh jalur jaringannya di-mock sehingga suite tetap jalan offline), prapemilahan AI (rumus skor NIK 45% / nama 30% / keterbacaan 25% dan ambang 85% yang ketat, parser KTP, jalur OCR, serta panel tinjauan `ai_ocr` termasuk penolakan akses warga dan jaminan mesin tidak pernah mengubah status berkas), serta laporan PDF petugas — termasuk penolakan akses anonim dan akses warga biasa, isi berkas, jejak audit, dan penanganan karakter di luar WinAnsi.

GitHub Actions menjalankan `.github/workflows/ci.yml` pada setiap *push* dan *pull request* ke `master`, dan dapat dipicu manual lewat `workflow_dispatch`. Ada tiga *job*:

| *Job* | Basis data | Cakupan |
| :--- | :--- | :--- |
| `cek-cepat` (Python 3.13) | SQLite | `check`, migrasi tertinggal, `collectstatic`, seluruh pengujian |
| `cek-cepat` (Python 3.14) | SQLite | sama, untuk memastikan tidak ada regresi versi Python |
| `paritas-mariadb` | MariaDB 10.11 | `check`, migrasi tertinggal, seluruh pengujian lewat PyMySQL |

*Job* `cek-cepat` juga memeriksa agar berkas `.env` tidak pernah terlacak oleh git. Riwayat hasil dan catatan peninjauannya tersedia di [`docs/ci-status.md`](docs/ci-status.md).

---

## 🚀 Arsitektur dan Status Implementasi

Implementasi aktif memakai aplikasi Django `core` plus aplikasi penunjang `ai_ocr` (hanya proxy model dan tampilan admin, tanpa tabel baru) dengan **MariaDB bawaan XAMPP (10.4)** pada port 3306. Django 5.2 resmi mensyaratkan MariaDB 10.5, sehingga `sipper/__init__.py` memuat *shim* kompatibilitas kecil: menurunkan gerbang versi minimum dan mematikan dukungan `INSERT ... RETURNING` yang belum tersedia di 10.4. Fitur yang sudah berjalan mencakup akun masyarakat dan petugas, pengajuan, unggah dokumen maksimal 5 MB, prapemilahan berkas oleh mesin (OCR KTP lalu skor kecocokan terhadap isian formulir; hasil di bawah ambang 85% ditandai *Perlu review manual*, tanpa pernah mengubah status berkas), peninjauan dokumen, riwayat pemutakhiran, kartu QR, kartu PDF, statistik, ekspor CSV, reset sandi, pencadangan, dan pemindai QR.

Rangkaian lokal pada mesin pengembangan: peramban → **Apache (:80)** → *reverse proxy* → **waitress (:8099)**. TLS (:443) belum dipasang di rangkaian ini, karena itu *cookie aman* dan *HTTPS-redirect* sengaja dimatikan sampai sertifikat benar-benar serving. Aset `/static/` dilayani Alias Apache dengan *fallback* WhiteNoise sehingga tetap tampil baik pada `runserver` maupun waitress. Berkas `/media/` **tidak pernah** dilayani secara langsung: unggahan warga hanya dapat diunduh melalui `/dokumen/<pk>/file/` yang memeriksa status masuk dan kepemilikan, sambil menulis catatan audit.

### Menjalankan Lokal

```powershell
# Prasyarat: panel XAMPP -> Start pada Apache dan MySQL (MariaDB)
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
dev.bat    # runserver dengan DJANGO_DEBUG=1; lihat catatan di bawah
```

Bawaan `DJANGO_DEBUG` di `sipper/settings.py` adalah **0** (fail-closed): proses yang terlanjur dijalankan tanpa variabel lingkungan `DJANGO_DEBUG` tidak boleh menyajikan *traceback* SQL. Karena itu pengembangan memakai `dev.bat`, yang menyetel `DJANGO_DEBUG=1` di lingkungan prosesnya sebelum `runserver`. Kalau perlu menjalankan `manage.py runserver` langsung, set lebih dulu: `set "DJANGO_DEBUG=1"`.

Bentuk produksi perlu satu langkah tambahan per mesin, karena Apache harus tahu cara mem-*proxy* ke waitress:

```powershell
# sekali per mesin; butuh izin tulis ke <XAMPP>\apache\conf
powershell -ExecutionPolicy Bypass -File scripts\install-apache-config.ps1 -Restart
```

Skrip itu menyalakan `mod_proxy_http` (bawaan XAMPP dimuat tapi dikomentari), menyalin `apache/sipper-httpd.conf` menjadi `conf/extra/httpd-sipper.conf` dengan `__PROJECT_ROOT__` sudah diganti lokasi folder proyek, menambahkan baris `Include` ke `httpd.conf`, lalu membatalkan seluruh perubahannya sendiri kalau `httpd -t` menolak hasil susunan. Lokasi XAMPP dideteksi otomatis (`C:\`, `D:\`, `F:\`) atau lewat `-ApacheHome`.

Pencadangan data dibuat dengan `python manage.py backup_db`, dan tersedia `prod.bat` untuk menyalakan seluruh rangkaian secara berurutan (MariaDB, collectstatic, waitress, Apache). Skrip itu juga menyetel profil produksi di lingkungan prosesnya (`DJANGO_DEBUG=0`, host dan origin pada port 80, cookie aman dan HTTPS-redirect dimatikan selama Apache belum serving TLS), sehingga isi `.env` untuk dua hal itu tidak ikut terpakai. Nilai yang **tidak** disetel `prod.bat` — `DB_HOST`, `DJANGO_EMAIL_BACKEND`, `CLAMAV_*` — tetap dibaca dari `.env`. Kredensial koneksi pengembangan berada di `.env` (`DB_USER=sipper_app`, `DB_PASSWORD` baca dari berkas itu, host `127.0.0.1:3306`, basis data `sipper_db`) dan berkas tersebut tidak di-*commit*.

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
| `/petugas/pengajuan/<pk>/laporan.pdf` | Laporan PDF data lengkap (khusus petugas, tercatat di audit) |
| `/petugas/statistik/` | Grafik statistik |
| `/kartu/`, `/kartu/<code>/`, `/kartu/<code>/download/` | Pencarian kartu, validasi publik, kartu PDF |
| `/scan-kartu/` | Pemindai QR |
| `/health/`, `/api/*` | Pemeriksaan status dan titik data antarhalaman |
| `/admin/` | Administrasi Django |

### Administrasi

Akun superuser memakai `/admin/` sebagai pusat kendali. Dasbor admin menampilkan statistik langsung yang diperbarui setiap 5 detik (`REFRESH_MS` pada `static/js/admin-dashboard.js`), pengajuan terbaru, aktivitas audit, dan jumlah dokumen yang menunggu peninjauan. Setiap model memiliki pencarian, filter, paginasi, dan aksi massal yang relevan. Petugas biasa bekerja di `/petugas/`; peran mereka disimpan sebagai baris `UserRole` yang dibaca `core.akses.is_officer` (satu-satunya tempat pertanyaan "apakah akun ini petugas" dijawab), tanpa menyentuh tabel autentikasi.


Perintah pengelolaan:

```powershell
# angkat akun warga yang sudah ada menjadi petugas
python manage.py promote_officer <username>

# bersihkan data uji coba — lihat dulu, lalu jalankan dengan konfirmasi
python manage.py clean_data --admin <email-admin> --dry-run
python manage.py clean_data --admin <email-admin> --yes
```

`clean_data` menghapus baris, jadi dia menolak bekerja tanpa `--yes` dan tanpa
`--admin` yang benar-benar ada di database; superuser lain tidak pernah ikut
terhapus. Cadangan dibuat lebih dulu dengan `python manage.py backup_db`.

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
