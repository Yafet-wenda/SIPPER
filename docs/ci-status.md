# Status CI SIPPER

Dokumen ini mencatat apa yang dijaga GitHub Actions, hasil terakhir yang benar-benar
terverifikasi di server, dan temuan review atas workflow-nya. Diperbarui 2026-10-06.

Berkas: `.github/workflows/ci.yml` (nama workflow: `CI`).
Pemicu: `push` ke `master`, `pull_request` ke `master`, dan `workflow_dispatch`.

## Apa yang dijalankan

Dua job paralel, keduanya `ubuntu-24.04`. Karena `cek-cepat` memakai matriks Python, satu
run tampil sebagai tiga job di Actions.

| Job | Basis data | Python | Langkah |
|---|---|---|---|
| `cek-cepat` | SQLite (in-memory) | 3.13 dan 3.14 (matriks) | checkout → setup-python (cache pip) → `pip install -r requirements.txt` → `mkdir -p tmp media staticfiles` → guard ".env tidak terlacak git" → `manage.py check` → `manage.py makemigrations --check --dry-run` → `manage.py collectstatic --noinput --clear` → `manage.py test` |
| `paritas-mariadb` | MariaDB 10.11 (service container + health-check) | 3.14 | checkout → setup-python → `pip install` → `mkdir -p tmp media` → `manage.py check` → `manage.py makemigrations --check --dry-run` → `manage.py test` (backend MySQL lewat PyMySQL) |

Alasan dua job: `cek-cepat` memberi umpan balik dalam ~40 detik tanpa menyalakan server,
`paritas-mariadb` menguji jalur yang sama dengan produksi (XAMPP MariaDB + PyMySQL + shim
versi di `sipper/__init__.py`).

Semua variabel yang dibaca `sipper/settings.py` disuplai dari blok `env:` workflow, karena
`.env` tidak ikut ter-commit. `DJANGO_DEBUG=1` dan `DJANGO_SECURE_SSL_REDIRECT=0` di CI
sengaja: dengan `DEBUG=0`, SSL redirect dan secure cookie membuat tes autentikasi
berbasis test client gagal, jadi CI tidak boleh memakai setelan keamanan berbentuk produksi.

## Hasil terverifikasi

Run nyata di `github.com/Yafet-wenda/SIPPER` (repo privat), dibaca lewat API GitHub.
Verifikasi manual terakhir dilakukan 2026-10-06 dan mencakup seluruh run sampai #10. Run
yang dipicu oleh commit dokumen ini sendiri tidak dicatat satu per satu — lencana CI di
`README.md` akar selalu menunjuk hasil terbaru. Seluruh run di tabel ini dipicu `push` ke
`master`.

| Run | Commit | Event | Kesimpulan | Detail |
|---|---|---|---|---|
| #10 (`37476231699`) | `540a9bd` | push | **success** | 3 job × 13 langkah, seluruhnya `success` |
| #9 (`37474714732`) | `815e404` | push | **success** | 3 job × 13 langkah, seluruhnya `success`; keluaran `Ran 38 tests` muncul dan langkah `Test suite` lulus pada ketiga job |
| #6 (`37472403329`) | `b0787d8` | push | **success** | 3 job × 13 langkah, seluruhnya `success`; log pengujian mencatat `Ran 38 tests` lalu `OK` pada ketiga job |
| #5 (`37420878060`) | `0a8c45c` | push | **success** | 3 job × 13 langkah, seluruhnya `success` |
| #4 (`37417058173`) | `ac47af1` | push | **success** | 3 job × 13 langkah, seluruhnya `success` |
| #3 (`37416846349`) | `97df981` | push | **success** | 3 job × 13 langkah — job MariaDB naik dari 12 menjadi 13 karena `Migrasi tidak tertinggal` untuk pertama kali dijalankan di sana |
| #2 (`37415179379`) | `dd1e6f0` | push | **success** | `cek-cepat` 13 langkah, `paritas-mariadb` 12 langkah (belum ada cek migrasi) |
| #1 (`37415061772`) | `5779f9e` | push | **success** | run pertama sejak workflow ditambahkan; komposisi langkahnya sama seperti #2 |

Nomor run di tabel ini melompat dari #6 ke #9. Run #7 (`37474712819`) dan #8
(`37474713460`) berstatus `cancelled`; keduanya memakai commit yang sama (`815e404`) dan
pemicu yang sama (`push`) seperti #9. Satu `push` tampak memicu tiga pengiriman event
dalam rentang satu detik (`run_started_at` 13:55:44, 13:55:45, dan 13:55:45 UTC — dua run
terakhir dimulai pada detik yang sama), lalu blok `concurrency` dengan
`cancel-in-progress: true` menyisakan hanya yang terbaru. Jadi, pembatalan itu perilaku
yang diharapkan dari `cancel-in-progress`, bukan kegagalan. Keduanya tetap tidak dicatat
sebagai hasil karena tidak ada satu pun langkah yang selesai.

Durasi job pada run #4–#6 serta #9 dan #10: `cek-cepat` 32–52 detik, `paritas-mariadb`
54–67 detik. Satu run penuh selesai dalam 59–83 detik, dihitung sejak event `push` sampai
langkah terakhir, jadi masih di bawah 1,5 menit.

