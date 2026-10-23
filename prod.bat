@echo off
rem =====================================================================
rem  PROD-LOKAL  -  SIPPER bentuk produksi di mesin ini  ->  http://localhost
rem
rem  Urutan: MariaDB -> collectstatic -> waitress (WSGI di 127.0.0.1:8099) ->
rem  Apache (:80, proxy ke waitress). Static dilayani Apache lewat Alias
rem  /static/ ke <folder proyek>\staticfiles. Media TIDAK pernah dibuka
rem  langsung, semuanya lewat view pemeriksa hak akses.
rem
rem  SEKALI PER MESIN, sebelum skrip ini ada gunanya:
rem      powershell -ExecutionPolicy Bypass -File scripts\install-apache-config.ps1 -Restart
rem  Skrip itu menyalakan mod_proxy_http dan memasang
rem  conf\extra\httpd-sipper.conf. Tanpa itu Apache menerima request lalu
rem  membalas 502 karena tidak bisa bicara HTTP ke waitress.
rem
rem  Lokasi XAMPP dideteksi otomatis (C:, D:, lalu F:). Kalau berada di tempat
rem  lain, set lebih dulu:  set XAMPP_HOME=E:\xampp
rem
rem  Nilai DJANGO_* di bawah menimpa isi .env, karena python-dotenv tidak
rem  menimpa variabel yang sudah ada di lingkungan. Yang ditimpa hanyalah
rem  DJANGO_DEBUG, DJANGO_ALLOWED_HOSTS, dan DJANGO_CSRF_TRUSTED_ORIGINS -
rem  jadi .env boleh tetap DJANGO_DEBUG=1 untuk dev.bat. Nilai lain
rem  (DB_HOST, DJANGO_EMAIL_BACKEND, dan tiga nilai keamanan TLS) tetap
rem  dibaca dari .env.
rem =====================================================================
cd /D "%~dp0"

if not defined XAMPP_HOME if exist "C:\xampp\mysql_start.bat" set "XAMPP_HOME=C:\xampp"
if not defined XAMPP_HOME if exist "D:\xampp\mysql_start.bat" set "XAMPP_HOME=D:\xampp"
if not defined XAMPP_HOME if exist "F:\xampp\mysql_start.bat" set "XAMPP_HOME=F:\xampp"
if not defined XAMPP_HOME set "XAMPP_HOME=C:\xampp"
echo        XAMPP: %XAMPP_HOME%

rem --- profil produksi -------------------------------------------------------
if not defined DJANGO_DEBUG set "DJANGO_DEBUG=0"
if not defined DJANGO_ALLOWED_HOSTS set "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1"
if not defined DJANGO_CSRF_TRUSTED_ORIGINS set "DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost,http://127.0.0.1,https://localhost,https://127.0.0.1"
rem  Tiga nilai TLS (DJANGO_SECURE_SSL_REDIRECT, DJANGO_SECURE_COOKIES,
rem  DJANGO_HSTS_SECONDS) SENGAJA tidak dipaksa di sini. `set` di blok ini
rem  berlaku sebagai variabel lingkungan proses, dan python-dotenv tidak menimpa
rem  yang sudah ada -- jadi selama ini angka itulah yang menang atas .env, bukan
rem  sebaliknya. Apache sudah melayani :443 dan mengirim X-Forwarded-Proto
rem  (apache/sipper-httpd.conf), maka keputusannya dikembalikan ke .env; tanpa
rem  .env sekalipun settings.py sudah gagal-tertutup ke nilai aman saat DEBUG=0.

rem  Cari assignment yang benar-benar berisi, bukan sekadar ada barisnya:
rem  "DJANGO_SECRET_KEY=" kosong juga membuat Django menolak start. findstr
rem  tidak mengenal "+", jadi ".." (dua karakter apa pun) yang dipakai.
if defined DJANGO_SECRET_KEY goto :punya_kunci
findstr /R /C:"^DJANGO_SECRET_KEY=.." .env >NUL 2>&1
if errorlevel 1 echo        PERHATIAN: DJANGO_SECRET_KEY kosong. Dengan DJANGO_DEBUG=0 Django menolak start - isi dulu di .env.
findstr /I /R /C:"^DJANGO_SECRET_KEY=replace" /C:"^DJANGO_SECRET_KEY=ganti" /C:"^DJANGO_SECRET_KEY=changeme" .env >NUL 2>&1
if not errorlevel 1 echo        PERHATIAN: DJANGO_SECRET_KEY masih nilai contoh dari .env.example - ganti dengan nilai acak panjang.
:punya_kunci

echo [1/4] MariaDB
tasklist /FI "IMAGENAME eq mysqld.exe" | findstr /I "mysqld.exe" >NUL
if errorlevel 1 (start "MariaDB" "%XAMPP_HOME%\mysql_start.bat") else (echo       sudah jalan, dilewati)

echo [2/4] collectstatic
if exist staticfiles\admin (
    echo       sudah tersusun, dilewati. Kalau ada file static berubah, jalankan:
    echo          .venv\Scripts\python.exe manage.py collectstatic --noinput
) else (
    echo       staticfiles masih kosong, menyusun ...
    "%~dp0.venv\Scripts\python.exe" manage.py collectstatic --noinput
)

echo [3/4] waitress di 127.0.0.1:8099
rem  --trusted-proxy: waitress secara default MENGHAPUS header proxy (x-forwarded-*)
rem  sebelum sampai ke Django. Tanpa dua baris flag di bawah, Django selalu melihat
rem  REMOTE_ADDR 127.0.0.1 (rate limit jadi dipakai bersama semua pengguna) dan
rem  SECURE_PROXY_SSL_HEADER tidak pernah punya bukti HTTPS.
netstat -ano | findstr "127.0.0.1:8099" | findstr "LISTENING" >NUL
if errorlevel 1 (start "SIPPER waitress" "%~dp0.venv\Scripts\python.exe" -m waitress --host=127.0.0.1 --port=8099 --threads=8 --trusted-proxy=127.0.0.1 --trusted-proxy-headers=x-forwarded-for --trusted-proxy-headers=x-forwarded-proto sipper.wsgi:application) else (echo       sudah jalan, dilewati)

echo [4/4] Apache di port 80 (alihan) dan 443 (TLS)
if not exist "%XAMPP_HOME%\apache\conf\extra\httpd-sipper.conf" echo       PERHATIAN: conf\extra\httpd-sipper.conf belum dipasang - http://localhost tidak akan meneruskan ke waitress. Jalankan install-apache-config.ps1 di baris paling atas.
tasklist /FI "IMAGENAME eq httpd.exe" | findstr /I "httpd.exe" >NUL
if errorlevel 1 (start "Apache" "%XAMPP_HOME%\apache_start.bat") else (echo       sudah jalan, dilewati - kalau konfigurasi baru saja dipasang, tutup jendela konsol Apache lalu jalankan apache_start.bat lagi)

echo.
echo Tunggu beberapa detik lalu buka  https://localhost
echo   Sertifikatnya masih bawaan XAMPP, jadi peramban menampilkan peringatan
echo   "sambungan Anda tidak privat" - lanjutkan; itu bukan galat aplikasi.
echo   http://localhost dibalas 301 ke alamat yang sama di atas https.
echo Cek cepat                   https://localhost/health/
echo phpMyAdmin tetap di  http://localhost/phpmyadmin/  - login pakai sipper_app
echo.
pause
