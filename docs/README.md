# 📚 Dokumentasi SIPPER

Selamat datang di folder dokumentasi **SIPPER** (*Sistem Informasi Penduduk Perantauan*).
Halaman ini menjadi indeks: memberi urutan baca yang tepat, menyatakan dokumen mana
yang masih bisa dipercaya, dan mencatat klaim yang tidak lagi sesuai dengan kode.

Untuk gambaran umum proyek — ringkasan, fitur, skema basis data, panduan instalasi, dan
status CI — cukup baca [`README.md`](../README.md) di akar repositori. Berkas itu adalah
dokumen paling mutakhir. Folder ini berisi uraian yang lebih panjang.

---

## 🧭 Urutan baca yang disarankan

| Tahap | Dokumen | Perkiraan waktu |
| :--- | :--- | :--- |
| 1. Kenali proyeknya | [`README.md`](../README.md) | 10 menit |
| 2. Jalankan di mesin sendiri | [`SIPPER_SETUP_DEPLOYMENT.md`](SIPPER_SETUP_DEPLOYMENT.md) | 30–45 menit |
| 3. Pahami alur kerja harian | [`SIPPER_QUICK_REFERENCE.md`](SIPPER_QUICK_REFERENCE.md) | 10 menit |
| 4. Dalami rancangan teknis | [`SIPPER_FULLSTACK_GUIDE.md`](SIPPER_FULLSTACK_GUIDE.md) | 1–2 jam |
| 5. Kerjakan tampilan | [`SIPPER_FRONTEND_TEMPLATES.md`](SIPPER_FRONTEND_TEMPLATES.md) | 1 jam |
| 6. Dalami pipeline OCR | [`laporan-implementasi-ocr.md`](laporan-implementasi-ocr.md) | 45 menit |
| Kapan saja | [`ci-status.md`](ci-status.md) | 5 menit |

---

## 🗂️ Isi folder

| Berkas | Isi | Status |
| :--- | :--- | :--- |
| `README.md` | Halaman yang sedang dibaca ini — indeks dokumentasi dan daftar selisih dengan kode. | **Aktual** (16 Oktober 2026) |
| `SIPPER_SETUP_DEPLOYMENT.md` | Langkah pemasangan lingkungan, konfigurasi basis data, migrasi, pengujian, sampai *deploy*. Paruh pertama sudah disesuaikan dengan kondisi *workspace* sekarang. | **Sebagian aktual** — lihat catatan di bawah |
| `SIPPER_QUICK_REFERENCE.md` | Kumpulan perintah singkat untuk Django, *git*, dan MySQL/MariaDB, serta peta struktur berkas dan palet warna. | **Aktual untuk rute, versi, dan peta berkas** (dibaca ulang 23 Oktober 2026); palet warna dan tautan sumber umum masih warisan rancangan lama |
| `SIPPER_FULLSTACK_GUIDE.md` | Rancangan *fullstack* paling lengkap: arsitektur, model, *view*, *form*, API, keamanan, dan tema UI. Panjangnya 2.445 baris. | **Rujukan historis** — menguraikan rencana multi-*app*, bukan implementasi yang berjalan |
| `SIPPER_FRONTEND_TEMPLATES.md` | Contoh kerangka HTML dan komponen JavaScript beserta palet warna. | **Rujukan historis** — nama *template* di dalamnya memakai struktur lama |
| `ci-status.md` | Apa yang dijalankan GitHub Actions, hasil yang sudah diverifikasi, temuan *review*, dan cara membaca hasil CI dari mesin pengembangan. | **Aktual untuk penjelasannya**; tabel per-*run*-nya berhenti di #10 (*run* #11–#22 baru dirangkum di halaman ini) |
| `laporan-implementasi-ocr.md` (+ `.docx`, `.pdf`) | Laporan implementasi OCR: pipeline Tesseract, parser format KTP, pra-proses, pemrosesan di latar, dan catatan keamanan. Versi `.docx` dan `.pdf` dihasilkan dari berkas `.md`. | **Sebagian aktual** — terbit 7 Oktober 2026 (v1.0), jadi belum memuat skor kecocokan NIK/nama dan panel tinjauan `ai_ocr` yang baru selesai 16 Oktober; keduanya dijelaskan di `README.md` akar. Bagian *Background Processing* dan *Rate Limiting* sudah dikoreksi 23 Oktober 2026 terhadap `core/ocr_worker.py` dan `core/throttle.py`; **`.docx`/`.pdf` belum dihasilkan ulang** dari berkas `.md` yang baru itu, jadi keduanya masih memuat teks lama. |
| `create-docx.js` dan `convert-to-pdf.ps1` | Penghasil `.docx` (paket npm `docx`) dan pengonversi `.docx` → `.pdf` (Word lewat COM) untuk laporan di atas. Jalur ini yang dipakai karena mesin tidak punya pandoc/LibreOffice. | **Aktual** — alat bantu, bukan dokumentasi |

