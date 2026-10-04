@echo off
rem =====================================================================
rem  DEV  -  server pengembangan SIPPER  ->  http://127.0.0.1:8000
rem
rem  PENTING - flag --insecure itu WAJIB di mesin ini.
rem  .env memakai DEBUG=0 (profil produksi) dan Django runserver berhenti
rem  melayani file static saat DEBUG=0. Tanpa --insecure, URL
rem  /static/img/banner-hero.jpg membalas 404 sehingga hero landing page
rem  tampak kosong / tanpa gambar.
rem
rem  Hanya untuk pengembangan. Untuk bentuk produksi pakai prod.bat
rem  (waitress + Apache di http://localhost).
rem =====================================================================
cd /D D:\SIPPER
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --insecure
