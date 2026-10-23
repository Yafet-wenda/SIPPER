"""Naikkan satu akun yang sudah ada menjadi petugas SIPPER.

Perintah ini hanya menulis baris UserRole, jadi tidak pernah menyentuh tabel
auth, sandi, maupun hak superuser. Dipakai alih-alih membuat akun petugas
lewat shell admin, supaya tidak ada sandi sementara yang muncul di riwayat
perintah.
"""
from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError

from core.models import UserRole


class Command(BaseCommand):
    help = 'Menandai akun yang sudah ada sebagai petugas, tanpa mengubah tabel auth.'

    def add_arguments(self, parser):
        parser.add_argument('username', help='Nama akun yang akan dijadikan petugas.')

    def handle(self, *args, **options):
        username = options['username'].strip()
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            raise CommandError(f'Akun "{username}" tidak ditemukan. Tidak ada yang diubah.')
        _, dibuat = UserRole.objects.update_or_create(user=user, defaults={'role': 'petugas'})
        kata = 'sekarang' if dibuat else 'tetap'
        self.stdout.write(self.style.SUCCESS(f'{user.username} {kata} memiliki role petugas.'))