Panduan *fullstack* dan referensi singkat masih menuliskan **Last Updated: 2024**, dan
tidak ditulis ulang ketika implementasi berpindah dari rencana multi-*app* ke satu
aplikasi `core`. Sebagian besar isinya masih berguna sebagai penjelasan mengapa sesuatu
dirancang begitu, tetapi jangan salin perintah atau nilai konfigurasinya mentah-mentah.
`SIPPER_FULLSTACK_GUIDE.md`, `SIPPER_FRONTEND_TEMPLATES.md`, dan
`SIPPER_SETUP_DEPLOYMENT.md` membuka dirinya dengan catatan status *workspace* sehingga
batasnya jelas; `SIPPER_QUICK_REFERENCE.md` sejak 23 Oktober 2026 juga punya catatan
semacam itu, dan tabel versi, peta berkas, serta daftar rutenya sudah dibaca ulang
terhadap kode (rute diambil dari `core/urls.py`).

---

## ✅ Fakta terkini — diverifikasi 23 Oktober 2026

Angka dan nama berikut dibaca langsung dari kode, bukan dari dokumen.

| Aspek | Nilai sebenarnya | Sumber |
| :--- | :--- | :--- |
| Bahasa pemrograman | Python 3.12.3 pada `.venv` lokal; CI menguji 3.13 dan 3.14 | `python --version` di dalam *venv*, `.github/workflows/ci.yml` |
| Rerangka web | Django 5.2.18 | `requirements.txt` (`Django>=5.2,<6.0`) |
| Basis data | MariaDB 10.4 bawaan XAMPP, *port* 3306 | `sipper/__init__.py` (gerbang versi diturunkan lewat *shim*) |
| Arsitektur aplikasi | dua aplikasi milik proyek: `core` (seluruh logika bisnis) dan `ai_ocr` (panel tinjauan hasil OCR, tanpa tabel sendiri) | `sipper/settings.py` (`INSTALLED_APPS`) |
| Model | 7 model tabel nyata: `Penduduk`, `Pengajuan`, `KartuDigital`, `Dokumen`, `AuditLog`, `Pemutakhiran`, `UserRole`; ditambah 1 *proxy model* `TinjauanOcr` di `ai_ocr` yang membaca baris `core_dokumen` yang sama | `core/models.py`, `ai_ocr/models.py` |
| Pengujian | 170 pengujian, seluruhnya lulus | `python manage.py test` di atas MariaDB (111 di `core/tests.py`, 14 di `core/tests_pdf.py`, 8 di `core/tests_llm.py`, 37 di `ai_ocr/tests.py`) |
| Baca OPTIK | Tesseract OCR 5.4 (berkas *binary* di luar repositori) melalui `pytesseract`, dengan pra-proses OpenCV; tiap panggilan dibatasi `BATAS_WAKTU_OCR = 60` detik sehingga berkas rusak berhenti sebagai hasil kosong, bukan menggantung | `core/ocr_processor.py`, `requirements.txt` (`pytesseract`, `opencv-python-headless`, `numpy`) |
| Prapemilahan AI | Skor kecocokan teks OCR KTP vs isian formulir: NIK 45%, nama 30%, keterbacaan 25%; di atas 85% berlabel *Valid*, sisanya *Perlu review manual*. Mesin hanya menulis kolom `ai_*`, tidak pernah `Dokumen.status` | `core/ai_verifikasi.py`, `ai_ocr/admin.py` |
| CI | 3 *job* — `cek-cepat` pada Python 3.13 dan 3.14 (SQLite) serta `paritas-mariadb` (MariaDB 10.11) | `.github/workflows/ci.yml` |
| Gaya | CSS tulisan sendiri: `static/css/style.css` dan `static/css/admin.css` | `static/`, `templates/base.html` |
| Huruf | Google Fonts — DM Sans dan Space Grotesk | `templates/base.html` |
| JavaScript | `static/js/admin-dashboard.js`, `static/js/file-label.js`, dan `static/js/html5-qrcode.min.js` | `static/js/` |
| Selang penyegaran dasbor petugas | 5 detik (`REFRESH_MS = 5000`) | `static/js/admin-dashboard.js:13` |
| Batas unggah | 5 MB *per berkas*, dua slot wajib (KTP dan KK); jenis dibatasi PDF, JPEG, PNG, ditambah batas 40 juta piksel dan pemeriksaan *magic byte*. Gerbang *middleware* mengikuti jumlah slot (2 × 5 MB + 3 MB) | `core/uploads.py` (`MAX_UPLOAD_BYTES`, `MAX_IMAGE_PIXELS`, `valid_upload`) dan `core/middleware.py` (`HARD_LIMIT_BYTES`) |
| Mode galat | Bawaan `DJANGO_DEBUG` adalah **0** (fail-closed). `dev.bat` menyetel 1 di lingkungan prosesnya, `prod.bat` menyetel 0 | `sipper/settings.py:11`, `dev.bat`, `prod.bat` |
| Scoping dasbor | Daftar pengajuan di `/dashboard/` disaring dengan `is_officer`, bukan `is_staff`: petugas yang diangkat lewat `promote_officer` hanya punya `UserRole`, tidak punya `is_staff` | `core/views.py:67` (`dashboard`), `core/akses.py`, uji `test_dashboard_scope_follows_petugas_role_not_is_staff` |
| Modul terpisah dari `views.py` | `akses.py` (penentu peran), `throttle.py` (pembatas + IP proxy), `uploads.py` (gerbang unggah), `ocr_worker.py` (thread OCR), `kartu_pdf.py` (gambar kartu), `csv_utils.py` (pelindung ekspor), `keputusan.py` (transisi status) | `core/` |
| Kunci rahasia | `DJANGO_SECRET_KEY` wajib diisi saat `DJANGO_DEBUG=0`; *server* gagal saat *start* daripada berjalan dengan kunci bawaan yang terlihat di repositori | `sipper/settings.py` |
| Isian formulir | Atribut `autocomplete` (`username`, `current-password`, `new-password`, `name`, `email`, `tel`) dipasang pada formulir masuk, daftar, ganti sandi, dan reset sandi lewat `core/forms.py`, supaya pengelola sandi dapat mengisi otomatis | `core/forms.py`, `templates/login.html`, `templates/register_v2.html` |
| Teks antarmuka | Tidak ada nama atau surel pengembang yang tertinggal di *placeholder*, contoh pengisian, atau teks bantuan; `test_ui_tidak_mencantumkan_data_pribadi_penyusun` memindai seluruh `templates/*.html` dan menolak regenerasi | `core/tests.py`, `templates/` |
| Navigasi layar kecil | *Breakpoint* 900 px memindahkan tautan petugas ke baris kedua yang bisa digeser (bukan `display: none`), dengan garis gulir tipis di tabel lebar | `static/css/style.css` |
| Visibilitas repositori | publik — yang dibuka untuk umum hanya sumber dan dokumentasinya; data warga (`media/`), rahasia (`.env`), dan basis data dikecualikan lewat `.gitignore` | pengaturan repositori GitHub |
| TLS | Aktif di mesin pengembangan: Apache melayani `:443` dengan sertifikat *self-signed* bawaan XAMPP, `http://` dibalas 301, *cookie* sesi/CSRF ber-flag `Secure`, dan HSTS dikirim (`DJANGO_HSTS_SECONDS=300`, sengaja pendek agar mudah ditarik kembali). `manage.py check --deploy` bersih. | `.env`, `apache/sipper-httpd.conf`, `sipper/settings.py:69-92` |
| Penanda HTTPS di belakang proxy | `SECURE_PROXY_SSL_HEADER` hanya aman bila Apache benar-benar mengirim `X-Forwarded-Proto`; itu disetel dengan `RequestHeader set X-Forwarded-Proto "https" "expr=%{HTTPS} == 'on'"` sehingga permintaan `:80` tidak ikut diberi penanda. | `apache/sipper-httpd.conf`, `sipper/settings.py:77` |
| Pengecualian test runner | `manage.py test` melonggarkan `SECURE_SSL_REDIRECT`, *cookie secure*, dan HSTS; tanpa itu setiap permintaan test client (HTTP polos) pulang 301 dan seluruh suite merah. Pengecualian terikat pada argumen `test`, jadi `runserver`/waitress tetap ketat. | `sipper/settings.py:80-92` |
| Status kedaluwarsa kartu | Kartu `aktif` yang `berlaku_sampai`-nya lewat ditandai `expired` di basis data — atomik lewat `KartuDigital.lewat_tempo().update(...)` saat halaman validasi dibuka, dan sapuan harian `refresh_card_status` untuk kartu yang tidak pernah dibuka. Status `expired` tidak pernah dihidupkan otomatis. | `core/models.py:84-86`, `core/views.py:502`, `core/management/commands/refresh_card_status.py` |
| Pekerjaan harian | Dua *Scheduled Task* Windows setelah `register-backup-task.bat`: "SIPPER backup harian" 06:30 (`backup.bat`) dan "SIPPER penutupan kartu" 06:35 (`maintenance-daily.bat`) | `register-backup-task.bat`, `backup.bat`, `maintenance-daily.bat` |

