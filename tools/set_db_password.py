"""Setel ulang password akun database sipper_app dan selaraskan .env.

Dijalankan sendiri oleh pengelola mesin ini (bukan oleh agen): password dibaca
pakai getpass sehingga tidak pernah tampil di log maupun percakapan.

Langkahnya:
  1. Login ke MariaDB sebagai root (password root dipakai sebentar, tidak disimpan).
  2. Ganti password sipper_app untuk setiap host tempat akun itu ada.
  3. Perbarui DB_PASSWORD di .env, lalu pastikan DJANGO_CSRF_TRUSTED_ORIGINS
     memuat origin http dan https untuk localhost/127.0.0.1.
  4. Sambungkan ulang dengan .env yang baru sebagai bukti hasilnya.

Pakai:  .venv\\Scripts\\python.exe tools\\set_db_password.py
"""

import getpass
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pymysql

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / '.env'
# Nama akun dan host dipakai sebagai identifier SQL (tidak bisa diparameterisasi),
# jadi dibatasi ke karakter yang aman: titik dan strip perlu untuk host seperti
# 127.0.0.1; tanda kutip, spasi, backtick, dan titik-koma tidak lolos.
ACCOUNT_RE = re.compile(r'^[A-Za-z0-9_.:\-]{1,64}$')


def quoted_account(name):
    if not ACCOUNT_RE.match(name or ''):
        raise SystemExit(f'Nama akun MariaDB tidak lazim: {name!r} — periksa DB_USER di .env.')
    return f"'{name}'"


def read_env_lines(path):
    if not path.exists():
        raise SystemExit(f'{path} tidak ditemukan.')
    return path.read_text(encoding='utf-8').splitlines()


def env_value(lines, key):
    prefix = f'{key}='
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix):].strip().strip('"').strip("'")
    return ''


def set_env_value(lines, key, value):
    """Ganti satu kunci tanpa mengutak-atik baris lain; tambahkan bila belum ada."""
    prefix = f'{key}='
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = f'{key}={value}'
            return lines
    lines.append(f'{key}={value}')
    return lines


def main():
    lines = read_env_lines(ENV_FILE)
    db_name = env_value(lines, 'DB_NAME') or 'sipper_db'
    app_user = env_value(lines, 'DB_USER') or 'sipper_app'
    host = env_value(lines, 'DB_HOST') or '127.0.0.1'
    port = int(env_value(lines, 'DB_PORT') or '3306')

    print(f'Target: {app_user} pada {host}:{port} (basis data {db_name}).')
    new_password = getpass.getpass(f'Password baru untuk {app_user}: ')
    if new_password != getpass.getpass('Ulangi password baru: '):
        raise SystemExit('Keduanya tidak sama, tidak ada yang diubah.')
    if len(new_password) < 12:
        raise SystemExit('Password terlalu pendek (minimal 12 karakter).')
    root_password = getpass.getpass('Password root MariaDB: ')

    try:
        connection = pymysql.connect(host=host, port=port, user='root', password=root_password,
                                     charset='utf8mb4', autocommit=True)
    except pymysql.err.OperationalError as error:
        raise SystemExit(f'Login root gagal: {error}\nJalankan tools\\reset-mariadb-root.bat dulu bila password root hilang.')

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT host FROM mysql.user WHERE user = %s', (app_user,))
            hosts = [row[0] for row in cursor.fetchall()]
            if not hosts:
                # Akun hilang: buat ulang dengan hak minimal pada satu basis data saja,
                # sama seperti saat pengerasan stack dulu.
                cursor.execute(f"CREATE USER {quoted_account(app_user)}@{quoted_account('localhost')} IDENTIFIED BY %s", (new_password,))
                for basis in (db_name, f'test_{db_name}'):
                    cursor.execute(
                        f"GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES, "
                        f"CREATE TEMPORARY TABLES, LOCK TABLES, EXECUTE, CREATE VIEW, SHOW VIEW, TRIGGER "
                        f"ON {quoted_account(basis)}.* TO {quoted_account(app_user)}@{quoted_account('localhost')}"
                    )
                hosts = ['localhost']
            for db_host in hosts:
                # MariaDB 10.4 menolak bentuk SET PASSWORD FOR ... = 'teks' dengan
                # galat 1372 (literal dibaca sebagai hash), jadi ALTER USER dipakai.
                cursor.execute(f"ALTER USER {quoted_account(app_user)}@{quoted_account(db_host)} IDENTIFIED BY %s", (new_password,))
            cursor.execute('FLUSH PRIVILEGES')
        print(f'Password {app_user} diganti untuk host: {", ".join(hosts)}.')
    finally:
        connection.close()

    backup = ENV_FILE.with_name(f'.env.bak-{datetime.now():%Y%m%d-%H%M%S}')
    backup.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    lines = set_env_value(lines, 'DB_PASSWORD', new_password)
    origins = env_value(lines, 'DJANGO_CSRF_TRUSTED_ORIGINS')
    required = ['http://localhost', 'http://127.0.0.1', 'https://localhost', 'https://127.0.0.1']
    merged = [origin.strip() for origin in origins.split(',') if origin.strip()]
    merged += [origin for origin in required if origin not in merged]
    lines = set_env_value(lines, 'DJANGO_CSRF_TRUSTED_ORIGINS', ','.join(merged))
    ENV_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'.env diperbarui (cadangan: {backup.name}).')

    os.environ['DB_ENGINE'] = 'mysql'
    for key in ('DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT'):
        os.environ[key] = env_value(read_env_lines(ENV_FILE), key)
    probe = pymysql.connect(host=host, port=port, user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'],
                            database=os.environ['DB_NAME'], charset='utf8mb4')
    probe.close()
    print('Verifikasi: koneksi ke basis data dengan .env yang baru berhasil.')
    print('Langkah terakhir: restart Waitress agar memakai password yang baru (prod.bat).')


if __name__ == '__main__':
    sys.exit(main())
