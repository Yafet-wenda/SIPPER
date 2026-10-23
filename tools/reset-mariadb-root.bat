@echo off
setlocal
rem =====================================================================
rem  Reset kata sandi root MariaDB (XAMPP) - jalankan sendiri, klik kanan
rem  "Run as administrator" dicmd window biasa juga bisa selama port 3306
rem  bebas.
rem
rem  Kata sandi baru diketik langsung di prompt mysql, jadi tidak pernah
rem  tersimpan di file ini maupun di riwayat perintah.
rem
rem  Efek samping: MariaDB dihentikan 2 kali selama +/- 30 detik. Tutup
rem  dulu waitress / phpMyAdmin tab kalau sedang dipakai.
rem  User aplikasi (sipper_app) dan isinya TIDAK disentuh.
rem =====================================================================

rem  Lokasi XAMPP dideteksi otomatis (C:, D:, lalu F:) seperti pada prod.bat.
rem  Kalau berada di tempat lain, set lebih dulu:  set XAMPP_HOME=E:\xampp
if not defined XAMPP_HOME if exist "C:\xampp\mysql_start.bat" set "XAMPP_HOME=C:\xampp"
if not defined XAMPP_HOME if exist "D:\xampp\mysql_start.bat" set "XAMPP_HOME=D:\xampp"
if not defined XAMPP_HOME if exist "F:\xampp\mysql_start.bat" set "XAMPP_HOME=F:\xampp"
if not defined XAMPP_HOME set "XAMPP_HOME=C:\xampp"
echo        XAMPP: %XAMPP_HOME%

set "BINDIR=%XAMPP_HOME%\mysql\bin"
set "MYSQD=%BINDIR%\mysqld.exe"
set "MYSQL=%BINDIR%\mysql.exe"
set "INI=%BINDIR%\my.ini"

echo =====================================================
echo  RESET KATA SANDI ROOT  -  MariaDB XAMPP
echo =====================================================
echo.
echo MariaDB akan dihentikan sementara. Jangan tutup jendela ini
echo sampai langkah [4/4] selesai.
echo.
pause

echo.
echo [1/4] Menghentikan mysqld ...
taskkill /F /IM mysqld.exe >nul 2>&1
timeout /t 4 /nobreak >nul

echo [2/4] Menjalankan MariaDB tanpa pemeriksaan hak akses ...
echo        (jendela baru "MariaDB root reset" terbuka - biarkan saja)
start "MariaDB root reset" "%MYSQD%" --defaults-file="%INI%" --standalone --skip-grant-tables
timeout /t 8 /nobreak >nul

echo.
echo [3/4] Jendela mysql akan terbuka. Ketik baris berikut SATU PER SATU:
echo.
echo         FLUSH PRIVILEGES;
echo         ALTER USER 'root'@'localhost' IDENTIFIED BY 'sandi-baru';
echo         FLUSH PRIVILEGES;
echo.
echo   Ganti 'sandi-baru' dengan pilihan Anda sendiri.
echo   Setelah selesai ketik:  exit
echo.
pause
"%MYSQL%" -u root mysql
if errorlevel 1 goto :fail

echo.
echo [4/4] Memulai ulang MariaDB secara normal ...
taskkill /F /IM mysqld.exe >nul 2>&1
timeout /t 5 /nobreak >nul
start "MariaDB" "%XAMPP_HOME%\mysql_start.bat"
timeout /t 10 /nobreak >nul

echo.
echo Verifikasi. Masukkan kata sandi root yang barusan Anda buat.
echo Kalau muncul "Welcome to the MariaDB monitor" = berhasil.
echo.
"%MYSQL%" -u root -p
echo.
echo Selesai. Catatan penting:
echo   - Simpan kata sandi root baru di tempat aman (tidak ada yang menyimpannya untuk Anda).
echo   - .env SIPPER tidak perlu diubah: Django memakai user sipper_app, bukan root.
echo   - phpMyAdmin: cukup login dengan sipper_app.
goto :end

:fail
echo.
echo Gagal terhubung ke mysql. Kemungkinan mysqld belum siap.
echo Menutup mode tanpa hak akses dan memulai ulang secara normal ...
taskkill /F /IM mysqld.exe >nul 2>&1
timeout /t 5 /nobreak >nul
start "MariaDB" "%XAMPP_HOME%\mysql_start.bat"
echo.
echo MariaDB sudah kembali normal. Ulangi skrip ini kalau mau coba lagi.

:end
endlocal
