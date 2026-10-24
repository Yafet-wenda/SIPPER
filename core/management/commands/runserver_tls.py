"""Server pengembangan lewat TLS: https://127.0.0.1:8000 dengan sertifikat self-signed.

Peramban modern menaikkan URL yang diketik tanpa skema menjadi https, jadi `runserver`
polos selalu berakhir ERR_SSL_PROTOCOL_ERROR sebelum satu bit pun sampai ke Django.
Perintah ini membungkus socket pendengaran milik runserver dengan TLS sehingga semua
sifat development tetap utuh (autoreload, halaman galat, /static/ dari sumber) sambil
alamat yang diminta peramban benar-benar dilayani.

Sertifikatnya dibuat sekali di tmp/dev-tls/ (dikecualikan .gitignore) memakai
apache/ssl/sipper-openssl.cnf, jadi SAN-nya sama dengan sertifikat produksi: localhost,
sipper.localhost, 127.0.0.1. Penerbitnya bukan CA, jadi peramban tetap menampilkan
peringatan kepercayaan pada kunjungan pertama — tekan Advanced → Proceed once per sesi.
"""
import shutil
import ssl
import subprocess
from pathlib import Path

from django.contrib.staticfiles.management.commands.runserver import Command as RunserverCommand
from django.core.management.base import CommandError

REPO_ROOT = Path(__file__).resolve().parents[3]
CERT_DIR = REPO_ROOT / 'tmp' / 'dev-tls'
OPENSSL_CNF = REPO_ROOT / 'apache' / 'ssl' / 'sipper-openssl.cnf'


def sertifikat_dev():
    """Path (sertifikat, kunci) untuk dev; pasangan baru dibuat lewat openssl bila belum ada."""
    crt, key = CERT_DIR / 'dev.crt', CERT_DIR / 'dev.key'
    if crt.exists() and key.exists():
        return crt, key
    openssl = shutil.which('openssl')
    if not openssl:
        raise CommandError(
            f'Belum ada sertifikat dev di {CERT_DIR} dan openssl tidak ada di PATH. Buat sekali:\n'
            f'  mkdir "{CERT_DIR}"\n'
            f'  openssl req -x509 -newkey rsa:2048 -nodes -days 825 -batch '
            f'-config "{OPENSSL_CNF}" -extensions v3_req '
            f'-keyout "{key}" -out "{crt}"')
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run([openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '825', '-batch',
                    '-config', str(OPENSSL_CNF), '-extensions', 'v3_req',
                    '-keyout', str(key), '-out', str(crt)], check=True)
    return crt, key


def server_tls(base_cls, crt, key):
    """Kelas server yang membungkus socket-nya sendiri dengan TLS sesudah listen."""
    konteks = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    konteks.load_cert_chain(certfile=str(crt), keyfile=str(key))

    class TLSServer(base_cls):
        def server_activate(self):
            super().server_activate()
            self.socket = konteks.wrap_socket(self.socket, server_side=True)

    return TLSServer


class Command(RunserverCommand):
    help = 'Menjalankan server pengembangan di https:// dengan sertifikat self-signed.'
    protocol = 'https'

    def handle(self, *args, **options):
        crt, key = sertifikat_dev()
        self.server_cls = server_tls(self.server_cls, crt, key)
        super().handle(*args, **options)
