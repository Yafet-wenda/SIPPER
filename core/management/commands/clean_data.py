"""Perintah pembersih data uji coba.

Perintah ini menghapus baris, jadi dia tidak pernah bekerja tanpa izin
eksplisit: --dry-run memperlihatkan isi database, dan penghapusan baru
jalan setelah --yes diberikan. Akun yang dilindungi dipakai sebagai batas
"jangan sentuh", sehingga admin yang tersisa di database hanyalah akun
tersebut beserta superuser.
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from core.models import (AuditLog, Dokumen, KartuDigital, Penduduk, Pengajuan,
                         Pemutakhiran, UserRole)

PILIHAN = (
    ('users', lambda: User.objects.count()),
    ('penduduk', lambda: Penduduk.objects.count()),
    ('pengajuan', lambda: Pengajuan.objects.count()),
    ('dokumen', lambda: Dokumen.objects.count()),
)


class Command(BaseCommand):
    help = ('Hapus data uji coba dan sisakan hanya satu akun admin. '
            'Pakai --dry-run untuk melihat tanpa menghapus, lalu --yes untuk menjalankan.')

    def add_arguments(self, parser):
        parser.add_argument('--admin', dest='admin_email', required=True,
                            help='Email akun admin yang tidak boleh dihapus.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Hitung dan tampilkan saja, tidak menghapus apa pun.')
        parser.add_argument('--yes', action='store_true',
                            help='Konfirmasi penghapusan. Tanpa bendera ini perintah berhenti.')

    def _stats(self):
        return {nama: hitung() for nama, hitung in PILIHAN}

    def handle(self, *args, **options):
        admin_email = options['admin_email'].strip()
        if not admin_email:
            raise CommandError('Nilai --admin tidak boleh kosong.')

        admin_user = User.objects.filter(email=admin_email).first()
        if admin_user is None:
            raise CommandError(f'Admin {admin_email} tidak ditemukan. Tidak ada yang diubah.')

        self.stdout.write(f'Admin yang dilindungi: {admin_user.username} (superuser={admin_user.is_superuser})')
        self.stdout.write('SEBELUM:')
        for nama, jumlah in self._stats().items():
            self.stdout.write(f'  {nama}: {jumlah}')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('dry-run: tidak ada baris yang dihapus.'))
            return
        if not options['yes']:
            raise CommandError(
                'Penghapusan butuh konfirmasi. Ulangi dengan --yes, atau periksa dulu dengan --dry-run.'
            )

        excluding = {
            AuditLog: ('user', admin_user),
            Pemutakhiran: ('penduduk__user', admin_user),
            KartuDigital: ('penduduk__user', admin_user),
            Dokumen: ('penduduk__user', admin_user),
            Pengajuan: ('penduduk__user', admin_user),
            Penduduk: ('user', admin_user),
            UserRole: ('user', admin_user),
        }
        for model, (relasi, akun) in excluding.items():
            model.objects.exclude(**{relasi: akun}).delete()
        User.objects.exclude(id=admin_user.id).exclude(is_superuser=True).delete()

        self.stdout.write('SETELAH:')
        for nama, jumlah in self._stats().items():
            self.stdout.write(f'  {nama}: {jumlah}')
        self.stdout.write(self.style.SUCCESS('Cleanup selesai.'))
