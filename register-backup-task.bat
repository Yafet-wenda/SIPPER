@echo off
rem =====================================================================
rem  Mendaftarkan dua tugas terjadwal SIPPER, keduanya pagi buta:
rem    06:30  "SIPPER backup harian"        -> backup.bat
rem    06:35  "SIPPER penutupan kartu"      -> maintenance-daily.bat
rem  Urutannya disengaja: cadangan diambil dulu, baru status kartu diubah,
rem  supaya dump terakhir selalu berisi keadaan sebelum perubahan harian.
rem
rem  Jalankan sekali. Kalau Windows menolak, klik kanan > Run as
rem  administrator.
rem
rem  Menghapus lagi:
rem     schtasks /Delete /TN "SIPPER backup harian" /F
rem     schtasks /Delete /TN "SIPPER penutupan kartu" /F
rem =====================================================================
call :daftarkan "SIPPER backup harian" 06:30 "%~dp0backup.bat"
if errorlevel 1 exit /b 1
call :daftarkan "SIPPER penutupan kartu" 06:35 "%~dp0maintenance-daily.bat"
if errorlevel 1 exit /b 1
echo.
echo Selesai. Keduanya berjalan otomatis setiap pagi, mulai pukul 06.30.
pause
rem Baris di bawah wajib: tanpa ini cmd lanjut jatuh ke badan :daftarkan
rem sesudah pause, dengan %1 kosong, dan skrip berakhir dengan dua galat sintaks.
exit /b 0

:daftarkan
rem %1 nama tugas, %2 jam, %3 berkas yang dijalankan.
schtasks /Query /TN %1 >NUL 2>&1
if %ERRORLEVEL%==0 (
    echo Tugas %~1 sudah terdaftar, diperbarui ...
    schtasks /Delete /TN %1 /F >NUL
)
schtasks /Create /TN %1 /TR "\"%~3\"" /SC DAILY /ST %2 /F
if errorlevel 1 (
    echo Gagal mendaftarkan tugas %~1. Coba jalankan file ini sebagai administrator.
    exit /b 1
)
schtasks /Query /TN %1 /FO LIST
exit /b 0