---

## ⚠️ Klaim yang sudah usang di dokumen lama

Daftar ini adalah hasil pemeriksaan menyeluruh, bukan dugaan. Setiap butir menunjuk
baris tertentu supaya mudah diverifikasi ulang sebelum dokumennya disunting.

| Klaim pada dokumen | Kenyataan di kode | Lokasi klaim |
| :--- | :--- | :--- |
| Django 4.2 | Django 5.2.18 | `SIPPER_FULLSTACK_GUIDE.md:10,61` — baris tumpukan sudah diberi label "rancangan lama" (dikoreksi 24 Okt 2026) |
| MySQL 8.0 | MariaDB 10.4 (XAMPP). *Shim* menolak MySQL 8, jadi klaim ini justru menyesatkan saat pemasangan. | `SIPPER_FULLSTACK_GUIDE.md:10` — sudah berlabel "rancangan lama" (24 Okt 2026); tabel QUICK_REFERENCE sudah memakai MariaDB |
| Bootstrap 5 | Tidak ada Bootstrap sama sekali di `templates/` dan `static/`; gaya memakai CSS tulisan sendiri. | Setiap penyebutan di FULLSTACK/FRONTEND/QUICK_REFERENCE kini berlabel "historis/rancangan lama" (24 Okt 2026) |
| `static/js/main.js` | Berkasnya tidak ada, dan tidak satu pun *template* memuatnya. | `SIPPER_FRONTEND_TEMPLATES.md:640`; `SIPPER_FULLSTACK_GUIDE.md:459,1757` (peta berkas QUICK_REFERENCE sudah diperbaiki) |
| LangChain 0.0.300 dan OpenAI 0.27.8 untuk prapemeriksaan pintar | Kedua paket tidak ada di `requirements.txt`. Yang berjalan sekarang adalah aturan validasi NIK serta pemeriksaan ukuran dan jenis berkas. | `SIPPER_FULLSTACK_GUIDE.md:70-71,669,2306`; `SIPPER_SETUP_DEPLOYMENT.md:160` |
| Multi-*app*: `users`, `perantau`, `verifikasi`, `kartu` | Dua aplikasi: `core` memegang seluruh rute dan model, `ai_ocr` hanya menambah panel tinjauan OCR di admin. Tidak ada satu pun dari empat nama *app* lama itu. | `SIPPER_FULLSTACK_GUIDE.md:88`; `SIPPER_FRONTEND_TEMPLATES.md:12` |
| Python 3.10 sebagai prasyarat minimum | Benar untuk Django 5.2, tetapi CI menguji 3.13 dan 3.14 sementara pengembangan lokal memakai 3.12.3. | `SIPPER_FULLSTACK_GUIDE.md:10,33` |
| Rute `/api/status/` dan `/api/perantau/status/` | `api_status` dihapus: tidak satu pun templat memanggilnya dan isinya (status pengajuan milik diri sendiri) sudah tersedia di dasbor. | `core/urls.py` |

