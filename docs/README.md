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
| Kapan saja | [`ci-status.md`](ci-status.md) | 5 menit |

---

## 🗂️ Isi folder

| Berkas | Isi | Status |
| :--- | :--- | :--- |
| `README.md` | Halaman yang sedang dibaca ini — indeks dokumentasi dan daftar selisih dengan kode. | **Aktual** (6 Oktober 2026) |
| `SIPPER_SETUP_DEPLOYMENT.md` | Langkah pemasangan lingkungan, konfigurasi basis data, migrasi, pengujian, sampai *deploy*. Paruh pertama sudah disesuaikan dengan kondisi *workspace* sekarang. | **Sebagian aktual** — lihat catatan di bawah |
| `SIPPER_QUICK_REFERENCE.md` | Kumpulan perintah singkat untuk Django, *git*, dan MySQL/MariaDB, serta peta struktur berkas dan palet warna. | **Sebagian usang** — tabel versinya lama |
| `SIPPER_FULLSTACK_GUIDE.md` | Rancangan *fullstack* paling lengkap: arsitektur, model, *view*, *form*, API, keamanan, dan tema UI. Panjangnya 2.445 baris. | **Rujukan historis** — menguraikan rencana multi-*app*, bukan implementasi yang berjalan |
| `SIPPER_FRONTEND_TEMPLATES.md` | Contoh kerangka HTML dan komponen JavaScript beserta palet warna. | **Rujukan historis** — nama *template* di dalamnya memakai struktur lama |
| `ci-status.md` | Apa yang dijalankan GitHub Actions, hasil yang sudah diverifikasi, temuan *review*, dan cara membaca hasil CI dari mesin pengembangan. | **Aktual** (verifikasi manual terakhir sampai *run* #9, 6 Oktober 2026) |

Panduan *fullstack* dan referensi singkat masih menuliskan **Last Updated: 2024**, dan
tidak ditulis ulang ketika implementasi berpindah dari rencana multi-*app* ke satu
aplikasi `core`. Sebagian besar isinya masih berguna sebagai penjelasan mengapa sesuatu
dirancang begitu, tetapi jangan salin perintah atau nilai konfigurasinya mentah-mentah.
`SIPPER_FULLSTACK_GUIDE.md`, `SIPPER_FRONTEND_TEMPLATES.md`, dan
`SIPPER_SETUP_DEPLOYMENT.md` membuka dirinya dengan catatan status *workspace* sehingga
batasnya jelas; `SIPPER_QUICK_REFERENCE.md` belum punya catatan semacam itu, dan justru
tabel versinya di baris 246–248 yang paling perlu dikoreksi.

---

## ✅ Fakta terkini — diverifikasi 6 Oktober 2026

Angka dan nama berikut dibaca langsung dari kode, bukan dari dokumen.

| Aspek | Nilai sebenarnya | Sumber |
| :--- | :--- | :--- |
| Bahasa pemrograman | Python 3.14.6 pada `.venv` | `py --version` di dalam *venv* |
| Rerangka web | Django 5.2.17 | `requirements.txt` (`Django>=5.2,<6.0`) |
| Basis data | MariaDB 10.4 bawaan XAMPP, *port* 3306 | `sipper/__init__.py` (gerbang versi diturunkan lewat *shim*) |
| Arsitektur aplikasi | satu aplikasi Django bernama `core` | `sipper/settings.py` (`INSTALLED_APPS`) |
| Model | 7 model: `Penduduk`, `Pengajuan`, `KartuDigital`, `Dokumen`, `AuditLog`, `Pemutakhiran`, `UserRole` | `core/models.py` |
| Pengujian | 38 pengujian, seluruhnya lulus | `DB_ENGINE=sqlite python manage.py test` |
| CI | 3 *job* — `cek-cepat` pada Python 3.13 dan 3.14 (SQLite) serta `paritas-mariadb` (MariaDB 10.11) | `.github/workflows/ci.yml` |
| Gaya | CSS tulisan sendiri: `static/css/style.css` dan `static/css/admin.css` | `static/`, `templates/base.html` |
| Huruf | Google Fonts — DM Sans dan Space Grotesk | `templates/base.html` |
| JavaScript | `static/js/admin-dashboard.js` dan `static/js/html5-qrcode.min.js` | `static/js/` |
| Selang penyegaran dasbor petugas | 5 detik (`REFRESH_MS = 5000`) | `static/js/admin-dashboard.js:13` |
| Batas unggah | 5 MB; jenis berkas dibatasi pada PDF, JPEG, dan PNG | `core/views.py:509` (`MAX_UPLOAD_BYTES`) |
| Visibilitas repositori | privat — proyek ini menyimpan data turunan KTP | pengaturan repositori GitHub |

---

## ⚠️ Klaim yang sudah usang di dokumen lama

Daftar ini adalah hasil pemeriksaan menyeluruh, bukan dugaan. Setiap butir menunjuk
baris tertentu supaya mudah diverifikasi ulang sebelum dokumennya disunting.

| Klaim pada dokumen | Kenyataan di kode | Lokasi klaim |
| :--- | :--- | :--- |
| Django 4.2 | Django 5.2.17 | `SIPPER_FULLSTACK_GUIDE.md:10,61`; `SIPPER_QUICK_REFERENCE.md:246,255` |
| MySQL 8.0 | MariaDB 10.4 (XAMPP). *Shim* menolak MySQL 8, jadi klaim ini justru menyesatkan saat pemasangan. | `SIPPER_FULLSTACK_GUIDE.md:10`; `SIPPER_QUICK_REFERENCE.md:247` |
| Bootstrap 5 | Tidak ada Bootstrap sama sekali di `templates/` dan `static/`; gaya memakai CSS tulisan sendiri. | `SIPPER_FULLSTACK_GUIDE.md:10,67,457,542,627,1697,1751`; `SIPPER_FRONTEND_TEMPLATES.md:756,975`; `SIPPER_QUICK_REFERENCE.md:248,261,410` |
| `static/js/main.js` | Berkasnya tidak ada, dan tidak satu pun *template* memuatnya. | `SIPPER_FRONTEND_TEMPLATES.md:640`; `SIPPER_FULLSTACK_GUIDE.md:459,1757`; `SIPPER_QUICK_REFERENCE.md:132` |
| LangChain 0.0.300 dan OpenAI 0.27.8 untuk prapemeriksaan pintar | Kedua paket tidak ada di `requirements.txt`. Yang berjalan sekarang adalah aturan validasi NIK serta pemeriksaan ukuran dan jenis berkas. | `SIPPER_FULLSTACK_GUIDE.md:70-71,669,2306`; `SIPPER_SETUP_DEPLOYMENT.md:160` |
| Multi-*app*: `users`, `perantau`, `verifikasi`, `kartu` | Satu aplikasi `core` dengan nama rute yang berbeda. | `SIPPER_FULLSTACK_GUIDE.md:88`; `SIPPER_FRONTEND_TEMPLATES.md:12` |
| Python 3.10 sebagai prasyarat minimum | Benar untuk Django 5.2, tetapi CI menguji 3.13 dan 3.14 sementara pengembangan memakai 3.14. | `SIPPER_FULLSTACK_GUIDE.md:10,33` |

Rekam jejak CI berada di `ci-status.md`. Tabelnya memuat delapan baris — *run* #1–#6 serta
#9 dan #10 — beserta urutan langkah dan durasi tiap *job*; kedelapan baris itu lulus pada tiga
*job*. *Run* #7 dan #8 tidak masuk tabel karena dibatalkan gerbang `concurrency` sebelum
ada langkah yang selesai, perilaku yang memang diharapkan, bukan kegagalan. Kalau ada
*run* baru yang diverifikasi, tabel itu yang lebih dulu diperbarui — halaman ini hanya
menyebut jumlah *job* dan kesimpulannya.

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
