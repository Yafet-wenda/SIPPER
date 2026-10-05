"""Pulihkan hak akses sipper_app ke sipper_db setelah entri grant hilang.

Latar: crash/mati mendadak MariaDB dapat menghilangkan baris grant di tabel
privilege, sehingga login sipper_app tetap berhasil (password benar) tapi
Django gagal dengan error 1044 "Access denied ... to database".

Dijalankan sendiri oleh pengelola mesin ini (bukan oleh agen): password root
dibaca pakai getpass sehingga tidak pernah tampil di log maupun percakapan.

Langkahnya:
  1. Login ke MariaDB sebagai root (password root dipakai sebentar, tidak disimpan).
  2. GRANT ulang hak yang sama seperti saat pengerasan stack dulu, untuk setiap
     host tempat akun sipper_app terdaftar. Password akun TIDAK diubah.
  3. Sambungkan ulang sebagai sipper_app memakai .env sebagai bukti hasilnya.

Pakai:  .venv\\Scripts\\python.exe tools\\restore_db_grants.py
"""

import getpass
import re
import sys
from pathlib import Path

import pymysql

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / '.env'
# Sama seperti tools/set_db_password.py: nama akun dan host dipakai sebagai
# identifier SQL (tidak bisa diparameterisasi), jadi dibatasi ke karakter aman.
ACCOUNT_RE = re.compile(r'^[A-Za-z0-9_.:\-]{1,64}$')

PRIVILEGES = (
    'SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES, '
    'CREATE TEMPORARY TABLES, LOCK TABLES, EXECUTE, CREATE VIEW, SHOW VIEW, TRIGGER'
)


def env_value(key, default=''):
    if not ENV_FILE.exists():
        raise SystemExit(f'{ENV_FILE} tidak ditemukan.')
    prefix = f'{key}='
    for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip().strip('"').strip("'")
    return default


def quoted_account(name):
    if not ACCOUNT_RE.match(name or ''):
        raise SystemExit(f'Nama akun MariaDB tidak lazim: {name!r} — periksa DB_USER di .env.')
    return f"'{name}'"


def main():
    db_name = env_value('DB_NAME', 'sipper_db')
    app_user = env_value('DB_USER', 'sipper_app')
    host = env_value('DB_HOST', '127.0.0.1')
    port = int(env_value('DB_PORT', '3306'))

    print(f'Memulihkan hak akses {app_user} ke basis data {db_name} pada {host}:{port}.')
    root_password = getpass.getpass('Password root MariaDB: ')

    try:
        connection = pymysql.connect(host=host, port=port, user='root', password=root_password,
                                     charset='utf8mb4', autocommit=True)
    except pymysql.err.OperationalError as error:
        raise SystemExit(f'Login root gagal: {error}\n'
                         'Kalau password root lupa, jalankan tools\\reset-mariadb-root.bat dulu.')

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT host FROM mysql.user WHERE user = %s', (app_user,))
            hosts = [row[0] for row in cursor.fetchall()]
            if not hosts:
                raise SystemExit(f'Akun {app_user} tidak ada di MariaDB - pakai tools\\set_db_password.py.')
            for db_host in hosts:
                cursor.execute(
                    f'GRANT {PRIVILEGES} ON {quoted_account(db_name)}.* '
                    f'TO {quoted_account(app_user)}@{quoted_account(db_host)}'
                )
                print(f'GRANT dijalankan untuk {app_user}@{db_host}.')
            cursor.execute('FLUSH PRIVILEGES')
    finally:
        connection.close()

    probe = pymysql.connect(host=host, port=port, user=app_user, password=env_value('DB_PASSWORD'),
                            database=db_name, charset='utf8mb4')
    try:
        with probe.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM django_migrations')
            count = cursor.fetchone()[0]
            cursor.execute('SHOW GRANTS')
            grants = [row[0] for row in cursor.fetchall()]
    finally:
        probe.close()

    print(f'Verifikasi: koneksi {app_user} ke {db_name} berhasil; django_migrations berisi {count} baris.')
    for grant in grants:
        print('  ', grant)
    print('Selesai. Jalankan lagi server SIPPER (dev.bat atau prod.bat).')


if __name__ == '__main__':
    sys.exit(main())
