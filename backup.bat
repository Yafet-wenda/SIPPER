@echo off
rem =====================================================================
rem  BACKUP  -  ekspor seluruh data SIPPER ke JSON + retensi otomatis
rem
rem  Hasil: <folder proyek>\backups\sipper-TANGGAL-JAM.json  (folder ini tidak
rem  ikut ke git). Default menyimpan 14 file terakhir.
rem
rem  Kalau Anda punya drive atau folder lain untuk salinan, set variabel
rem  lingkungan SIPPER_BACKUP_MIRROR ke path itu, misalnya
rem     setx SIPPER_BACKUP_MIRROR "E:\cadangan-sipper"
rem  lalu skrip ini akan menyalin hasilnya ke sana juga.
rem =====================================================================
cd /D "%~dp0"
.venv\Scripts\python.exe manage.py backup_db --keep 14
if errorlevel 1 (
    echo BACKUP GAGAL - periksa apakah MariaDB berjalan di 127.0.0.1:3306
    exit /b 1
)

if "%SIPPER_BACKUP_MIRROR%"=="" goto :done
echo Menyalin ke cermin %SIPPER_BACKUP_MIRROR% ...
rem /E bukan /MIR: folder cermin tidak boleh dibersihkan, di sana bisa ada isi lain.
robocopy backups "%SIPPER_BACKUP_MIRROR%" /E /XO /NFL /NDL /NJH /NJS >NUL
if %ERRORLEVEL% GEQ 8 echo Penyalinan ke cermin gagal, cek path-nya.

:done
echo Backup selesai.
