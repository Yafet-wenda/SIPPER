@echo off
rem =====================================================================
rem  TUGAS HARIAN - menutup kartu digital yang masa berlakunya lewat.
rem
rem  Halaman /kartu/<kode>/ sudah menyimpan status kedaluwarsa saat ada yang
rem  memindai, tetapi kartu yang tidak pernah dibuka tetap tercatat "aktif" di
rem  basis data. Skrip ini dibereskan oleh tugas terjadwal
rem  "SIPPER penutupan kartu harian" (lihat register-backup-task.bat).
rem
rem  Pindah ke cadangan kering sebelum yakin: ganti baris terakhir menjadi
rem      .venv\Scripts\python.exe manage.py refresh_card_status --dry-run
rem =====================================================================
cd /D "%~dp0"
.venv\Scripts\python.exe manage.py refresh_card_status
if errorlevel 1 (
    echo PENUTUPAN KARTU GAGAL - periksa apakah MariaDB berjalan di 127.0.0.1:3306
    exit /b 1
)
