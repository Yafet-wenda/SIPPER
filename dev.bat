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
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --insecure