Langkah yang dijalankan pada job `cek-cepat` (13 langkah, tetapi hanya 9 langkah bernama
yang dikutip di bawah — empat sisanya dibuat otomatis oleh runner: `Set up job`, dua
langkah `Post`, dan `Complete job`): Ambil kode → Pasang Python → Pasang dependensi →
Siapkan folder runtime → Pastikan berkas `.env` tidak ikut ter-commit → Django system
check → Migrasi tidak tertinggal → Kumpulkan aset static (WhiteNoise) → Test suite.
Job `paritas-mariadb` juga memiliki 13 langkah, tetapi isinya berbeda: job ini menambah
`Initialize containers` dan `Stop containers`, serta tidak memiliki langkah guard `.env`
maupun `collectstatic` karena aset static tidak dipakai di jalur itu.

Jumlah 38 pengujian terverifikasi ulang di log run #6 dan #9, pada ketiga job. Dua job
SQLite membuat basis data uji in-memory (`file:memorydb_default`), sedangkan job MariaDB
membuat `test_sipper_db` di server sungguhan. Langkah
`Test suite (MySQL backend lewat PyMySQL)`
hijau — artinya shim `minimum_database_version = (10, 4)` bekerja di MariaDB 10.11, dan
`pip install -r requirements.txt` berhasil di Linux untuk 3.13 maupun 3.14 (termasuk
`gunicorn` yang bersyarat non-Windows).

## Temuan review

Dua hal sudah dibereskan, sisanya sengaja dibiarkan sebagai catatan.

Sudah diterapkan:

1. **Guard `.env` dan cek migrasi tidak simetris.** Semula langkah "Migrasi tidak
   tertinggal" hanya ada di job SQLite, padahal `makemigrations --check` justru lebih
   bernilai saat server MySQL sungguhan hidup. Sekarang job `paritas-mariadb` juga
   menjalankannya. (Guard `.env` tetap satu tempat: langkah ini membaca isi repo, bukan
   basis data, jadi dua kali tidak menambah nilai.)
2. **Folder runtime tidak ada di fresh checkout.** `tmp/` dan `media/` ada di `.gitignore`,
   jadi runner tidak pernah punya keduanya; `MEDIA_ROOT` (tes unggah) dan
   `EMAIL_FILE_PATH=tmp/outbox` akan menunjuk path yang tidak ada. Langkah `mkdir -p`
   sudah ditambahkan di kedua job.

Catatan yang belum diterapkan (butuh keputusan, bukan bug):

1. **Belum ada lint/format gate.** Proyek ini belum punya konfigurasi ruff/flake8, jadi
   CI hanya menguji perilaku. Menambah `ruff check` akan memunculkan banyak temuan lama
   sekaligus; lebih baik diadopsi bertahap sebagai commit terpisah.
2. **Aksi pihak ketiga tidak dipin ke SHA.** `actions/checkout@v4` dan
   `setup-python@v5` mengikuti tag. Untuk repo privat kampus ini risiko dapat diterima;
   kalau repo nanti dibuka untuk umum, pin ke commit SHA adalah upgrade yang murah.
3. **CI tidak menguji MySQL 8.** Bukan kelalaian: shim di `sipper/__init__.py` memasang
   `minimum_database_version = (10, 4)` tanpa memandang engine, dan Django membandingkan
   tuple versi server terhadapnya — `8.0.x < 10.4` akan `NotSupportedError`. Jadi selama
   shim masih buta-engine, server CI harus MariaDB. Kalau produksi pernah pindah ke
   MySQL 8, jadikan properti itu kondisional terhadap `self.connection.mysql_is_mariadb`
   dulu, baru tambah job `mysql:8.0`.
4. **Versi Python dev di luar rentang resmi Django.** Mesin ini memakai 3.14.6 dengan
   Django 5.2.17; dukungan resmi 5.2 adalah 3.10–3.13. CI sengaja menguji keduanya supaya
   kita tahu kalau 3.14 jadi masalah.

## Cara membaca hasil CI dari mesin ini

Tiga jalur dicoba dan hanya satu yang bekerja (tercatat supaya tidak mengulang jalan buntu):

- Konektor MCP GitHub **tidak punya** tool untuk run hasil `push`; `get_check_runs` hanya
  bekerja lewat nomor PR. `WebFetch` ke halaman `/actions` → 404 (repo privat, tanpa login).
  Tool browser yang ada membuka sesi Chrome terpisah yang tidak ikut login GitHub.
- Yang bekerja: **Git Bash** + kredensial yang sudah tersimpan di Git Credential Manager,
  untuk panggilan read-only:

  ```bash
  TOKEN=$(printf 'protocol=https\nhost=github.com\n\n' \
            | git credential fill | sed -n 's/^password=//p')
  curl -s -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/Yafet-wenda/SIPPER/actions/runs?per_page=5"
  curl -s -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/Yafet-wenda/SIPPER/actions/runs/<run_id>/jobs"
  # Log pengujian sebuah job — perlu -L karena endpoint-nya mengirim redirect
  curl -sL -H "Authorization: Bearer $TOKEN" \
    "https://api.github.com/repos/Yafet-wenda/SIPPER/actions/jobs/<job_id>/logs"
  unset TOKEN
  ```

  Token tidak pernah ditampilkan, hanya panjangnya. Versi PowerShell 5.1 dari pipa yang
  sama gagal (`fatal: refusing to work with credential missing protocol field`) karena
  string multi-baris tidak sampai ke git sebagai barisan terpisah — gunakan Git Bash.
- Alternatif tanpa kredensial apa pun: buka
  https://github.com/Yafet-wenda/SIPPER/actions langsung.
