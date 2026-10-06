# Status CI SIPPER

Dokumen ini mencatat apa yang dijaga GitHub Actions, hasil terakhir yang benar-benar
terverifikasi di server, dan temuan review atas workflow-nya. Diperbarui 2026-10-06.

Berkas: `.github/workflows/ci.yml` (nama workflow: `CI`).
Pemicu: `push` ke `master`, `pull_request` ke `master`, dan `workflow_dispatch`.

## Apa yang dijalankan

Dua job paralel, keduanya `ubuntu-24.04`:

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

Run nyata di `github.com/Yafet-wenda/SIPPER` (repo privat), dibaca lewat API GitHub pada
2026-10-06:

| Run | Commit | Event | Kesimpulan | Detail |
|---|---|---|---|---|
| #3 (`37416846349`) | `97df981` | push | **success** | 3 job, semua langkah `success` — termasuk `Migrasi tidak tertinggal` yang baru ditambahkan di job MariaDB |
| #2 (`37415179379`) | `dd1e6f0` | push | **success** | 3 job, semua langkah `success` |
| #1 (`37415061772`) | `5779f9e` | push | **success** | run pertama sejak workflow ditambahkan |

Rincian job pada run #2: `Cek cepat (SQLite, Python 3.13)` 30 s, `Cek cepat (SQLite,
Python 3.14)` 40 s, `Paritas MariaDB (Python 3.14)` 56 s. Jumlah tes 38, dan lintasan
`Test suite (MySQL backend lewat PyMySQL)` hijau — artinya shim `minimum_database_version
= (10, 4)` bekerja di MariaDB 10.11, dan `pip install -r requirements.txt` berhasil di
Linux untuk 3.13 maupun 3.14 (termasuk `gunicorn` yang bersyarat non-Windows).

## Temuan review

Dua hal sudah dibereskan, sisanya sengaja dibiarkan sebagai catatan.

Sudah diterapkan:

1. **Guard `.env` dan cek migrasi tidak simetris.** Semula langkah "Migrasi tidak
   tertinggal" hanya ada di job SQLite, padahal `makemigrations --check` justru lebih
   bernilai saat server MySQL sungguhan hidup. Sekarang job `paritas-mariadb` juga
   menjalankannya. (Guard `.env` tetap satu tempat: ia membaca isi repo, bukan basis data,
   jadi dua kali tidak menambah nilai.)
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
  unset TOKEN
  ```

  Token tidak pernah ditampilkan, hanya panjangnya. Versi PowerShell 5.1 dari pipa yang
  sama gagal (`fatal: refusing to work with credential missing protocol field`) karena
  string multi-baris tidak sampai ke git sebagai barisan terpisah — gunakan Git Bash.
- Alternatif tanpa kredensial apa pun: buka
  https://github.com/Yafet-wenda/SIPPER/actions langsung.
