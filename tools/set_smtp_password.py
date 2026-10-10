"""Setel kredensial SMTP Gmail di .env lalu buktikan dengan satu email nyata.

Dijalankan sendiri oleh pengelola mesin ini (bukan oleh agen): App Password
dibaca pakai getpass sehingga tidak pernah tampil di log, di riwayat perintah,
maupun di percakapan.

Yang ditulis ke .env:
  DJANGO_EMAIL_BACKEND   = django.core.mail.backends.smtp.EmailBackend
  DJANGO_EMAIL_HOST      = smtp.gmail.com
  DJANGO_EMAIL_PORT      = 587
  DJANGO_EMAIL_USE_TLS   = 1
  DJANGO_EMAIL_HOST_USER = wendayafet@gmail.com
  DJANGO_EMAIL_HOST_PASSWORD = <16 karakter dari Google App Passwords>
  DJANGO_DEFAULT_FROM_EMAIL  = "SIPPER <wendayafet@gmail.com>"

Syarat Gmail: akun harus sudah 2-Step Verification, lalu buat App Password di
https://myaccount.google.com/apppasswords (16 karakter, spasi dihapus otomatis).
Password biasa tidak akan diterima Google.

Pakai:  .venv\\Scripts\\python.exe tools\\set_smtp_password.py [email-tujuan-uji]
"""

import getpass
import os
import sys
from datetime import datetime

import django
from django.conf import settings
from django.core.mail import EmailMessage

from set_db_password import BASE_DIR, ENV_FILE, env_value, read_env_lines, set_env_value

GMAIL_HOST = 'smtp.gmail.com'
GMAIL_PORT = 587
PLACEHOLDER_DOMAINS = ('example.com', 'example.org', 'localhost')


def is_placeholder(value):
    return not value or any(domain in value.lower() for domain in PLACEHOLDER_DOMAINS)


def ask_address(current):
    default = '' if is_placeholder(current) else current
    while True:
        raw = input(f'Alamat Gmail pengirim{f" [{default}]" if default else ""}: ').strip()
        address = raw or default
        if not address:
            print('Alamat belum diisi.')
            continue
        if not address.endswith('@gmail.com'):
            setuju = input('Bukan alamat @gmail.com. Tetap lanjutkan? [y/N]: ').strip().lower()
            if setuju not in ('y', 'ya'):
                continue
        return address


def ask_app_password():
    password = getpass.getpass('App Password Gmail (16 karakter, spasi boleh): ').replace(' ', '')
    if len(password) < 8:
        raise SystemExit('App Password terlalu pendek. Ambil dari https://myaccount.google.com/apppasswords')
    return password


def main():
    lines = read_env_lines(ENV_FILE)
    current_user = env_value(lines, 'DJANGO_EMAIL_HOST_USER')
    sender = ask_address(current_user)
    password = ask_app_password()

    from_email = f'SIPPER <{sender}>'
    recipient = (sys.argv[1] if len(sys.argv) > 1 else '').strip() or sender

    backup = ENV_FILE.with_name(f'.env.bak-{datetime.now():%Y%m%d-%H%M%S}')
    backup.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for key, value in {
        'DJANGO_EMAIL_BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
        'DJANGO_EMAIL_HOST': GMAIL_HOST,
        'DJANGO_EMAIL_PORT': str(GMAIL_PORT),
        'DJANGO_EMAIL_USE_TLS': '1',
        'DJANGO_EMAIL_HOST_USER': sender,
        'DJANGO_EMAIL_HOST_PASSWORD': password,
        'DJANGO_DEFAULT_FROM_EMAIL': from_email,
    }.items():
        lines = set_env_value(lines, key, value)
    ENV_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'.env diperbarui (cadangan: {backup.name}).')

    sys.path.insert(0, str(BASE_DIR))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sipper.settings')
    django.setup()
    print(f'Mengirim uji lewat {settings.EMAIL_HOST}:{settings.EMAIL_PORT} sebagai {sender} ke {recipient} ...')
    message = EmailMessage(subject='[SIPPER] Uji SMTP',
                           body='Kalau pesan ini masuk ke inbox, konfigurasi email SIPPER sudah berfungsi.',
                           from_email=settings.DEFAULT_FROM_EMAIL,
                           to=[recipient])
    try:
        message.send(fail_silently=False)
    except Exception as error:
        print(f'Gagal kirim: {type(error).__name__}: {error}')
        print('Kemungkinan penyebab:')
        print('  - App Password salah atau kadaluarsa -> buat ulang di https://myaccount.google.com/apppasswords')
        print('  - 2-Step Verification belum aktif -> aktifkan dulu, App Password tidak tersedia tanpa itu')
        print('  - Port 587 diblokir jaringan -> coba jaringan lain (settings hanya membaca USE_TLS; port 465 perlu DJANGO_EMAIL_USE_SSL ditambahkan ke settings.py)')
        print(f'Kembali ke kondisi sebelumnya: salin {backup.name} menjadi .env')
        return 1
    print('Terkirim. Cek inbox (dan folder Spam) untuk memastikan.')
    print('Langkah terakhir: restart Waitress (prod.bat) agar proses yang berjalan memakai .env yang baru.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
