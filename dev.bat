@echo off
rem =====================================================================
rem  DEV  -  server pengembangan SIPPER  ->  https://127.0.0.1:8000
rem
rem  runserver_tls (lihat core/management/commands/runserver_tls.py) = runserver
rem  biasa tetapi socket-nya dibungkus TLS dengan sertifikat self-signed di
rem  tmp/dev-tls/. Alasannya: Chrome menaikkan URL yang diketik tanpa skema
rem  menjadi https, jadi server http polos di :8000 tidak pernah tersentuh.
rem  Kunjungan pertama menampilkan peringatan sertifikat - tekan
rem  Advanced -> Proceed to 127.0.0.1 (unsafe).
rem
rem  Flag --insecure di baris terakhir bukan soal TLS: flag itu membuat
rem  /static/ dibaca langsung dari static/ sumber, tanpa collectstatic dulu.
rem  WhiteNoise tetap melayani /static/ tanpa flag itu.
rem
rem  Hanya untuk pengembangan. Untuk bentuk produksi pakai prod.bat
rem  (waitress + Apache di https://localhost).
rem
rem  DJANGO_DEBUG disetel di sini karena bawaan settings.py mati (fail-closed):
rem  tanpa baris ini halaman galat development tidak pernah muncul di dev.
rem =====================================================================
cd /D "%~dp0"
set "DJANGO_DEBUG=1"
rem HSTS di sini WAJIB mati. Kalau aktif, peramban menyimpan host 127.0.0.1 sebagai
rem https-only dan tidak lagi menawarkan tombol "Proceed" untuk sertifikat
rem self-signed, sehingga dev macet penuh. Dua flag lain ikut dimatikan supaya dev
rem tidak pernah dialihkan; prod.bat tidak menyentuh baris ini dan tetap .env.
set "DJANGO_SECURE_SSL_REDIRECT=0"
set "DJANGO_SECURE_COOKIES=0"
set "DJANGO_HSTS_SECONDS=0"
rem Buka browser otomatis 4 detik setelah baris ini (server butuh waktu siap).
start "" /min cmd /c "timeout /t 4 /nobreak >nul & start https://127.0.0.1:8000/"
.venv\Scripts\python.exe manage.py runserver_tls 127.0.0.1:8000 --insecure
pause