Rekam jejak CI berada di `ci-status.md`. Sampai 24 Oktober 2026 repositori punya 32
*run* workflow `CI`: 29 berkesimpulan **success** dan 3 (`#7`, `#8`, `#16`) `cancelled`
karena gerbang `concurrency` dengan `cancel-in-progress: true` membatalkan run lama dari
*push* yang sama sebelum ada langkah yang selesai. Tidak ada satu pun *run* yang
*failure*. Tabel per-*run* di `ci-status.md` masih berhenti di #10; baris sisanya belum
dicatat satu per satu, hanya kesimpulannya yang dibaca ulang lewat API GitHub.

---

## ✍️ Konvensi menulis dokumentasi di sini

- Bahasa Indonesia semi-formal, mengikuti EYD Edisi V. Istilah teknis (*deploy*,
  *commit*, *template*, *job*) dibiarkan dalam bahasa Inggris dan dicetak miring.
- Kode, nama berkas, path, dan perintah tetap bahasa Inggris apa adanya.
- Setiap klaim tentang versi, jumlah pengujian, atau nama berkas wajib disertai sumber
  yang bisa diperiksa. Kalau angka berubah, dokumennya ikut diubah di *commit* yang sama.
- Dokumen yang mendahului implementasi diberi label **rujukan historis** di tabel isi
  folder, bukan dibiarkan tampak sebagai panduan terkini.

---

## 🔄 Cara memperbarui

1. Verifikasi faktanya dari kode lebih dulu — jangan menyalin dari dokumen lain.
2. Sunting dokumen terkait, lalu perbarui tabel di halaman ini kalau ada klaim yang
   berpindah status.
3. Jalankan `python manage.py test` (atau `DB_ENGINE=sqlite python manage.py test` saat
   MariaDB mati) kalau perubahan menyentuh contoh kode yang benar-benar dijalankan.
4. Perbarui `README.md` di akar repositori bila fakta yang berubah cukup penting bagi
   pembaca pertama.

Dua pekerjaan yang sudah diusulkan dan belum dikerjakan: menyunting ulang
`SIPPER_FULLSTACK_GUIDE.md` dan `SIPPER_FRONTEND_TEMPLATES.md` supaya sesuai
implementasi berjalan, serta menghapus topik `bootstrap` pada halaman GitHub repositori
karena tidak lagi menggambarkan proyek.
