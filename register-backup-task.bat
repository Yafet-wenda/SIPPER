@echo off
rem =====================================================================
rem  Mendaftarkan tugas terjadwal "SIPPER backup harian" (jam 06:30).
rem  Jalankan sekali. Kalau Windows menolak, klik kanan > Run as
rem  administrator.
rem
rem  Menghapus lagi:
rem     schtasks /Delete /TN "SIPPER backup harian" /F
rem =====================================================================
schtasks /Query /TN "SIPPER backup harian" >NUL 2>&1
if %ERRORLEVEL%==0 (
    echo Tugas sudah terdaftar, diperbarui ...
    schtasks /Delete /TN "SIPPER backup harian" /F >NUL
)
schtasks /Create /TN "SIPPER backup harian" /TR "\"%~dp0backup.bat\"" /SC DAILY /ST 06:30 /F
if %ERRORLEVEL% neq 0 (
    echo Gagal mendaftarkan tugas. Coba jalankan file ini sebagai administrator.
    pause
    exit /b 1
)
schtasks /Query /TN "SIPPER backup harian" /FO LIST
echo.
echo Selesai. Backup harian berjalan otomatis pukul 06.30.
pause
