@echo off
rem =====================================================================
rem  DEV  -  server pengembangan SIPPER  ->  http://127.0.0.1:8000
rem
rem  PENTING - flag --insecure bukan lagi penentu gambar hilang.
rem  WhiteNoise (lihat MIDDLEWARE di sipper/settings.py) melayani /static/
rem  dari proses Django apa pun, jadi runserver tanpa --insecure tetap 200.
rem  Flag ini tetap dipakai karena membaca static/ langsung dari sumbernya:
rem  tanpa --insecure, file static baru butuh collectstatic dulu agar muncul.
rem
rem  Hanya untuk pengembangan. Untuk bentuk produksi pakai prod.bat
rem  (waitress + Apache di http://localhost).
rem
rem  DJANGO_DEBUG disetel di sini karena bawaan settings.py mati (fail-closed):
rem  tanpa baris ini halaman galat development tidak pernah muncul di dev.
rem =====================================================================
cd /D "%~dp0"
set "DJANGO_DEBUG=1"
rem .env memaksa tiga flag TLS demi produksi (Apache + https). Di dev tidak ada
rem TLS, jadi flag itu dimatikan dulu supaya http://127.0.0.1:8000 tetap bisa
rem dibuka; prod.bat tidak menyentuh baris ini dan tetap memakai nilai .env.
set "DJANGO_SECURE_SSL_REDIRECT=0"
set "DJANGO_SECURE_COOKIES=0"
set "DJANGO_HSTS_SECONDS=0"
rem Buka browser otomatis 4 detik setelah baris ini (server butuh waktu siap).
rem URL ditulis LENGKAP dengan https:// supaya Chrome tidak menaikkan ke https.
start "" /min cmd /c "timeout /t 4 /nobreak >nul & start https://127.0.0.1:8000/"
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --insecure
pause
