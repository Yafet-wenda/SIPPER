@echo off
rem =====================================================================
rem  PROD-LOKAL  -  SIPPER bentuk produksi di mesin ini  ->  http://localhost
rem
rem  Urutan: MariaDB -> waitress (WSGI di 127.0.0.1:8099) -> Apache (:80 proxy)
rem  Static dilayani Apache lewat Alias /static/ ke <folder proyek>\staticfiles
rem  Media TIDAK pernah dibuka langsung, semuanya lewat view pemeriksa hak akses.
rem
rem  Lokasi XAMPP dideteksi otomatis (C:, D:, lalu F:). Kalau berada di tempat
rem  lain, set lebih dulu:  set XAMPP_HOME=E:\xampp
rem
rem  Kalau ada file static yang berubah, jalankan dulu:
rem     .venv\Scripts\python.exe manage.py collectstatic --noinput
rem =====================================================================
cd /D "%~dp0"

if not defined XAMPP_HOME if exist "C:\xampp\mysql_start.bat" set "XAMPP_HOME=C:\xampp"
if not defined XAMPP_HOME if exist "D:\xampp\mysql_start.bat" set "XAMPP_HOME=D:\xampp"
if not defined XAMPP_HOME if exist "F:\xampp\mysql_start.bat" set "XAMPP_HOME=F:\xampp"
if not defined XAMPP_HOME set "XAMPP_HOME=C:\xampp"
echo        XAMPP: %XAMPP_HOME%

echo [1/3] MariaDB
tasklist /FI "IMAGENAME eq mysqld.exe" | findstr /I "mysqld.exe" >NUL
if errorlevel 1 (start "MariaDB" "%XAMPP_HOME%\mysql_start.bat") else (echo       sudah jalan, dilewati)

echo [2/3] waitress di 127.0.0.1:8099
rem  --trusted-proxy: waitress secara default MENGHAPUS header proxy (x-forwarded-*)
rem  sebelum sampai ke Django. Tanpa dua baris flag di bawah, Django selalu melihat
rem  REMOTE_ADDR 127.0.0.1 (rate limit jadi dipakai bersama semua pengguna) dan
rem  SECURE_PROXY_SSL_HEADER tidak pernah punya bukti HTTPS.
netstat -ano | findstr "127.0.0.1:8099" | findstr "LISTENING" >NUL
if errorlevel 1 (start "SIPPER waitress" .venv\Scripts\python.exe -m waitress --host=127.0.0.1 --port=8099 --threads=8 --trusted-proxy=127.0.0.1 --trusted-proxy-headers=x-forwarded-for --trusted-proxy-headers=x-forwarded-proto sipper.wsgi:application) else (echo       sudah jalan, dilewati)

echo [3/3] Apache di port 80
tasklist /FI "IMAGENAME eq httpd.exe" | findstr /I "httpd.exe" >NUL
if errorlevel 1 (start "Apache" "%XAMPP_HOME%\apache_start.bat") else (echo       sudah jalan, dilewati)

echo.
echo Tunggu beberapa detik lalu buka  http://localhost
echo phpMyAdmin tetap di  http://localhost/phpmyadmin/  - login pakai sipper_app
echo.
pause
